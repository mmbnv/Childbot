"""
Temperament — характер, с которым существо рождается.

У человека нет «нулевых настроек»: один ребёнок пугливый, другой безрассудно
смелый; один усидчивый, другой непоседа. Это темперамент — биологическая
основа личности. Он не выбирается и не переучивается, но проявляется во всём:

  * как быстро возникает эмоция (реактивность);
  * какой у неё базовый уровень (дофамин, серотонин, кортизол...);
  * насколько сильно тянет к новому (поиск новизны);
  * как быстро устаёт и как долго терпит;
  * как крепко привязывается к папе.

Здесь темперамент — пять базовых черт (как «Большая пятёрка» у человека),
из которых выводятся коэффициенты для всех систем мозга. Характер рождается
случайно при первом запуске и сохраняется — существо остаётся собой.
"""
import json
import os
import random


TEMPERAMENT_FILE = "data/temperament.json"


def clip(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


# Черты «Большой пятёрки» (0..1), по-русски и с человеческим смыслом.
TRAITS = {
    'openness':          'открытость новому',
    'conscientiousness': 'усидчивость',
    'extraversion':      'общительность',
    'agreeableness':     'доброжелательность',
    'neuroticism':       'впечатлительность',
}


class Temperament:
    def __init__(self, file=TEMPERAMENT_FILE):
        self.file = file
        self.traits = {}
        self.load()
        if not self.traits:
            self._birth()

    def _birth(self):
        """Родиться со своим характером: черты слегка смещены от середины."""
        for t in TRAITS:
            self.traits[t] = round(clip(0.5 + random.uniform(-0.22, 0.22)), 3)
        self.save()
        print(f"🧬 Родился с характером: {self.summary()}")

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.traits = d.get('traits', {})
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'traits': self.traits}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def t(self, name, default=0.5):
        return self.traits.get(name, default)

    # ---------- ПРОИЗВОДНЫЕ: как характер красит работу мозга ----------

    def reactivity(self):
        """Как сильно вспыхивает эмоция (впечатлительность)."""
        return 0.6 + self.t('neuroticism') * 0.9

    def recovery(self):
        """Как быстро эмоция утихает (уравновешенность)."""
        return clip(0.55 + (1.0 - self.t('neuroticism')) * 0.4, 0.3, 1.0)

    def baseline(self, mod):
        """Базовый уровень нейромодулятора у этого характера."""
        base = {
            'dopamine': 0.5,
            'serotonin': 0.5 + self.t('agreeableness') * 0.2,
            'noradrenaline': 0.2 + self.t('neuroticism') * 0.3
            + self.t('extraversion') * 0.1,
            'acetylcholine': 0.4 + self.t('openness') * 0.3,
            'cortisol': 0.12 + self.t('neuroticism') * 0.3,
            'oxytocin': 0.2 + self.t('agreeableness') * 0.3
            + self.t('extraversion') * 0.15,
            'endorphins': 0.3,
        }
        return clip(base.get(mod, 0.5))

    def novelty_seeking(self):
        """Тяга к новому: открытость + экстраверсия — впечатлительность."""
        return clip(0.3 + self.t('openness') * 0.6 + self.t('extraversion') * 0.3
                    - self.t('neuroticism') * 0.4, 0.1, 1.0)

    def persistence(self):
        """Насколько доводит дело до конца (усидчивость)."""
        return clip(0.3 + self.t('conscientiousness') * 0.7, 0.1, 1.0)

    def patience(self):
        """Терпение: не бросать при первой неудаче."""
        return clip(0.3 + self.t('conscientiousness') * 0.5
                    + (1.0 - self.t('neuroticism')) * 0.3, 0.1, 1.0)

    def fatigue_rate(self):
        """Как быстро устаёт."""
        return 0.85 + self.t('neuroticism') * 0.4 - self.t('extraversion') * 0.2

    def attach_rate(self):
        """Как быстро привязывается к папе."""
        return clip(0.5 + self.t('agreeableness') * 0.6
                    + self.t('extraversion') * 0.3, 0.2, 1.2)

    def sociability(self):
        """Насколько тянется к общению и игре с папой."""
        return clip(0.3 + self.t('extraversion') * 0.6
                    + self.t('agreeableness') * 0.3, 0.1, 1.0)

    def speech_urge(self):
        """Охота говорить (болтливость)."""
        return clip(0.3 + self.t('extraversion') * 0.7, 0.1, 1.0)

    def summary(self):
        return ', '.join(f"{TRAITS[k]} {v:.2f}" for k, v in self.traits.items())
