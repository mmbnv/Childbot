"""
Experiment — любопытство как способ узнать мир.

Ребёнок не ждёт, пока ему объяснят. Он пробует сам: «а что будет, если...».
Здесь существо выбирает САМЫЙ неясный закон (понятие с малой уверенностью)
и делает безопасный опыт, чтобы его проверить.

Опыт всегда безопасен: только из белого списка действий, только когда рядом
нет угрозы, нет сильной боли и мы сыты. Это не безрассудство, а научение —
как ребёнок трогает воду, но не лезет в огонь.
"""

# law -> (действие, условие-применимости, как объяснить)
SAFE_PROBES = {
    'support':   ('jump_once', lambda f: f['on_ground'],
                  'прыгнуть и проверить, что приземлюсь'),
    'gravity':   ('jump_forward', lambda f: f['on_ground'],
                  'прыгнуть вперёд и посмотреть, потянет ли вниз'),
    'solid':     ('step_forward', lambda f: True,
                  'шагнуть и проверить, остановит ли стена'),
    'passage':   ('use', lambda f: f['near_door'],
                  'открыть дверь и проверить, пропустит ли'),
    'tool':      ('gather', lambda f: True,
                  'добыть и проверить, нужен ли инструмент'),
    'combine':   ('craft', lambda f: True,
                  'соединить вещества и посмотреть, выйдет ли новое'),
    'heat':      ('smelt', lambda f: True,
                  'нагреть и проверить, изменится ли вещество'),
    'nutrition': ('eat_food', lambda f: f['food'] < 14,
                  'поесть и проверить, уйдёт ли голод'),
    'reachable': ('go_to_position', lambda f: True,
                  'пойти к цели и проверить, можно ли дойти'),
}


class Experimenter:
    def __init__(self, concepts, cooldown=25.0):
        self.concepts = concepts
        self.cooldown = cooldown
        self.last_time = 0.0
        self.running = None      # имя проверяемого закона
        self.history = []

    def _pick_law(self, features):
        """Выбрать самый неясный закон, для которого есть безопасный опыт."""
        unknown = [n for n in self.concepts.unknown() if n in SAFE_PROBES]
        if not unknown:
            return None
        # сначала те, что применимы прямо сейчас, потом самые неясные
        applicable = [n for n in unknown if SAFE_PROBES[n][1](features)]
        pool = applicable or []
        if not pool:
            return None
        pool.sort(key=lambda n: self.concepts.confidence(n))
        return pool[0]

    def maybe_probe(self, features, now):
        """Вернуть (action, params, law_name, why) или None."""
        if (now - self.last_time) < self.cooldown:
            return None
        law = self._pick_law(features)
        if not law:
            return None
        action, _cond, why = SAFE_PROBES[law]
        self.last_time = now
        self.running = law
        return action, self._params(law, features), law, why

    def _params(self, law, features):
        if law == 'reachable':
            return {'x': features['x'] + 3, 'y': features['y'], 'z': features['z']}
        if law in ('combine', 'heat', 'tool', 'gravity', 'solid', 'support'):
            return None
        return None

    def observe(self, law_name, confirmed):
        """Записать результат опыта, чтобы не повторять одно и то же."""
        if law_name:
            self.history.append({'law': law_name, 'confirmed': bool(confirmed)})
            if len(self.history) > 50:
                self.history.pop(0)
        self.running = None

    def summary(self):
        if not self.history:
            return "опытов ещё не ставил"
        ok = sum(1 for h in self.history if h['confirmed'])
        return f"поставил {len(self.history)} опытов (подтвердилось {ok})"
