"""
Values — ценности и принятие решений: «две системы» и арбитраж между ними.

Человек решает двумя способами, и они постоянно спорят:

  * СИСТЕМА 1 (быстрая). Привычка и наитие: знакомое действие «на автомате».
    Дёшево, быстро, но негибко. Здесь — model-free ценность Q(ситуация,
    действие), выученная по дофаминовой ошибке (как в базальных ганглиях),
    плюс эпизодический контроль: «в похожей ситуации это сработало — сделай так».

  * СИСТЕМА 2 (медленная). Обдумывание: мысленная симуляция последствий
    (imagination), сравнение вариантов, выбор ведущего к цели. Дорого, но
    гибко. Здесь — ценность, посчитанная воображением.

  * АРБИТРАЖ. Что победит: привычка или размышление? Когда привычка уверенна
    и ситуация знакома — она; когда дело новое, важное или привычка подводит —
    в дело вступает обдумывание. Расхождение двух систем рождает «сигнал
    конфликта» (как передняя цингулярная кора): замешательство, пауза, внимание.

  * ОБУЧЕНИЕ ЦЕННОСТЯМ. Успех (дофамин) повышает ценность действия в ситуации;
    неудача — понижает. Так рождаются «привычки характера» — то, что существо
    ценит и делает охотно, а не по приказу.

Ценности — это и есть то, что делает поведение личным: не «что выгодно», а
«что я ценю и к чему стремлюсь».
"""
import json
import os
import time

from core.temperament import clip


VALUES_FILE = "data/values.json"


def context_key(drives, state):
    """Ситуация для ценности: главная нужда + опасность + папа + время суток."""
    dominant = drives.dominant()
    night = 'ночь' if state.get('is_night') else 'день'
    near = (state.get('player') or {}).get('distance', 999) < 12
    danger = bool((state.get('nearest_hostile') or {}).get('distance', 999) < 10)
    return f"{dominant}|{'опасно' if danger else 'спокойно'}|{'с_папой' if near else 'один'}|{night}"


class Values:
    def __init__(self, temperament, file=VALUES_FILE):
        self.temperament = temperament
        self.file = file
        # model-free ценность: Q[context][action] -> ценность (может быть <0)
        self.q = {}
        # эпизодический контроль: «в ситуации X лучше всего сработало Y»
        self.episodic = {}
        self.last_conflict = 0.0
        self.conflicts = 0
        self.learned = 0
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.q = d.get('q', {})
            self.episodic = d.get('episodic', {})
            self.learned = d.get('learned', 0)
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'q': self.q, 'episodic': self.episodic,
                           'learned': self.learned}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============ ЦЕННОСТЬ (model-free) ============

    def value(self, context, action):
        return float(self.q.get(context, {}).get(action, 0.0))

    def best_known(self, context, min_value=0.5):
        """Что, по опыту, ЛУЧШЕ ВСЕГО и достаточно хорошо в этой ситуации.

        Привычка (быстрая система) берётся за дело, только когда ценность
        действительно высока. Иначе «привычкой» становилось бы случайное
        действие, и поведение рассыпалось бы.
        """
        row = self.q.get(context)
        if not row:
            return self.episodic.get(context)
        best = max(row, key=row.get)
        return best if row.get(best, 0.0) >= min_value else None

    def update(self, context, action, reward, lr=0.2):
        """Дофаминовое обучение: подкрепление меняет ценность действия здесь."""
        row = self.q.setdefault(context, {})
        old = float(row.get(action, 0.0))
        row[action] = round(clip(old + lr * (reward - old), -1.0, 1.0), 3)
        if reward > 0.3:
            self.episodic[context] = action
        self.learned += 1
        if self.learned % 5 == 0:
            self.save()

    # ============ АРБИТРАЖ ДВУХ СИСТЕМ ============

    def arbitrate(self, habit_action, deliberate_action, confidence, tension,
                  novel=False, danger=False):
        """
        Решить, что делать: привычку (быстро) или обдуманный выбор (медленно).

        Возвращает (action, source, conflict):
          source — 'habit' | 'deliberate' | 'conflict';
          conflict — насколько системы разошлись (0..1), сигнал замешательства.

        Логика как у человека:
          * привычка берёт верх, когда уверена, ситуация знакома и не опасна;
          * обдумывание берёт верх, когда ново/важно/опасно или привычка слаба;
          * если они РАСХОДЯТСЯ и обе не пусты — возникает конфликт: пауза,
            внимание, иногда лучшее из двух.
        """
        conflict = 0.0
        # Конфликт — это когда ДВЕ РАЗНЫЕ системы предлагают РАЗНОЕ. Если
        # обдумывание не нашло ничего (deliberate пусто), это не конфликт, а
        # просто «привычка знает, а ум — нет».
        if habit_action and deliberate_action and habit_action != deliberate_action:
            conflict = 0.6 + 0.4 * min(1.0, tension / 3.0)
            self.conflicts += 1
            self.last_conflict = time.time()

        # Привычка сильна, если уверена и не в опасности.
        habit_power = confidence * (0.4 + self.temperament.t('conscientiousness') * 0.6)
        if danger or novel:
            habit_power *= 0.4
        deliberate_power = (1.0 - confidence) + min(1.0, tension / 3.0) * 0.5
        if novel or danger:
            deliberate_power += 0.4

        if not habit_action:
            return deliberate_action, 'deliberate', conflict
        if not deliberate_action:
            return habit_action, 'habit', conflict

        if habit_power >= deliberate_power:
            return habit_action, 'habit', conflict
        return deliberate_action, 'deliberate', conflict

    def summary(self):
        return (f"ценности: ситуаций {len(self.q)}, обновлений {self.learned}, "
                f"конфликтов привычки и ума {self.conflicts}")
