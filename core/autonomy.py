"""
Autonomy — спонтанные желания (свободное поведение при низком напряжении).

Когда базовые потребности удовлетворены, существо не «зависает», а играет,
исследует, проявляет любопытство — как ребёнок. Это не хаос: желания
взвешены настроением, любопытством и уверенностью в себе.
"""
import random
import time


class Autonomy:
    def __init__(self):
        self.last_goal_time = 0
        self.goal_cooldown = 5.0
        self.recent_actions = []

    def _pick(self, candidates):
        filtered = [c for c in candidates if c[1] not in self.recent_actions[-3:]]
        if not filtered:
            filtered = candidates
        return random.choice(filtered) if filtered else None

    def generate_goal(self, drives, neuromod, world_state, self_state):
        now = time.time()
        if (now - self.last_goal_time) < self.goal_cooldown:
            return None

        tension = drives.tension()
        if tension > 2.5:
            return None

        d = drives.to_dict()
        mood = neuromod.mood()
        exploration = neuromod.exploration()
        candidates = []

        # любопытство: тяга исследовать
        if d['curiosity'] > 0.5 and random.random() < 0.5 * exploration:
            candidates = [
                ('пойти в новое место', 'step_forward', None),
                ('осмотреть всё вокруг', 'look_around', None),
                ('забраться повыше', 'jump_forward', None),
            ]
        # игра
        elif mood == 'хорошо' and random.random() < 0.3:
            candidates = [
                ('просто поиграть', 'spin_around', None),
                ('попрыгать', 'jump_once', None),
                ('посмотреть вверх', 'look_up', None),
                ('пройтись', 'step_forward', None),
            ]
        # спокойное созерцание
        elif mood == 'спокойно' and random.random() < 0.15:
            candidates = [
                ('осмотреться', 'look_around', None),
                ('пройтись', 'step_forward', None),
            ]
        # скука: надо чем-то заняться
        elif d['boredom'] > 0.6:
            candidates = [
                ('покопать от скуки', 'dig_nearby', None),
                ('побегать', 'sprint_short', None),
            ]

        if not candidates:
            return None

        pick = self._pick(candidates)
        if pick:
            self.recent_actions.append(pick[1])
            if len(self.recent_actions) > 10:
                self.recent_actions.pop(0)
            self.last_goal_time = now
            return pick
        return None
