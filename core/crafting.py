"""
CraftingSkill — умение доводить вещь до готовности шаг за шагом.

Это «руки» существа в ремесле. Оно не выполняет жёсткий список, а каждый раз
смотрит на инвентарь и спрашивает: «чего мне не хватает прямо сейчас?» —
и делает ровно один шаг к цели (добыть / поставить верстак / скрафтить).
После каждого шага пересчитывает заново, поэтому работает и с настоящими
выходами крафта (1 бревно → 4 доски), и с нехваткой инструмента.

Так ребёнок и учится: не «сделай кирку», а «сначала палки, потом камень,
потом кирка» — по одной ступени.
"""
import time


class CraftingSkill:
    def __init__(self, recipes, curriculum, act, max_depth=12, task_failure_cb=None):
        # act(action, params) — моторный выход. В мозге это cortex.act, чтобы
        # каждое ремесленное действие тоже обучало предсказание.
        self.act = act
        self.recipes = recipes
        self.curriculum = curriculum
        self.max_depth = max_depth
        # Если не осилили задачу игры — сообщить об этом трекеру задач.
        self.task_failure_cb = task_failure_cb

        self.target = None
        self.table_placed = False
        self.fails = 0
        self.last_action = None
        self.last_result = None
        self.cooldown_until = 0.0
        self.crafted_count = 0

    # ---------- ИНВЕНТАРЬ ----------

    def _count(self, inventory, item):
        total = 0
        for i in inventory:
            n = i.get('name', '')
            if n == item or item in n:
                total += i.get('count', 0)
        return total

    def _has(self, inventory, item):
        return self._count(inventory, item) > 0

    # ---------- ПЛАН НА ОДИН ШАГ ----------

    def _next_move(self, item, count, inventory, depth=0):
        """Вернуть ('gather'|'craft'|'place_table', params) или None, если готово."""
        if depth > self.max_depth:
            return None
        if self._count(inventory, item) >= count:
            return None

        r = self.recipes.get(item)
        if not r:
            return None

        if r.get('kind') == 'gather':
            # сначала нужный инструмент (кирка и т.п.)
            for ing, cnt in r.get('need', {}).items():
                mv = self._next_move(ing, cnt, inventory, depth + 1)
                if mv:
                    return mv
            return ('gather', {'name': item, 'from': self.recipes.sources(item)})

        # крафт: сперва ингредиенты
        for ing, cnt in r.get('need', {}).items():
            mv = self._next_move(ing, cnt, inventory, depth + 1)
            if mv:
                return mv

        # плавка: сначала печь, потом топливо/руда уже проверены выше
        if r.get('kind') == 'smelt':
            mv = self._next_move('furnace', 1, inventory, depth + 1)
            if mv:
                return mv
            return ('smelt', {'name': item})

        # всё есть — нужен верстак?
        if r.get('table') and not self.table_placed:
            if self._has(inventory, 'crafting_table'):
                return ('place_table', {})
            mv = self._next_move('crafting_table', 1, inventory, depth + 1)
            if mv:
                return mv
        return ('craft', {'name': item})

    # ---------- ШАГ ----------

    def tick(self, inventory, goal_override=None):
        """Сделать один шаг к текущей цели. Вернуть описание шага или None.

        inventory — список {'name','count'} из self_model.
        goal_override — задача от игры (если есть): её выполняем в первую
        очередь, а учебная программа ждёт. Так существо может пройти игру,
        которую никто ему не объяснял.
        """
        if time.time() < self.cooldown_until:
            return None

        # Новая задача игры заменяет текущую цель; своя программа — только
        # когда игра молчит.
        if goal_override and (self.target is None
                              or self.target.get('id') != goal_override.get('id')):
            self.target = goal_override
            self.fails = 0
            print(f"🎓 Учусь: {goal_override['name']} ({goal_override.get('item')})")
        elif self.target is None:
            goal = self.curriculum.next_goal(inventory)
            if not goal:
                return None
            self.target = goal
            self.fails = 0
            print(f"🎓 Учусь: {goal['name']} ({goal['item']})")

        # Задача-действие (не рецепт): просто выполняем то, что просит игра.
        if self.target.get('kind') == 'do':
            return self._do_task()

        move = self._next_move(self.target['item'], 1, inventory)
        if move is None:
            # цель достигнута — учебная программа сама перейдёт к следующей
            # (ступени отмечаются в next_goal, поддержка повторяется вечно).
            print(f"✅ Сделано: {self.target['name']}")
            self.crafted_count += 1
            self.target = None
            return None

        action, params = move
        self.last_action = action
        result = self.act(action, params=params)
        r = (result or {}).get('result', {}) if isinstance(result, dict) else {}
        self.last_result = r
        return self._handle_result(action, params, r)

    def _do_task(self):
        """Выполнить задачу-действие от игры (дверь, соединение, поиск)."""
        action = self.target.get('action') or 'look_around'
        params = self.target.get('params')
        self.last_action = action
        result = self.act(action, params=params)
        r = (result or {}).get('result', {}) if isinstance(result, dict) else {}
        self.last_result = r
        return self._handle_result(action, params, r)

    def _handle_result(self, action, params, r):
        params = params or {}
        if r.get('ok'):
            self.fails = 0
            if action == 'place_table':
                self.table_placed = True
            if action == 'craft':
                print(f"🔨 Скрафтил: {params.get('name')}")
            elif action == 'smelt':
                print(f"🔥 Переплавил: {params.get('name')}")
            elif action == 'gather':
                print(f"⛏️  Добыл: {params.get('name')}")
            return {'action': action, 'params': params, 'ok': True}

        # неудача: копим счётчик и иногда отступаем, чтобы не залипнуть
        self.fails += 1
        reason = r.get('reason', 'unknown')
        if self.fails <= 3:
            print(f"⚠️  Крафт-шаг не удался: {action} {params} ({reason})")
        if self.fails >= 6:
            if self.target.get('from_task') and self.task_failure_cb:
                self.task_failure_cb()
            else:
                self.curriculum.note_failure()
            print(f"⏭️  Пропускаю {self.target['item']} ({reason}) — вернусь позже")
            self.target = None
            self.fails = 0
            self.cooldown_until = time.time() + 20
        return {'action': action, 'params': params, 'ok': False, 'reason': reason}

    def summary(self):
        if self.target:
            return f"делаю: {self.target['name']} ({self.target['item']})"
        return "ремесло: " + self.curriculum.summary()
