"""
Predictor — предсказательная модель (мозг — машина предсказаний).

Мозг постоянно предсказывает: «если я сделаю X, станет ли мне легче?»
Здесь это реализовано через кортикальную колонну (NeuralColumn), которая
учится на опыте связывать (состояние + действие) → изменение драйвов.

Новое:
  * simulate(action, drives, state) — предсказать состояние ПОСЛЕ действия;
  * rollout(drives, state, actions) — «прокрутить в уме» цепочку действий
    (мысленная симуляция — основа планирования и воображения);
  * best_action(...) — выбрать действие, максимально снижающее напряжение.

API совместим со старым: predict_relief / observe_relief / consolidate /
save_periodic / summary.
"""
import json
import os
import random
import numpy as np

from core.neural_column import NeuralColumn


PREDICTOR_FILE = "data/neural_predictor.npz"
VALUE_TABLE_FILE = "data/relief_table.json"
DRIVE_THRESHOLD = 0.05

# Список действий — должен совпадать с bot.js
ACTION_NAMES = [
    'step_forward', 'step_back', 'step_left', 'step_right',
    'jump_once', 'jump_forward', 'sprint_short', 'sneak',
    'go_to_player', 'walk_away_from_player', 'come_close_to_player',
    'stay_here', 'look_at_player', 'look_around',
    'dig_forward', 'dig_down', 'dig_up', 'dig_nearby', 'dig_tree',
    'escape_pit', 'place_block', 'build_shelter',
    'drop_item', 'eat_food', 'equip_best_armor', 'hold_item',
    'attack_nearest', 'find_and_attack',
    'flee_from_hostile', 'attack_hostile',
    'look_up', 'look_down', 'spin_around', 'stop',
    'interact', 'wait_1sec', 'mimic_last',
    'look_at_position', 'go_to_position',
    'force_break_out', 'unequip_armor',
]

DRIVES = ['hunger', 'fear', 'pain', 'boredom', 'loneliness',
          'fatigue', 'curiosity', 'comfort']

# Веса важности драйвов для интегрального «напряжения».
# comfort исключён: это производная величина, а не независимая потребность,
# и её предсказание только шумит (см. _tension).
DRIVE_WEIGHTS = {
    'hunger': 1.2, 'fear': 1.5, 'pain': 1.4, 'boredom': 0.7,
    'loneliness': 1.0, 'fatigue': 0.9, 'curiosity': 0.5, 'comfort': 0.0,
}

# Сколько компонент до action-блока: 3 HP + 3 food + 1 night + 2 player + 2 hostile + 8 drives
STATE_SIZE = 3 + 3 + 1 + 2 + 2 + len(DRIVES)
N_INPUT = STATE_SIZE + len(ACTION_NAMES)


class Predictor:
    def __init__(self):
        n_hidden = 64
        n_output = len(DRIVES)

        self.column = NeuralColumn(N_INPUT, n_hidden, n_output)

        self.experience = []
        self.MAX_EXPERIENCE = 500
        self._cache = {}
        self._last_drives = {}   # последнее наблюдённое состояние драйвов

        # Быстрая ассоциативная память: action -> drive -> сглаженный релиф.
        # Это «стриатум/гиппокамп»: учится с одного-двух раз, надёжен.
        self.relief_table = {}
        self.load_table()

        if self.column.load(PREDICTOR_FILE):
            st = self.column.stats()
            print(f"🧠 Нейроколонна загружена: {st['updates']} обновлений, "
                  f"{st['sparsity_pct']:.0f}% живых синапсов, "
                  f"ошибка {st['recent_error']:.3f}")
        else:
            print(f"🧠 Нейроколонна новая ({N_INPUT}→{n_hidden}→{n_output}) "
                  f"[{len(ACTION_NAMES)} действий]")

    # ============ ENCODING ============

    def _encode(self, action, drives_dict, state):
        x = np.zeros(N_INPUT, dtype=np.float64)
        idx = 0

        hp = state.get('health', 20) or 20
        if hp < 8:
            x[idx] = 1.0
        elif hp < 15:
            x[idx + 1] = 1.0
        else:
            x[idx + 2] = 1.0
        idx += 3

        food = state.get('food', 20) or 20
        if food < 8:
            x[idx] = 1.0
        elif food < 15:
            x[idx + 1] = 1.0
        else:
            x[idx + 2] = 1.0
        idx += 3

        if state.get('is_night'):
            x[idx] = 1.0
        idx += 1

        p = state.get('player')
        if p and p.get('distance', 999) < 10:
            x[idx] = 1.0
        else:
            x[idx + 1] = 1.0
        idx += 2

        if state.get('nearest_hostile'):
            x[idx] = 1.0
        else:
            x[idx + 1] = 1.0
        idx += 2

        for i, d in enumerate(DRIVES):
            v = drives_dict.get(d, 0.0)
            x[idx + i] = min(1.0, max(0.0, float(v)))
        idx += len(DRIVES)

        if action and action in ACTION_NAMES:
            ai = ACTION_NAMES.index(action)
            x[idx + ai] = 1.0

        return x

    # ============ БЫСТРАЯ АССОЦИАТИВНАЯ ПАМЯТЬ ============

    def load_table(self):
        if not os.path.exists(VALUE_TABLE_FILE):
            return
        try:
            with open(VALUE_TABLE_FILE, 'r', encoding='utf-8') as f:
                self.relief_table = json.load(f)
        except Exception:
            pass

    def save_table(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(VALUE_TABLE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.relief_table, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _table_get(self, action, drive):
        return self.relief_table.get(action, {}).get(drive)

    def _table_update(self, action, drive, relief, lr=0.3):
        d = self.relief_table.setdefault(action, {})
        old = d.get(drive, 0.0)
        d[drive] = round(old + lr * (relief - old), 4)

    # ============ PREDICT ============

    def _tension(self, drive_vec):
        """Интегральное напряжение по предсказанному вектору драйвов."""
        t = 0.0
        for i, d in enumerate(DRIVES):
            t += float(drive_vec[i]) * DRIVE_WEIGHTS.get(d, 1.0)
        return t

    def predict_relief(self, action, drives_dict, state):
        """Общий предсказанный релиф от действия (взвешен по силе драйвов)."""
        self._last_drives = dict(drives_dict)
        x = self._encode(action, drives_dict, state)
        h, out = self.column.forward(x)
        self._cache[action] = (x, h, out)

        relief = self.simulate(action, drives_dict, state)
        total = 0.0
        weight = 0.0
        for i, d in enumerate(DRIVES):
            v = drives_dict.get(d, 0.0)
            if v < DRIVE_THRESHOLD or DRIVE_WEIGHTS.get(d, 0.0) <= 0:
                continue
            total += float(relief[i]) * v
            weight += v

        if weight == 0:
            return 0.1
        return float(total / weight)

    def simulate(self, action, drives_dict, state):
        """
        Предсказать, насколько действие снизит каждый драйв (вектор облегчения).

        Два «мозга» вместе:
          * нейроколонна — обобщает и переносит опыт на новые ситуации;
          * быстрая таблица — надёжно помнит, что именно помогло.
        Если есть прямой опыт по этой паре (action, drive) — доверяем таблице,
        иначе опираемся на обобщение колонны.
        """
        x = self._encode(action, drives_dict, state)
        neural = self.column.imagine(x, steps=1)
        out = np.array(neural, dtype=np.float64)
        for i, d in enumerate(DRIVES):
            t = self._table_get(action, d)
            if t is not None:
                out[i] = 0.25 * out[i] + 0.75 * t
        return out

    def action_value(self, action, drives_dict, state):
        """
        Ценность действия = предсказанное облегчение × важность × насколько
        драйв сейчас силён. Необученные действия дают ~0 (не выглядят выгодными).
        """
        relief = self.simulate(action, drives_dict, state)
        value = 0.0
        for i, d in enumerate(DRIVES):
            w = DRIVE_WEIGHTS.get(d, 0.0)
            cur = drives_dict.get(d, 0.0)
            if w <= 0 or cur < DRIVE_THRESHOLD:
                continue
            value += float(relief[i]) * w * cur
        return value

    def best_action(self, drives_dict, state, candidates):
        """
        Выбрать действие с наибольшей предсказанной ценностью.
        Это «мысленная примерка» каждого варианта перед действием.
        """
        best, best_val = None, -1e9
        for a in candidates:
            val = self.action_value(a, drives_dict, state)
            if val > best_val:
                best_val, best = val, a
        return best, best_val

    def rollout(self, drives_dict, state, action_sequence):
        """
        «Прокрутить в уме» цепочку действий: каждое действие снижает драйвы
        на предсказанную величину. Возвращает итоговое напряжение — оценку плана.
        """
        cur = {d: float(drives_dict.get(d, 0.0)) for d in DRIVES}
        for a in action_sequence:
            relief = self.simulate(a, cur, state)
            for i, d in enumerate(DRIVES):
                cur[d] = float(np.clip(cur[d] - relief[i], 0.0, 1.0))
        return self._tension(np.array([cur[d] for d in DRIVES]))

    # ============ OBSERVE ============

    def observe_relief(self, action, drive, state, relief_amount, learning_rate=0.3):
        # Кодируем состояние с полным набором драйвов (как при предсказании),
        # чтобы ассоциация переносилась на реальные ситуации.
        drives_now = dict(self._last_drives)
        drives_now[drive] = 1.0
        x = self._encode(action, drives_now, state)
        h, out = self.column.forward(x)

        target = out.copy()
        if drive in DRIVES:
            i = DRIVES.index(drive)
            target[i] = float(relief_amount)

        # Скорость обучения растёт с дофамином, но не падает до нуля
        lr = 0.02 + 0.06 * float(learning_rate)
        self.column.learn(x, h, out, target, dopamine=learning_rate, lr=lr)

        # Быстрая ассоциативная запись (стриатум/гиппокамп)
        self._table_update(action, drive, relief_amount, lr=0.15 + 0.25 * float(learning_rate))

        self.experience.append((x.copy(), h.copy(), out.copy(), target.copy(), learning_rate))
        if len(self.experience) > self.MAX_EXPERIENCE:
            self.experience.pop(0)

    # ============ CONSOLIDATION ============

    def consolidate(self):
        """«Сон»: повторяем случайный опыт без новой среды (офлайн-обучение)."""
        if len(self.experience) < 20:
            return
        sample = random.sample(self.experience, min(50, len(self.experience)))
        for x, h, out, target, dopamine in sample:
            self.column.learn(x, h, out, target, dopamine=dopamine * 0.5, lr=0.005)
        st = self.column.stats()
        print(f"😴 Консолидация: {len(sample)} воспроизведений, ошибка {st['recent_error']:.3f}")

    def save_periodic(self):
        self.column.save(PREDICTOR_FILE)
        self.save_table()

    def summary(self):
        st = self.column.stats()
        return (f"🧠 нейроколонна: {st['updates']} обновлений, "
                f"{st['sparsity_pct']:.0f}% живых связей, "
                f"{st['spikes']} спайков, ошибка {st['recent_error']:.3f}")
