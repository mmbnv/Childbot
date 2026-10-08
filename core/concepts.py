"""
Concepts — фундаментальные понятия о мире, которые существо открывает само.

Это не список рецептов Minecraft. Это законы, верные в любой игре и в жизни:

  * gravity    — если нет опоры под ногами, падаю вниз;
  * support    — твёрдое держит меня, сквозь него не провалюсь;
  * solid      — сквозь твёрдое не пройти (стена останавливает);
  * passage    — дверь можно открыть, и она пропускает (зайти в дверь);
  * tool       — без нужного инструмента вещь не добыть;
  * combine    — два вещества вместе дают новое (это и есть химия);
  * heat       — огонь/печь меняет вещество (плавка);
  * danger     — это делает больно;
  * nutrition  — это убирает голод;
  * reachable  — сюда можно дойти.

Каждое понятие — это проверяемая гипотеза: «если так, то будет так».
Существо наблюдает переход (было → стало, что делал) и подтверждает или
опровергает гипотезу. Когда подтверждений достаточно — понятие «известно»
и на него можно опираться в решениях.

Мир описывается набором ПРИЗНАКОВ (features), а не конкретными блоками.
Любая игра-адаптер, который умеет их отдать, получает те же понятия — поэтому
разум универсален.
"""

# Признаки мира (единый язык для любой игры):
#   x, y, z          — положение
#   on_ground        — стою на твёрдом
#   support_below    — подо мной твёрдый блок
#   blocked          — прошлое движение упёрлось в препятствие
#   health, food     — здоровье и сытость
#   inventory_total  — сколько всего предметов
#   near_door        — рядом дверь/проход
#   door_open        — дверь открыта/прошли
#   hostile          — расстояние до врага или None
#   night            — ночь ли


def extract_features(state, self_state):
    """Собрать признаки из того, что отдаёт тело. Всё — с безопасными умолчаниями."""
    state = state or {}
    self_state = self_state or {}
    inv = self_state.get('inventory') or []
    inv_total = 0
    for i in inv:
        try:
            inv_total += int(i.get('count', 0))
        except Exception:
            pass
    pos = self_state.get('pos') or {}
    hostile = state.get('nearest_hostile')
    hd = None
    if hostile:
        hd = hostile.get('distance')
    return {
        'x': float(state.get('x', pos.get('x', 0.0)) or 0.0),
        'y': float(state.get('y', pos.get('y', 0.0)) or 0.0),
        'z': float(state.get('z', pos.get('z', 0.0)) or 0.0),
        'on_ground': bool(state.get('on_ground', state.get('has_sky_above', True))),
        'support_below': bool(state.get('support_below', state.get('on_ground', True))),
        'blocked': bool(state.get('blocked', False)),
        'health': float(state.get('health', self_state.get('health', 20)) or 0.0),
        'food': float(state.get('food', self_state.get('food', 20)) or 0.0),
        'inventory_total': float(inv_total),
        'near_door': bool(state.get('near_door', False)),
        'door_open': bool(state.get('door_open', False)),
        'hostile': (float(hd) if hd is not None else None),
        'night': bool(state.get('is_night', False)),
    }


MOVE_ACTIONS = {
    'step_forward', 'step_back', 'step_left', 'step_right', 'jump_once',
    'jump_forward', 'sprint_short', 'go_to_player', 'walk_away_from_player',
    'come_close_to_player', 'go_to_position', 'find_and_attack',
    'flee_from_hostile', 'attack_hostile', 'escape_pit', 'force_break_out',
    'dig_forward', 'dig_tree',
}


class Law:
    """Проверяемая гипотеза о законе мира."""

    def __init__(self, name, description, when, expect, min_evidence=3):
        self.name = name
        self.description = description
        self._when = when        # (before, action, ok, reason) -> bool
        self._expect = expect    # (before, after, action, ok, reason) -> bool
        self.min_evidence = min_evidence
        self.confirmed = 0
        self.refuted = 0

    def applies(self, before, action, ok, reason):
        try:
            return bool(self._when(before, action, ok, reason))
        except Exception:
            return False

    def check(self, before, after, action, ok, reason):
        # Сигнатура _expect: (before, action, after, ok, reason).
        try:
            return bool(self._expect(before, action, after, ok, reason))
        except Exception:
            return False

    def confidence(self):
        n = self.confirmed + self.refuted
        if n == 0:
            return 0.0
        return (self.confirmed + 1) / (n + 2)      # сглаживание Лапласа

    def known(self):
        return self.confirmed >= self.min_evidence and self.confidence() >= 0.7

    def to_dict(self):
        return {'confirmed': self.confirmed, 'refuted': self.refuted}


# --- ГИПОТЕЗЫ (семена понятий). Проверяются опытом, а не верой. ---

def _l_gravity():
    return Law(
        'gravity', 'если нет опоры под ногами — падаю вниз',
        when=lambda b, a, ok, r: (not b['support_below']) and (not b['on_ground']),
        expect=lambda b, a, aft, ok, r: aft['y'] <= b['y'] + 0.01 or aft['on_ground'],
    )


def _l_support():
    return Law(
        'support', 'твёрдое под ногами держит — сквозь пол не проваливаюсь',
        when=lambda b, a, ok, r: b['support_below'] and b['on_ground'] and a in MOVE_ACTIONS,
        expect=lambda b, a, aft, ok, r: aft['y'] >= b['y'] - 0.6,
    )


def _l_solid():
    return Law(
        'solid', 'сквозь твёрдую стену не пройти — она останавливает',
        when=lambda b, a, ok, r: b['blocked'] and a in MOVE_ACTIONS,
        expect=lambda b, a, aft, ok, r: abs(aft['x'] - b['x']) < 0.75 and abs(aft['z'] - b['z']) < 0.75,
    )


def _l_passage():
    return Law(
        'passage', 'дверь можно открыть, и она пропускает дальше',
        when=lambda b, a, ok, r: a in ('use', 'interact') and b['near_door'],
        expect=lambda b, a, aft, ok, r: ok or aft['door_open'] or abs(aft['x'] - b['x']) > 0.3,
    )


def _l_tool():
    return Law(
        'tool', 'без нужного инструмента вещь не добыть',
        when=lambda b, a, ok, r: a in ('gather', 'dig_nearby', 'dig_forward', 'dig_tree'),
        expect=lambda b, a, aft, ok, r: ok or aft['inventory_total'] > b['inventory_total'],
    )


def _l_combine():
    return Law(
        'combine', 'два вещества вместе дают новое (соединение)',
        when=lambda b, a, ok, r: a in ('craft', 'combine'),
        expect=lambda b, a, aft, ok, r: ok and abs(aft['inventory_total'] - b['inventory_total']) >= 1,
    )


def _l_heat():
    return Law(
        'heat', 'огонь/печь меняет вещество (плавка)',
        when=lambda b, a, ok, r: a == 'smelt',
        expect=lambda b, a, aft, ok, r: ok or aft['inventory_total'] != b['inventory_total'],
    )


def _l_danger():
    # Бой с врагом всегда чем-то кончается: либо мне больно, либо враг уходит.
    # И то и другое подтверждает: «это опасное дело, его нельзя не замечать».
    return Law(
        'danger', 'драка с врагом опасна — либо больно, либо он уходит',
        when=lambda b, a, ok, r: a in ('attack_hostile', 'find_and_attack'),
        expect=lambda b, a, aft, ok, r: aft['health'] < b['health'] or aft['hostile'] is None,
    )


def _l_nutrition():
    return Law(
        'nutrition', 'это убирает голод',
        when=lambda b, a, ok, r: a == 'eat_food',
        expect=lambda b, a, aft, ok, r: ok and aft['food'] >= b['food'],
    )


def _l_reachable():
    return Law(
        'reachable', 'к цели можно дойти — расстояние сокращается',
        when=lambda b, a, ok, r: a in ('go_to_position', 'go_to_player', 'come_close_to_player'),
        expect=lambda b, a, aft, ok, r: (ok and abs(aft['x'] - b['x']) + abs(aft['z'] - b['z']) > 0.1)
        or not ok,
    )


def default_laws():
    return [_l_gravity(), _l_support(), _l_solid(), _l_passage(), _l_tool(),
            _l_combine(), _l_heat(), _l_danger(), _l_nutrition(), _l_reachable()]


class TransitionModel:
    """Общая модель «что делает действие»: средние изменения признаков.

    Это самый нижний слой обучения — без имён и подсказок. Именно из таких
    регулярностей и рождаются понятия.
    """

    def __init__(self):
        self.stats = {}     # action -> {'n', 'ok', 'dy', 'dhealth', 'dfood', 'dinv'}

    def observe(self, before, after, action, ok):
        s = self.stats.setdefault(action, {'n': 0, 'ok': 0, 'dy': 0.0,
                                           'dhealth': 0.0, 'dfood': 0.0, 'dinv': 0.0})
        s['n'] += 1
        if ok:
            s['ok'] += 1
        s['dy'] += after['y'] - before['y']
        s['dhealth'] += after['health'] - before['health']
        s['dfood'] += after['food'] - before['food']
        s['dinv'] += after['inventory_total'] - before['inventory_total']

    def predict(self, action):
        s = self.stats.get(action)
        if not s or s['n'] == 0:
            return None
        n = s['n']
        return {'success': s['ok'] / n, 'dy': s['dy'] / n, 'dhealth': s['dhealth'] / n,
                'dfood': s['dfood'] / n, 'dinv': s['dinv'] / n, 'n': n}

    def summary(self):
        return f"знаю эффект {len(self.stats)} действий"


class ConceptLearner:
    """Набор понятий + общая модель переходов. Учится из каждого действия."""

    def __init__(self, file="data/concepts.json"):
        self.file = file
        self.laws = {law.name: law for law in default_laws()}
        self.transitions = TransitionModel()
        self.observations = 0
        self.load()

    # ---------- ОБУЧЕНИЕ ----------

    def observe(self, before, after, action, result=None):
        """Одно действие: было → стало. Обновляем понятия и модель переходов."""
        if not before or not after or not action:
            return
        ok, reason = self._outcome(result)
        self.observations += 1
        self.transitions.observe(before, after, action, ok)
        for law in self.laws.values():
            if law.applies(before, action, ok, reason):
                if law.check(before, after, action, ok, reason):
                    law.confirmed += 1
                else:
                    law.refuted += 1

    @staticmethod
    def _outcome(result):
        if not isinstance(result, dict):
            return True, ''
        inner = result.get('result') if isinstance(result.get('result'), dict) else result
        ok = bool(inner.get('ok', result.get('ok', True)))
        return ok, str(inner.get('reason', '') or '')

    # ---------- ЗНАНИЕ ----------

    def knows(self, name):
        law = self.laws.get(name)
        return bool(law and law.known())

    def confidence(self, name):
        law = self.laws.get(name)
        return law.confidence() if law else 0.0

    def unknown(self):
        """Понятия, которые ещё плохо подтверждены — что интересно проверить."""
        return [name for name, law in self.laws.items() if not law.known()]

    def expect(self, action):
        return self.transitions.predict(action)

    def advice(self, before, action):
        """Подсказка поведению: опираться на известные законы.

        Возвращает (bonus, forbid) — насколько действие ценно и не запрещено ли.
        """
        bonus, forbid = 0.0, False
        if self.knows('gravity') and not before.get('support_below', True):
            if action in ('dig_down', 'dig_nearby'):
                forbid = True            # копать под собой в воздухе — упаду
            if action in ('place_block', 'step_back'):
                bonus += 0.2             # нащупать опору
        if self.knows('passage') and before.get('near_door') and not before.get('door_open'):
            if action in ('use', 'interact'):
                bonus += 0.5             # зайти в дверь — это проход
        if self.knows('danger') and before.get('hostile') is not None:
            if action in ('flee_from_hostile', 'attack_hostile'):
                bonus += 0.3
        if self.knows('nutrition') and before.get('food', 20) < 8:
            if action == 'eat_food':
                bonus += 0.4
        return bonus, forbid

    # ---------- СОХРАНЕНИЕ ----------

    def load(self):
        import json
        import os
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for name, d in data.get('laws', {}).items():
                if name in self.laws:
                    self.laws[name].confirmed = d.get('confirmed', 0)
                    self.laws[name].refuted = d.get('refuted', 0)
            self.observations = data.get('observations', 0)
        except Exception:
            pass

    def save(self):
        import json
        import os
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({
                    'laws': {n: l.to_dict() for n, l in self.laws.items()},
                    'observations': self.observations,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def summary(self):
        known = [n for n in self.laws if self.knows(n)]
        if not known:
            return f"понятий пока не знаю (наблюдений {self.observations})"
        return (f"понял {len(known)}/{len(self.laws)} законов: "
                + ', '.join(known))

    def explain(self):
        lines = []
        for name, law in self.laws.items():
            mark = '✅' if law.known() else '·'
            lines.append(f"{mark} {name}: {law.description} "
                         f"({law.confirmed}/{law.confirmed + law.refuted})")
        return '\n'.join(lines)
