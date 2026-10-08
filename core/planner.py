"""
Planner — планирование через мысленную симуляцию.

Человек, прежде чем действовать, «проигрывает» варианты в голове и выбирает
лучший. Здесь планировщик:
  1. по потребности (сильному драйву) порождает несколько планов-кандидатов;
  2. прогоняет каждый через предсказательную модель (predictor.rollout);
  3. выбирает план с наименьшим предсказанным напряжением;
  4. если ни один не помогает и нет опоры в памяти — не строит план вовсе.

Это отличается от «жёсткого» if-else: план рождается из опыта существа.
"""


class Plan:
    def __init__(self, steps, why, score=0.0):
        self.steps = steps          # [{'action', 'params', 'why'}, ...]
        self.why = why
        self.score = score

    def actions(self):
        return [s['action'] for s in self.steps]


class Planner:
    def __init__(self, symbolic, knowledge=None):
        self.symbolic = symbolic
        self.knowledge = knowledge
        self.last_plan = None
        self.last_plan_time = 0
        self.plan_cooldown = 12

    # ---------- ГЕНЕРАЦИЯ КАНДИДАТОВ ----------

    def _plan_for_hunger(self, d):
        plans = []
        # охота на известное животное
        for target in ['cow', 'pig', 'chicken', 'sheep', 'rabbit']:
            pos = self.symbolic.where_is(target)
            if pos:
                plans.append(Plan([
                    {'action': 'find_and_attack', 'params': {'target': target},
                     'why': f'добыть еду ({target})'},
                    {'action': 'eat_food', 'params': None, 'why': 'съесть'},
                ], f'охота на {target}'))
                break
        # просто поесть из инвентаря
        plans.append(Plan([
            {'action': 'eat_food', 'params': None, 'why': 'поесть из запасов'},
        ], 'поесть из инвентаря'))
        # поискать еду — пойти к известной воде/деревьям
        if self.symbolic.where_is('water'):
            w = self.symbolic.where_is('water')
            plans.append(Plan([
                {'action': 'go_to_position', 'params': {'x': w['x'], 'y': w['y'], 'z': w['z']},
                 'why': 'идти к воде — там жизнь'},
            ], 'поиск еды у воды'))
        return plans

    def _plan_for_fatigue(self, d):
        plans = []
        bed = self.symbolic.where_is('bed') or self.symbolic.where_is('red_bed')
        if bed:
            plans.append(Plan([
                {'action': 'go_to_position',
                 'params': {'x': bed['x'], 'y': bed['y'], 'z': bed['z']},
                 'why': 'идти к кровати'},
                {'action': 'interact', 'params': {'name': 'bed'}, 'why': 'лечь спать'},
                {'action': 'wait_1sec', 'params': None, 'why': 'отдохнуть'},
            ], 'сон в кровати'))
        else:
            # нет кровати — построить укрытие и отдохнуть
            plans.append(Plan([
                {'action': 'build_shelter', 'params': None, 'why': 'укрытие для сна'},
                {'action': 'wait_1sec', 'params': None, 'why': 'передохнуть'},
            ], 'сон в укрытии'))
        return plans

    def _plan_for_fear(self, d, state):
        plans = []
        if state.get('nearest_hostile'):
            plans.append(Plan([
                {'action': 'flee_from_hostile', 'params': None, 'why': 'убежать от угрозы'},
            ], 'бегство'))
            plans.append(Plan([
                {'action': 'attack_hostile', 'params': None, 'why': 'дать отпор'},
            ], 'бой'))
        # спрятаться от ночи
        if state.get('is_night') and not state.get('has_sky_above', True) is False:
            plans.append(Plan([
                {'action': 'build_shelter', 'params': None, 'why': 'спрятаться на ночь'},
            ], 'укрытие от ночи'))
        if not plans:
            plans.append(Plan([
                {'action': 'go_to_player', 'params': None, 'why': 'быть рядом с папой — там безопасно'},
            ], 'поиск защиты'))
        return plans

    def _plan_for_loneliness(self, d):
        return [Plan([
            {'action': 'go_to_player', 'params': None, 'why': 'быть рядом с папой'},
            {'action': 'look_at_player', 'params': None, 'why': 'посмотреть на него'},
        ], 'поиск близости')]

    def _plan_for_curiosity(self, d):
        plans = []
        # исследовать известное интересное место
        for name in ['water', 'lava', 'chest', 'crafting_table', 'furnace', 'door']:
            pos = self.symbolic.where_is(name)
            if pos:
                plans.append(Plan([
                    {'action': 'go_to_position',
                     'params': {'x': pos['x'], 'y': pos['y'], 'z': pos['z']},
                     'why': f'исследовать {name}'},
                    {'action': 'look_around', 'params': None, 'why': 'осмотреться'},
                ], f'исследование {name}'))
                break
        # просто идти в неизвестное
        plans.append(Plan([
            {'action': 'step_forward', 'params': None, 'why': 'идти в неизвестное'},
            {'action': 'look_around', 'params': None, 'why': 'осмотреться'},
        ], 'исследование'))
        return plans

    def _plan_for_pain(self, d):
        return [Plan([
            {'action': 'eat_food', 'params': None, 'why': 'восстановить силы'},
            {'action': 'flee_from_hostile', 'params': None, 'why': 'уйти от боли'},
        ], 'залечить раны')]

    # ---------- ВЫБОР ПЛАНА ----------

    def make_plan(self, drives, state, predictor=None, threshold=0.45):
        """
        Вернуть лучший план или None. Если predictor дан — планы оцениваются
        мысленной симуляцией, иначе берётся первый осмысленный.
        """
        d = drives.to_dict()
        dominant = drives.dominant()
        candidates = []

        if dominant == 'hunger' and d['hunger'] > threshold:
            candidates = self._plan_for_hunger(d)
        elif dominant == 'fatigue' and d['fatigue'] > threshold:
            candidates = self._plan_for_fatigue(d)
        elif dominant == 'fear' and d['fear'] > threshold:
            candidates = self._plan_for_fear(d, state)
        elif dominant == 'pain' and d['pain'] > threshold:
            candidates = self._plan_for_pain(d)
        elif dominant == 'loneliness' and d['loneliness'] > threshold:
            candidates = self._plan_for_loneliness(d)
        elif dominant == 'curiosity' and d['curiosity'] > threshold:
            candidates = self._plan_for_curiosity(d)

        if not candidates:
            return None

        # Фильтр: план из одного бесполезного действия без опоры в памяти
        if self.knowledge:
            known_failures = set()
            for c in candidates:
                for a in c.actions():
                    known_failures |= set(self.knowledge.get_known_failures(dominant))
            candidates = [c for c in candidates
                          if not all(a in known_failures for a in c.actions())] or candidates

        # Оценка мысленной симуляцией
        if predictor is not None:
            for c in candidates:
                c.score = predictor.rollout(d, state, c.actions())
            candidates.sort(key=lambda c: c.score)

        self.last_plan = candidates[0]
        return self.last_plan

    def should_plan(self, now=None):
        import time
        now = now or time.time()
        if (now - self.last_plan_time) < self.plan_cooldown:
            return False
        self.last_plan_time = now
        return True
