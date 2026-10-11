"""
Causality — причины и следствия: почему не вышло и что с этим делать.

Ребёнок не просто терпит неудачу — он спрашивает «почему?». Здесь живёт
причинно-следственный разум:

  * НАБЛЮДЕНИЕ. Каждое неудавшееся действие разбирается на ПРИЧИНУ
    («не дотянулся», «нужен инструмент», «стена», «нет опоры», «заперто»,
    «нет материала», «не нашёл», «нужна печь/топливо», «далеко»...).
  * ПАМЯТЬ. Причина запоминается: сколько раз встречалась, помогло ли
    средство. Так рождается убеждение «в этом мире блок не бьётся без кирки».
  * РАЗМЫШЛЕНИЕ. Из причины выводится средство (что нужно) и план попыток
    (подойти ближе, обойти, взять инструмент, поставить опору, открыть...).
  * ПРОВЕРКА. Средство пробуется; если помогло — убеждение помечается
    исправленным, и в следующий раз существо действует сразу правильно.

Всё опирается на ПРИЗНАКИ мира и СМЫСЛ причины, а не на конкретные блоки
Minecraft, поэтому работает в любой игре. Причина — это не имя, а связь:
«действие не удалось, потому что X; чтобы вышло, нужно Y».
"""


# Причина -> как её понимать и чем лечить.
#   need   — чего не хватает (человеческое имя)
#   action — действие-средство
#   key    — устойчивый признак причины
CAUSE_BY_REASON = {
    'no_materials':     ('materials', 'нет нужных материалов'),
    'missing_material': ('materials', 'не хватает материала'),
    'no_recipe':        ('recipe_unknown', 'не знаю, как это сделать'),
    'no_crafting_table': ('no_table', 'нужен верстак'),
    'no_table':         ('no_table', 'нужен верстак'),
    'no_tool':          ('tool', 'нужен инструмент'),
    'need_tool':        ('tool', 'нужен инструмент'),
    'wrong_tool':       ('tool', 'нужен другой инструмент'),
    'tool_required':    ('tool', 'нужен инструмент'),
    'not_found':        ('not_found', 'здесь этого нет'),
    'nothing_new':      ('not_found', 'здесь больше нечего взять'),
    'target_not_found': ('not_found', 'не вижу цели'),
    'out_of_reach':     ('reach', 'не дотягиваюсь'),
    'cannot_reach':     ('reach', 'не могу дойти'),
    'cannot_reach_target': ('reach', 'не могу дойти до цели'),
    'no_surface':       ('reach', 'не на что поставить'),
    'cannot_place_furnace': ('reach', 'некуда поставить печь'),
    'locked':           ('locked', 'заперто'),
    'no_fuel':          ('fuel', 'нет топлива'),
    'no_input':         ('input', 'нет сырья для плавки'),
    'no_food_to_sprint': ('tired', 'слишком голоден, чтобы бежать'),
    'bot_not_spawned':  ('body', 'тело ещё не готово'),
    'timeout':          ('path', 'путь не находится'),
    # причины, которые шлёт настоящее тело (bot.js)
    'cannot_reach_tree': ('reach', 'не могу дойти до дерева'),
    'animal_not_found': ('not_found', 'зверя здесь нет'),
    'no_recipe_or_materials': ('materials', 'нет материалов или рецепта'),
    'unknown_item':     ('recipe_unknown', 'не знаю такой вещи'),
    'nothing_to_dig':   ('not_found', 'здесь нечего копать'),
    'no_diggable_block': ('not_found', 'нет блока, который можно сломать'),
    'no_block_in_hand': ('materials', 'в руке нет блока'),
    'held_item_not_block': ('materials', 'в руке не блок'),
    'no_player':        ('no_target', 'не вижу папу'),
    'no_target':        ('no_target', 'рядом нет цели'),
    'block_gone':       ('not_found', 'блок уже исчез'),
    'no_progress':      ('no_progress', 'говорят «готово», а вещь не появилась'),
}

# Средство по умолчанию для каждой причины: (что нужно, действие, ключ-признак)
DEFAULT_FIX = {
    'materials':      (None, 'gather', None),
    'recipe_unknown': (None, 'look_around', None),
    'no_table':       ('верстак', 'craft', {'name': 'crafting_table'}),
    'tool':           (None, 'craft', None),
    'not_found':      (None, 'look_around', None),
    'reach':          (None, 'go_to_position', None),
    'locked':         ('ключ', 'use', None),
    'fuel':           ('топливо', 'gather', {'name': 'coal'}),
    'input':          (None, 'gather', None),
    'tired':          ('еда', 'eat_food', None),
    'body':           (None, 'wait_1sec', None),
    'path':           (None, 'look_around', None),
    'no_support':     ('опора', 'place_block', None),
    'solid':          ('проход', 'dig_forward', None),
    'no_target':      (None, 'look_around', None),
    'no_progress':    (None, 'look_around', None),
    'unknown':        (None, 'look_around', None),
}

# Действия, которые двигают тело (для причин «стена» и «далеко»).
MOVE_ACTIONS = {
    'step_forward', 'step_back', 'step_left', 'step_right', 'jump_forward',
    'sprint_short', 'go_to_player', 'come_close_to_player', 'go_to_position',
    'walk_away_from_player', 'find_and_attack',
}

# Насколько близко нужно быть, чтобы дотянуться до блока.
REACH_LIMIT = 3.0


def _dist(a, b):
    try:
        return ((a.get('x', 0) - b.get('x', 0)) ** 2
                + (a.get('y', 0) - b.get('y', 0)) ** 2
                + (a.get('z', 0) - b.get('z', 0)) ** 2) ** 0.5
    except Exception:
        return 0.0


def _same_params(a, b):
    """Совпадают ли параметры (мягко: None и отсутствие — одно и то же)."""
    a = a or {}
    b = b or {}
    keys = {k for k in list(a) + list(b) if a.get(k) is not None or b.get(k) is not None}
    if not keys:
        return True
    for k in keys:
        if a.get(k) != b.get(k):
            return False
    return True


class Cause:
    """Разобранная причина неудачи и средство против неё."""

    def __init__(self, key, text, need=None, action=None, params=None,
                 plan=None, evidence=None):
        self.key = key
        self.text = text
        self.need = need
        self.action = action
        self.params = params
        self.plan = plan or []          # [(action, params), ...] — как попробовать
        self.evidence = evidence or {}  # признаки/причина тела на момент разбора

    def to_dict(self):
        return {'key': self.key, 'text': self.text, 'need': self.need,
                'action': self.action, 'params': self.params}


class Reasoner:
    """Причинно-следственная память и размышление."""

    def __init__(self, file="data/causes.json", recipes=None):
        self.file = file
        self.recipes = recipes
        self.beliefs = {}       # key -> {'count','fixed','text','need','action','params'}
        self.recent = []        # последние разобранные причины (для размышления)
        self.total = 0
        self.last_reflection = 0.0
        self.reflection_interval = 40.0
        self.load()

    # ---------- РАЗБОР: ПОЧЕМУ НЕ ВЫШЛО ----------

    def explain(self, action, params, ok, reason, before=None, after=None):
        """Разобрать исход действия. Если не вышло — вернуть Cause, иначе None."""
        if ok:
            self.note_success(action, params)
            return None
        cause = self._classify(action, params, reason, before)
        self._remember(cause)
        return cause

    def diagnose(self, action, params, reason, before=None):
        """Разобрать причину БЕЗ записи в память (для пробных попыток)."""
        return self._classify(action, params, reason, before)

    def _classify(self, action, params, reason, before):
        before = before or {}
        params = params or {}
        reason = (reason or '').lower()

        # 1. Прямой смысл причины от тела.
        key, text = CAUSE_BY_REASON.get(reason, (None, None))

        # 2. Если тело не сказало — вывести из действия и признаков мира.
        if key is None:
            key, text = self._infer(action, params, before)

        need, fix_action, fix_params = DEFAULT_FIX.get(key, (None, 'look_around', None))
        # 3. Уточнить средство по рецептам: чего именно не хватает.
        need, fix_action, fix_params = self._refine(
            key, action, params, before, need, fix_action, fix_params)

        evidence = {'reason': reason, 'blocked': before.get('blocked'),
                    'support_below': before.get('support_below'),
                    'reach': before.get('reach'), 'on_ground': before.get('on_ground')}
        return Cause(key, text or reason or 'не вышло', need, fix_action, fix_params,
                     plan=self._plan(key, action, params, before, need, fix_action,
                                     fix_params),
                     evidence=evidence)

    def _infer(self, action, params, before):
        """Вывести причину из самого действия и состояния мира."""
        # Стена: пробовал идти, но упёрся.
        if action in MOVE_ACTIONS and (before.get('blocked') or before.get('solid_ahead')):
            return 'solid', 'стена не пускает'
        # Нет опоры: копаю/строю там, где под ногами пусто.
        if action in ('dig_down', 'dig_nearby', 'place_block', 'build_shelter',
                      'dig_up') and not before.get('support_below', True):
            return 'no_support', 'под ногами нет опоры'
        # Гравитация: прыгаю, но не на земле.
        if action in ('jump_once', 'jump_forward') and not before.get('on_ground', True):
            return 'no_support', 'я в воздухе, не оттолкнуться'
        # Далеко: цель задана координатами, а я не рядом.
        if params and any(k in params for k in ('x', 'z')) and action in MOVE_ACTIONS:
            if _dist(before, params) > REACH_LIMIT * 3:
                return 'reach', 'цель слишком далеко'
        # Атака без цели.
        if action in ('attack_hostile', 'attack_nearest', 'find_and_attack') \
                and before.get('hostile') is None:
            return 'no_target', 'рядом никого нет'
        return 'unknown', 'пока не понял почему'

    def _refine(self, key, action, params, before, need, fix_action, fix_params):
        """Уточнить «чего не хватает» по рецептам — конкретный предмет/инструмент."""
        name = params.get('name') if isinstance(params, dict) else None
        r = self.recipes

        if key == 'tool' and r and name:
            tool = self._tool_for(name)
            if tool:
                return tool, 'craft', {'name': tool}
        if key == 'materials' and r and name:
            missing = self._missing_ingredient(name, before)
            if missing:
                if r.is_craft(missing):
                    return missing, 'craft', {'name': missing}
                # Если нужно дерево, а его нет — искать ЛЮБОЕ дерево, а не
                # только дуб: материалы одного рода взаимозаменяемы.
                from core.recipes import material_family
                fam = material_family(missing)
                if fam:
                    src = None
                    for cand in r.sources(missing) or []:
                        if material_family(cand) == fam:
                            src = cand
                            break
                    return missing, 'gather', {'name': src or missing}
                return missing, 'gather', {'name': missing}
        if key == 'no_progress' and r and name:
            # «Говорят готово, а вещи нет»: скорее всего рядом нечего взять.
            # Идём искать это в мире, а не повторяем вслепую. Для дерева
            # просим ЛЮБОЕ дерево ('log'), иначе тело снова не найдёт дуб.
            from core.recipes import material_family
            src = (r.sources(name) or [name])[0]
            fam = material_family(name)
            if fam and fam in (r.sources(name) or []):
                src = fam
            return need, 'gather', {'name': src}
        if key == 'input' and r and name:
            rec = r.get(name) or {}
            for ing in rec.get('need', {}):
                return ing, 'gather', {'name': ing}
        if key == 'reach' and params and 'x' in params:
            return need, 'go_to_position', {'x': params.get('x'),
                                            'y': params.get('y', before.get('y', 0)),
                                            'z': params.get('z')}
        return need, fix_action, fix_params

    def _tool_for(self, item):
        """Каким инструментом добывается предмет (из рецептов)."""
        r = self.recipes
        if not r:
            return None
        rec = r.get(item) or {}
        for ing in rec.get('need', {}):
            if 'pickaxe' in ing or 'axe' in ing or 'sword' in ing or 'shovel' in ing:
                return ing
        return None

    def _missing_ingredient(self, item, before):
        r = self.recipes
        if not r:
            return None
        from core.recipes import count_in
        rec = r.get(item) or {}
        inv = before.get('_inventory', [])
        for ing, cnt in rec.get('need', {}).items():
            if count_in(inv, ing) < cnt:
                return ing
        return None

    def _plan(self, key, action, params, before, need, fix_action, fix_params):
        """Цепочка попыток: как решить проблему, от простого к сложному."""
        plan = []
        if fix_action:
            plan.append((fix_action, fix_params))
        # Обходные пути — «множество вариантов для проверок», как просил папа.
        if key == 'reach':
            plan.append(('step_forward', None))          # подойти ближе
            plan.append(('jump_forward', None))          # прыгнуть вверх/вперёд
            plan.append(('place_block', None))           # подняться на блок
            plan.append(('look_around', None))           # найти другой путь
        elif key == 'solid':
            plan.append(('dig_forward', None))           # пробить стену
            plan.append(('step_left', None))             # обойти слева
            plan.append(('step_right', None))            # обойти справа
            plan.append(('jump_forward', None))          # перепрыгнуть
        elif key == 'no_support':
            plan.append(('place_block', None))           # создать опору
            plan.append(('step_back', None))             # отойти от края
        elif key == 'tool':
            plan.append(('gather', {'name': 'log'}))     # собрать ЛЮБОЕ дерево
            plan.append(('craft', {'name': need} if need else None))
        elif key == 'materials':
            if need:
                plan.append(('gather', {'name': need}))
        elif key == 'no_table':
            plan.append(('craft', {'name': 'crafting_table'}))
            plan.append(('place_table', None))
        elif key == 'locked':
            plan.append(('gather', None))                # поискать ключ
            plan.append(('combine', None))               # соединить с замком
            plan.append(('look_around', None))
        elif key == 'not_found':
            plan.append(('look_around', None))
            plan.append(('step_forward', None))
        elif key == 'no_progress':
            plan.append(('gather', fix_params))       # искать ЛЮБОЕ дерево
            plan.append(('step_forward', None))       # уйти и поискать дальше
            plan.append(('look_around', None))
        elif key == 'path':
            plan.append(('step_forward', None))
            plan.append(('jump_forward', None))
        elif key == 'fuel':
            plan.append(('gather', {'name': 'coal'}))
        # убрать дубликаты, сохранив порядок
        seen, uniq = set(), []
        for a, p in plan:
            sig = (a, tuple(sorted((p or {}).items())))
            if sig not in seen:
                seen.add(sig)
                uniq.append((a, p))
        return uniq

    # ---------- ПАМЯТЬ О ПРИЧИНАХ ----------

    def _remember(self, cause):
        self.total += 1
        b = self.beliefs.setdefault(cause.key, {
            'count': 0, 'fixed': 0, 'text': cause.text,
            'need': cause.need, 'action': cause.action, 'params': cause.params})
        b['count'] += 1
        b['text'] = cause.text
        if cause.need:
            b['need'] = cause.need
        if cause.action:
            b['action'] = cause.action
            b['params'] = cause.params
        self.recent.append(cause)
        if len(self.recent) > 40:
            self.recent.pop(0)

    def note_success(self, action, params):
        """Действие удалось — если это было средство против причины, отметить."""
        for key, b in self.beliefs.items():
            if b.get('action') == action and _same_params(b.get('params'), params):
                b['fixed'] = b.get('fixed', 0) + 1

    def note_fix(self, cause):
        """Средство против ЭТОЙ причины помогло — значит, я её решил."""
        if not cause:
            return
        b = self.beliefs.get(cause.key)
        if b:
            b['fixed'] = b.get('fixed', 0) + 1

    # ---------- ПОДСКАЗКА ПОВЕДЕНИЮ ----------

    def advice(self, before, action, params=None):
        """Опираться на причины: поднять ценность средства, запретить вредное."""
        bonus, forbid = 0.0, False
        # Нет опоры — нельзя копать вниз (упаду). Это следствие причины.
        if not before.get('support_below', True) and action in ('dig_down', 'dig_nearby'):
            forbid = True
        # Стена впереди — не биться в неё лбом.
        if before.get('solid_ahead') and action in ('step_forward', 'go_to_player',
                                                    'come_close_to_player'):
            forbid = True
        # Известное незалеченное убеждение — подсказать средство.
        for key, b in self.beliefs.items():
            if b.get('fixed', 0) > 0:
                continue
            if b.get('count', 0) < 2:
                continue
            if b.get('action') == action and _same_params(b.get('params'), params):
                bonus += 0.45
            # «Не дотягиваюсь» — подойти ближе ценно.
            if key == 'reach' and action in ('step_forward', 'go_to_position',
                                             'come_close_to_player'):
                bonus += 0.3
            # «Заперто» — искать ключ/соединять ценно.
            if key == 'locked' and action in ('gather', 'combine', 'use'):
                bonus += 0.35
        return bonus, forbid

    # ---------- РАЗМЫШЛЕНИЕ ----------

    def reflect(self, features=None, now=0.0):
        """Мысль вслух о причине и о том, как её решить. Не чаще интервала."""
        if (now - self.last_reflection) < self.reflection_interval:
            return None
        top = self.top_belief()
        if not top:
            return None
        self.last_reflection = now
        key, b = top
        why = b.get('text', 'не вышло')
        if b.get('fixed', 0) > 0:
            return f"раньше было «{why}» — я уже научился это обходить"
        need = b.get('need')
        if need:
            return f"не выходит: {why}. Нужно: {need}. Попробую по-другому"
        return f"не выходит: {why}. Придумаю, как иначе"

    def top_belief(self):
        """Самое частое незалеченное убеждение — о чём стоит подумать."""
        items = [(k, b) for k, b in self.beliefs.items()
                 if b.get('fixed', 0) == 0 and b.get('count', 0) >= 2]
        if not items:
            return None
        items.sort(key=lambda kv: -kv[1]['count'])
        return items[0]

    # ---------- СОХРАНЕНИЕ ----------

    def load(self):
        import json
        import os
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.beliefs = data.get('beliefs', {})
            self.total = data.get('total', 0)
        except Exception:
            pass

    def save(self):
        import json
        import os
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'beliefs': self.beliefs, 'total': self.total},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def summary(self):
        if not self.beliefs:
            return "причин пока не знаю"
        fixed = sum(1 for b in self.beliefs.values() if b.get('fixed', 0) > 0)
        return (f"знаю {len(self.beliefs)} причин неудач "
                f"(решено {fixed}), всего разборов {self.total}")

    def explain_all(self):
        lines = []
        for k, b in sorted(self.beliefs.items(), key=lambda kv: -kv[1].get('count', 0)):
            mark = '✅' if b.get('fixed', 0) > 0 else '·'
            need = f" → нужно: {b['need']}" if b.get('need') else ""
            lines.append(f"{mark} {b.get('text', k)} "
                         f"({b.get('count', 0)}×, решено {b.get('fixed', 0)}){need}")
        return '\n'.join(lines)
