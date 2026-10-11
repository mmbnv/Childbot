"""
Development — взросление: существо не остаётся одинаковым, оно растёт.

Человек меняется со временем: у младенца одно поведение, у подростка другое.
Развитие здесь идёт по возрасту — не по таймеру, а по ОПЫТУ: сколько существо
прожило шагов, сколько узнало, сколько пережило. Возраст растёт от жизни.

Стадии (как у ребёнка):
  * младенец (0)  — только ощущения и эмоции; рефлексы, привязанность, плач.
  * малыш (1)     — любопытство, лепет-речь, игра рядом, подражание.
  * дошкольник (2)— вопросы «почему», воображение, свои желания, «я сам».
  * школьник (3)  — усидчивость, планы, правила, забота о других.

От стадии зависит:
  * длина фразы (лепет → связная речь);
  * насколько сильны игра, любопытство, самостоятельность;
  * насколько существо терпеливо и планирует.

Возраст не сбрасывается — существо взрослеет на глазах у папы.
"""
import json
import os
import time

from core.temperament import clip


DEVELOPMENT_FILE = "data/development.json"

STAGES = [
    {'name': 'младенец', 'min_age': 0, 'max_age': 600,
     'desc': 'ощущаю, чувствую, тянусь к папе'},
    {'name': 'малыш', 'min_age': 600, 'max_age': 2400,
     'desc': 'любопытный, лепечу, играю рядом, подражаю'},
    {'name': 'дошкольник', 'min_age': 2400, 'max_age': 7200,
     'desc': 'спрашиваю «почему», воображаю, «я сам!»'},
    {'name': 'школьник', 'min_age': 7200, 'max_age': 999999,
     'desc': 'терпеливый, строю планы, забочусь о других'},
]


class Development:
    def __init__(self, file=DEVELOPMENT_FILE):
        self.file = file
        self.age = 0.0             # «прожитые шаги» — опыт, не время
        self.stage = 0
        self.birth = time.time()
        self.learned_total = 0
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.age = d.get('age', 0.0)
            self.birth = d.get('birth', time.time())
            self.learned_total = d.get('learned_total', 0)
            self.stage = self._stage_for(self.age)
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'age': self.age, 'birth': self.birth,
                           'learned_total': self.learned_total},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _stage_for(self, age):
        for i, s in enumerate(STAGES):
            if s['min_age'] <= age < s['max_age']:
                return i
        return len(STAGES) - 1

    def live(self, learned=False, steps=1.0):
        """Прожить ещё немного. Новое знание ускоряет взросление."""
        self.age += steps * (1.6 if learned else 1.0)
        if learned:
            self.learned_total += 1
        new_stage = self._stage_for(self.age)
        if new_stage != self.stage:
            self.stage = new_stage
            print(f"🌱 Вырос: теперь я {self.stage_name()} — {self.stage_desc()}")
        return self.stage

    # ============ ЧТО ДАЁТ ВОЗРАСТ ============

    def stage_name(self):
        return STAGES[self.stage]['name']

    def stage_desc(self):
        return STAGES[self.stage]['desc']

    def speech_stage(self):
        """Уровень речи: 0 лепет, 1 телеграф, 2 фраза, 3 связная."""
        return self.stage

    def playfulness(self):
        """Игра ярче всего в дошкольном возрасте."""
        return {0: 0.3, 1: 0.7, 2: 1.0, 3: 0.6}[self.stage]

    def curiosity(self):
        return {0: 0.5, 1: 0.8, 2: 1.0, 3: 0.7}[self.stage]

    def independence(self):
        """«Я сам!» — растёт с возрастом."""
        return {0: 0.1, 1: 0.3, 2: 0.6, 3: 0.8}[self.stage]

    def patience_bonus(self):
        return {0: 0.0, 1: 0.1, 2: 0.25, 3: 0.4}[self.stage]

    def question_urge(self):
        """Сколько вопросов задаёт (пик в дошкольном)."""
        return {0: 0.1, 1: 0.4, 2: 0.9, 3: 0.5}[self.stage]

    def attention_span(self):
        """Сколько шагов удерживает одно занятие."""
        return {0: 3, 1: 6, 2: 10, 3: 16}[self.stage]

    def summary(self):
        days = (time.time() - self.birth) / 86400.0
        return (f"возраст {self.stage_name()} (опыт {self.age:.0f}, "
                f"дней от рождения {days:.1f}): {self.stage_desc()}")
