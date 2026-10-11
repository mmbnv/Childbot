"""
WorkingMemory — рабочая память (аналог префронтальной коры).

Человек удерживает в уме ~7±2 элемента и активно их «прокручивает».
Здесь:
  * слоты с временем жизни (без повторения — забывается);
  * удержание цели;
  * «внутренняя речь» — что я сейчас делаю;
  * ёмкость ограничена, вытесняется самое слабое.
"""
import time


class WorkingMemory:
    CAPACITY = 7

    def __init__(self):
        self.slots = {}          # key -> {'value', 'salience', 'time'}
        self.goal = None         # активная цель
        self.plan_step = None    # текущий шаг плана
        self.self_talk = None    # внутренняя речь
        self.last_decay = time.time()

    def _decay(self):
        now = time.time()
        dt = now - self.last_decay
        self.last_decay = now
        # без повторения след слабеет
        for k in list(self.slots):
            self.slots[k]['salience'] -= 0.05 * dt
            if self.slots[k]['salience'] <= 0:
                del self.slots[k]

    def hold(self, key, value, salience=1.0):
        self._decay()
        self.slots[key] = {'value': value, 'salience': salience, 'time': time.time()}
        self._enforce_capacity()

    def refresh(self, key, salience=1.0):
        if key in self.slots:
            self.slots[key]['salience'] = max(self.slots[key]['salience'], salience)
            self.slots[key]['time'] = time.time()

    def get(self, key, default=None):
        self._decay()
        s = self.slots.get(key)
        return s['value'] if s else default

    def drop(self, key):
        self.slots.pop(key, None)

    def _enforce_capacity(self):
        while len(self.slots) > self.CAPACITY:
            weakest = min(self.slots, key=lambda k: self.slots[k]['salience'])
            del self.slots[weakest]

    def set_goal(self, goal):
        self.goal = goal

    def clear_goal(self):
        self.goal = None
        self.plan_step = None

    def contents(self):
        self._decay()
        return {k: v['value'] for k, v in self.slots.items()}

    def summary(self):
        items = [f"{k}={v['value']}" for k, v in self.slots.items()]
        goal = self.goal or "нет"
        talk = self.self_talk or "—"
        return (f"рабочая память [{len(self.slots)}/{self.CAPACITY}]: "
                f"{', '.join(items) or 'пусто'} | цель: {goal} | внутренняя речь: {talk}")
