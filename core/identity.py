"""
Identity — «Я»: связная история о себе, которая делает поведение постоянным.

Личность — это не набор черт, а ИСТОРИЯ, которую существо о себе рассказывает,
и ЦЕННОСТИ, которым оно остаётся верно. Человек поступает сообразно тому, кем
себя считает: «я тот, кто заботится о папе», «я любопытный», «я не сдаюсь».
Из этого рождается постоянство характера — иначе поведение рассыпается на
случайные реакции (робот).

Здесь:
  * КОРЕНОВЫЕ ЦЕННОСТИ. Из характера и прожитого складываются главные ценности
    («быть рядом с папой», «узнавать новое», «быть полезным», «не сдаваться»).
    Они задают вес целям — существо стремится к тому, что для него важно.

  * ИСТОРИЯ О СЕБЕ. Связный рассказ: кто я, кто мой папа, что я пережил, что
    понял. Не список событий, а осмысленный нарратив (как у человека).

  * СОГЛАСОВАННОСТЬ С СОБОЙ. Существо замечает, когда поступает против того,
    кем себя считает, — и это неприятно (когнитивный диссонанс). Так характер
    удерживается сам, без внешних правил.

  * НАМЕРЕНИЯ. Долгие намерения («хочу научиться строить»), которые живут
    поверх сиюминутных нужд и придают жизни направление.
"""
import json
import os
import time

from core.temperament import clip


IDENTITY_FILE = "data/identity.json"

# Корневые ценности: имя -> как звучит и как проверяется по поведению.
CORE_VALUES = {
    'связь': 'быть рядом с папой и радовать его',
    'познание': 'узнавать новое и понимать мир',
    'польза': 'быть полезным и помогать',
    'стойкость': 'не сдаваться и доводить дело до конца',
    'игра': 'играть и радоваться',
    'безопасность': 'беречь себя и не лезть в беду',
}


class Identity:
    def __init__(self, temperament, file=IDENTITY_FILE):
        self.temperament = temperament
        self.file = file
        self.values = {}          # имя -> сила (0..1)
        self.narrative = []       # ['кто я', ...] связная история
        self.intentions = []      # долгие намерения: {'what','why','since','done'}
        self.dissonance = 0.0
        self.last_norm_break = 0.0
        self.load()
        if not self.values:
            self._form_values()

    def _form_values(self):
        """Сформировать главные ценности из характера (как растёт личность)."""
        self.values = {
            'связь': round(clip(0.4 + self.temperament.t('agreeableness') * 0.5
                                + self.temperament.t('extraversion') * 0.2), 3),
            'познание': round(clip(0.4 + self.temperament.t('openness') * 0.6), 3),
            'польза': round(clip(0.35 + self.temperament.t('agreeableness') * 0.6), 3),
            'стойкость': round(clip(0.35 + self.temperament.t('conscientiousness') * 0.6), 3),
            'игра': round(clip(0.35 + self.temperament.t('extraversion') * 0.4
                               + self.temperament.t('openness') * 0.3), 3),
            'безопасность': round(clip(0.4 + self.temperament.t('neuroticism') * 0.5), 3),
        }
        self.narrative.append({'text': 'я — ребёнок, который учится жить и любит папу',
                               'time': time.time()})
        self.save()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.values = d.get('values', {})
            self.narrative = d.get('narrative', [])[-40:]
            self.intentions = d.get('intentions', [])
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'values': self.values, 'narrative': self.narrative[-40:],
                           'intentions': self.intentions}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============ ЦЕННОСТИ ============

    def value_weight(self, name):
        return self.values.get(name, 0.3)

    def strongest(self, n=2):
        return sorted(self.values.items(), key=lambda kv: -kv[1])[:n]

    def grow_value(self, name, amount=0.03):
        """Прожитое усиливает ценность (например, часто играл — полюбил игру)."""
        if name in self.values:
            self.values[name] = round(clip(self.values[name] + amount), 3)

    # ============ ИСТОРИЯ О СЕБЕ ============

    def add_to_story(self, text):
        if self.narrative and self.narrative[-1]['text'] == text:
            return
        self.narrative.append({'text': text, 'time': time.time()})
        if len(self.narrative) > 40:
            self.narrative.pop(0)
        self.save()

    def story(self, n=4):
        return ' → '.join(e['text'] for e in self.narrative[-n:])

    def who_am_i(self):
        strong = ', '.join(f"{k} ({v:.1f})" for k, v in self.strongest(3))
        return f"я тот, для кого важнее всего: {strong}"

    # ============ СОГЛАСОВАННОСТЬ С СОБОЙ ============

    def check_consistency(self, action, drives):
        """
        Не поступил ли я против того, кем себя считаю?

        Возвращает силу диссонанса (0..1). Например, «стойкость» высока, а я
        бросил дело; «связь» высока, а я убегаю от папы. Это рождает
        неприятное чувство — совесть.
        """
        d = drives.to_dict()
        clash = 0.0
        # Бросил дело при высокой стойкости.
        if action in ('wait_1sec', 'stay_here', 'stop') and self.value_weight('стойкость') > 0.6:
            clash = max(clash, 0.5)
        # Убегаю от папы при высокой связи.
        if action == 'walk_away_from_player' and self.value_weight('связь') > 0.6:
            clash = max(clash, 0.5)
        # Лезть в опасность при высокой ценности безопасности.
        if action in ('attack_hostile', 'attack_nearest') and self.value_weight('безопасность') > 0.7:
            clash = max(clash, 0.4)
        self.dissonance = clip(clash)
        if clash > 0:
            self.last_norm_break = time.time()
        return clash

    def soothe(self):
        """Помириться с собой: осознал и обещаю иначе (снижает диссонанс)."""
        self.dissonance = clip(self.dissonance - 0.4)
        return self.dissonance

    # ============ НАМЕРЕНИЯ ============

    def intend(self, what, why='', horizon=600):
        for it in self.intentions:
            if it['what'] == what and not it['done']:
                return it
        it = {'what': what, 'why': why, 'since': time.time(),
              'horizon': horizon, 'done': False}
        self.intentions.append(it)
        self.intentions = self.intentions[-6:]
        self.save()
        return it

    def fulfil(self, what):
        for it in self.intentions:
            if it['what'] == what and not it['done']:
                it['done'] = True
        self.save()

    def active_intentions(self):
        now = time.time()
        return [it for it in self.intentions
                if not it['done'] and (now - it['since']) < it.get('horizon', 600)]

    def summary(self):
        strong = ', '.join(f"{k} {v:.1f}" for k, v in self.strongest(3))
        return (f"«Я»: {strong}; намерений {len(self.active_intentions())}, "
                f"диссонанс {self.dissonance:.2f}")
