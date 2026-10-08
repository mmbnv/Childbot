"""
Cortex — моторное решение (что делать прямо сейчас).

Выбор действия соединяет три вещи, как в реальном мозге:
  1. предсказание облегчения (predictor — «мысленная примерка»);
  2. уверенность в себе (self_model — «получится ли у меня»);
  3. нейромодуляцию (exploration — «тяга к новому», patience — «терпение»).

После действия cortex.observe() сравнивает ожидание и реальность и учит
предсказательную модель (дофаминовая ошибка).
"""
import random
import time


ACTION_POOL = [
    'step_forward', 'step_back', 'step_left', 'step_right',
    'jump_once', 'jump_forward', 'sprint_short',
    'go_to_player', 'walk_away_from_player', 'come_close_to_player',
    # stay_here / wait_1sec / stop / sneak не в свободном выборе: они не
    # двигают и не меняют мир, из-за них существо «застывало». Доступны
    # как явные команды, в планах и во сне.
    'look_at_player', 'look_around',
    # dig_down не входит: он всегда копает блок под ногами и роняет
    # существо в яму. Оставлен только как явная команда папы.
    # escape_pit вне ямы ничего не делает — вызывается только мозгом по факту.
    'dig_forward', 'dig_up', 'dig_nearby', 'dig_tree',
    'place_block', 'build_shelter',
    'drop_item', 'eat_food', 'equip_best_armor', 'hold_item',
    'attack_nearest', 'find_and_attack',
    'flee_from_hostile', 'attack_hostile',
    'look_up', 'look_down', 'spin_around',
    # проход и соединение — фундаментальные умения, доступные и вне ремесла
    'use', 'interact',
]


class Cortex:
    def __init__(self, adapter, drives, neuromod, predictor, self_model, world_model,
                 catalog, advisor=None):
        self.adapter = adapter
        self.drives = drives
        self.neuromod = neuromod
        self.predictor = predictor
        self.self_model = self_model
        self.world_model = world_model
        self.catalog = catalog
        # advisor(features, action) -> (bonus, forbid): подсказка от понятий
        # о мире (гравитация, дверь, опасность...). Мозг устанавливает её после
        # создания ConceptLearner.
        self.advisor = advisor

        self.pending_action = None
        self.pending_drives_before = None
        self.pending_context = None
        self.pending_prediction = None
        self.pending_time = 0
        self.last_action = None
        self.last_result = None
        self._recent_actions = []

    def snapshot_drives(self):
        return self.drives.to_dict()

    def _features(self, state):
        """Признаки мира для понятий (без импорта-цикла на уровне модуля)."""
        try:
            from core.concepts import extract_features
            return extract_features(state, getattr(self.self_model, '__dict__', {}))
        except Exception:
            return {}

    def _snapshot_context(self):
        try:
            return self.adapter.get_state() or {}
        except Exception:
            return {}

    def choose_action(self, state, forbid=None):
        drives_now = self.drives.to_dict()
        candidates = [a for a in ACTION_POOL if self.catalog.has(a)]
        if forbid:
            candidates = [a for a in candidates if a not in forbid]
        # Не повторяем одно и то же в третий раз подряд — иначе существо
        # зацикливается на одном движении.
        recent = self._recent_actions[-2:]
        no_repeat = [a for a in candidates if a not in recent]
        if no_repeat:
            candidates = no_repeat
        if not candidates:
            return 'stay_here'

        # Оценка: предсказанный прирост облегчения + уверенность + любопытство
        feats = self._features(state)
        scored = []
        exploration = self.neuromod.exploration()
        for a in candidates:
            relief = self.predictor.predict_relief(a, drives_now, state)
            conf = self.self_model.confidence(a)
            novelty_bonus = exploration * 0.15 * (1.0 - conf)
            noise = exploration * 0.1 * (0.5 - random.random())
            law_bonus = 0.0
            if self.advisor is not None:
                try:
                    bonus, forbid = self.advisor(feats, a)
                    if forbid:
                        continue
                    law_bonus = bonus
                except Exception:
                    law_bonus = 0.0
            scored.append((a, relief + conf * 0.1 + novelty_bonus + law_bonus + noise))

        scored.sort(key=lambda x: -x[1])
        top_n = min(3, len(scored))
        chosen = random.choice(scored[:top_n])[0]
        self._recent_actions.append(chosen)
        if len(self._recent_actions) > 6:
            self._recent_actions.pop(0)
        return chosen

    def act(self, action, params=None):
        self.last_action = action
        self.pending_action = action
        self.pending_drives_before = self.snapshot_drives()
        self.pending_context = self._snapshot_context()
        self.pending_prediction = self.predictor.simulate(
            action, self.pending_drives_before, self.pending_context)
        self.pending_time = time.time()

        result = self.adapter.action(action, params=params)
        # Исход последнего действия — для обучения понятий о мире.
        if isinstance(result, dict):
            inner = result.get('result') if isinstance(result.get('result'), dict) else result
            self.last_result = {'ok': bool(inner.get('ok', True)),
                                'reason': str(inner.get('reason', '') or '')}
        else:
            self.last_result = None
        return result

    def observe(self):
        """Сравнить ожидание и реальность, обучить предсказание (дофамин)."""
        if not self.pending_action:
            return None
        if time.time() - self.pending_time < 0.4:
            return None

        drives_after = self.drives.to_dict()
        drives_before = self.pending_drives_before
        context = self.pending_context
        action = self.pending_action
        prediction = self.pending_prediction

        # Ошибка предсказания по каждому драйву
        total_pred_error = 0.0
        for i, drive in enumerate(drives_before):
            before = drives_before[drive]
            after = drives_after[drive]
            if before < 0.15:
                continue
            drop = before - after
            relief_amount = min(1.0, drop / max(before, 0.01)) if drop > 0 else 0.0
            self.predictor.observe_relief(
                action, drive, context, relief_amount,
                learning_rate=self.neuromod.learning_rate())
            if prediction is not None and i < len(prediction):
                total_pred_error += abs(float(prediction[i]) - relief_amount)

        # Дофаминовая ошибка: сбылось ли предсказание?
        tension_before = sum(drives_before.values())
        tension_after = sum(drives_after.values())
        delta = tension_before - tension_after
        reward = max(0.0, min(1.0, 0.5 + delta * 2))
        self.neuromod.reward(0.5, reward)

        self.pending_action = None
        self.pending_prediction = None
        return delta
