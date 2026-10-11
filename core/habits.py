"""
Habits — привычки и автоматизмы.

Человек не решает каждое действие заново: повторяющееся поведение становится
привычкой и выполняется «на автомате» (базальные ганглии). Это экономит силы:
в знакомой ситуации не думаешь, а просто делаешь, как привык.

Но у привычек есть и тёмная сторона — они негибки. Поэтому мозг должен уметь
их замечать и ЛОМАТЬ, когда привычка перестала помогать (переучивание).
Именно так существо перестаёт залипать: привычка «копать дерево» распознаётся
как бесполезная и заменяется новой.

Здесь:
  * привычка = (ситуация → действие), сила растёт с повторами и наградой;
  * в знакомой ситуации привычка подсказывает действие (bonus);
  * если привычка много раз не даёт результата — она забывается (extinction).
"""
import json
import os
import time


HABITS_FILE = "data/habits.json"


class Habit:
    __slots__ = ('cue', 'action', 'strength', 'uses', 'wins', 'losses', 'time')

    def __init__(self, cue, action, strength=0.3):
        self.cue = cue
        self.action = action
        self.strength = strength
        self.uses = 0
        self.wins = 0
        self.losses = 0
        self.time = time.time()

    def to_dict(self):
        return {'cue': self.cue, 'action': self.action,
                'strength': round(self.strength, 3), 'uses': self.uses,
                'wins': self.wins, 'losses': self.losses, 'time': self.time}

    @classmethod
    def from_dict(cls, d):
        h = cls(d['cue'], d['action'], d.get('strength', 0.3))
        h.uses = d.get('uses', 0)
        h.wins = d.get('wins', 0)
        h.losses = d.get('losses', 0)
        h.time = d.get('time', time.time())
        return h


class Habits:
    def __init__(self, file=HABITS_FILE):
        self.file = file
        self.habits = {}      # cue -> Habit
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for d in data:
                h = Habit.from_dict(d)
                self.habits[h.cue] = h
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump([h.to_dict() for h in self.habits.values()],
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # Действия, которые не становятся привычкой: они не меняют мир, и привычка
    # к ним превращается в застывание («стоял и смотрел»).
    IDLE = {'wait_1sec', 'stay_here', 'stop', 'look_around', 'look_up', 'look_down',
            'spin_around', 'sneak'}

    def cue_of(self, drives, state, novelty=False):
        """Ситуация, в которой включается привычка: нужда + обстановка.

        Ключ намеренно простой (только устойчивые признаки: главная потребность,
        день/ночь, папа рядом, спокойно ли). Иначе привычка никогда не включается.
        """
        dominant = drives.dominant()
        night = 'ночь' if state.get('is_night') else 'день'
        player = 'папа_рядом' if (state.get('player') or {}).get('distance', 999) < 12 else 'папа_далеко'
        calm = 'спокойно' if drives.tension() < 1.5 else 'напряжённо'
        return f"{dominant}|{night}|{player}|{calm}"

    def suggest(self, cue):
        """Какое действие подсказывает привычка (или None)."""
        h = self.habits.get(cue)
        if h and h.strength > 0.35:
            return h.action
        return None

    def strengthen(self, cue, action, reward=True):
        """Повтор укрепил привычку; награда ускоряет закрепление."""
        h = self.habits.get(cue)
        if h is None or h.action != action:
            # Смена действия в той же ситуации = переучивание.
            h = Habit(cue, action, strength=0.3)
            self.habits[cue] = h
        h.uses += 1
        if reward:
            h.wins += 1
            h.strength = min(1.0, h.strength + 0.08)
        else:
            h.losses += 1
            h.strength = max(0.0, h.strength - 0.12)
        h.time = time.time()
        self.save()
        return h

    def reward(self, cue, amount=1.0):
        h = self.habits.get(cue)
        if not h:
            return
        h.strength = min(1.0, h.strength + 0.1 * amount)
        h.wins += 1
        self.save()

    def punish(self, cue, amount=1.0):
        """Привычка не сработала — она слабеет (это и ломает залипание)."""
        h = self.habits.get(cue)
        if not h:
            return
        h.strength = max(0.0, h.strength - 0.15 * amount)
        h.losses += 1
        if h.strength <= 0.02:
            self.habits.pop(cue, None)
        self.save()

    def strongest(self, n=3):
        items = sorted(self.habits.values(), key=lambda h: -h.strength)[:n]
        return items

    def summary(self):
        if not self.habits:
            return "привычек пока нет"
        top = self.strongest(3)
        return "привычки: " + ', '.join(
            f"{h.action} ({h.strength:.2f})" for h in top)
