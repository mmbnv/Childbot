"""
Prior — субъективное ожидание мира из ПРОШЛОГО опыта.

Почему так. Companion-работа IBL (Nature 645, 192–200, 2025) показала: у мыши
есть субъективный приор о том, где появится стимул, он КОДИРУЕТСЯ В 20–30%
областей мозга и зависит от ПРОШЛЫХ 5–6 выборов, а не только от последнего.
Это байесовское ожидание: мозг накапливает статистику среды и заранее
склоняется к вероятному исходу, ещё до свидетельств.

Для нашего существа это значит: у него должно быть ОЖИДАНИЕ того, что обычно
происходит в этой ситуации и что обычно срабатывает. Тогда решение начинается
не с нуля, а «с наклоном» — как у живого.

Реализация:
  * leaky-интегратор по категории ситуации (контекст) — недавние исходы весят
    больше давних, но помнятся несколько шагов (окно ≈ 6);
  * prior.predict(context, action) → ожидаемая ценность [−1, 1];
  * prior.observe(context, action, outcome) — обновление после поступка;
  * сохраняется на диск, поэтому ожидания живут между запусками.
"""
import json
import os

PRIOR_FILE = "data/prior.json"


def clip(v, lo=-1.0, hi=1.0):
    return max(lo, min(hi, v))


class Prior:
    # Окно памяти: сколько прошлых исходов держим (IBL: 5–6 выборов).
    WINDOW = 6
    LEAK = 0.25          # скорость забывания давнего
    LR = 0.3             # скорость обучения

    def __init__(self, file=PRIOR_FILE):
        self.file = file
        self.beliefs = {}        # context -> action -> ожидание [-1,1]
        self.history = {}        # context -> список последних исходов
        self.updates = 0
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.beliefs = {k: dict(v) for k, v in d.get('beliefs', {}).items()}
            self.history = {k: list(v) for k, v in d.get('history', {}).items()}
            self.updates = d.get('updates', 0)
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'beliefs': self.beliefs, 'history': self.history,
                           'updates': self.updates}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- ОЖИДАНИЕ ----------

    def predict(self, context, action):
        """Заранее ожидаемая ценность действия в этой ситуации."""
        return float(self.beliefs.get(context, {}).get(action, 0.0))

    def context_prior(self, context):
        """Общий наклон ситуации: что тут обычно хорошо/плохо (знак)."""
        row = self.beliefs.get(context)
        if not row:
            return 0.0
        return clip(sum(row.values()) / max(1, len(row)))

    def surprise(self, context, action, outcome):
        """Насколько исход разошёлся с ожиданием (для любопытства/страха)."""
        return abs(outcome - self.predict(context, action))

    # ---------- ОБУЧЕНИЕ ----------

    def observe(self, context, action, outcome):
        """Запомнить исход. Недавние исходы весят больше (окно ≈ 6)."""
        outcome = clip(outcome)
        row = self.beliefs.setdefault(context, {})
        old = row.get(action, 0.0)
        row[action] = clip(old * (1 - self.LR) + outcome * self.LR)

        h = self.history.setdefault(context, [])
        h.append(round(outcome, 3))
        # Забываем давнее: держим последние WINDOW исходов (IBL: 5–6).
        while len(h) > self.WINDOW:
            h.pop(0)
        self.updates += 1

    # ---------- ОТЧЁТ ----------

    def summary(self):
        return (f"приор: ситуаций {len(self.beliefs)}, обновлений {self.updates}, "
                f"окно {self.WINDOW}")
