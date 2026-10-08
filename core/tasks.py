"""
Tasks — что игра ставит перед существом.

Любая игра чего-то хочет от игрока: достижения, квесты, цели уровня. Обычно
их можно перечислить списком:

    [{'id': 'wood', 'name': 'добыть дерево', 'target': 'oak_log', 'count': 1,
      'need': 'рубить дерево', 'done': False}, ...]

Существо спрашивает у тела «чего от меня хочет игра?» (адаптер, метод
`get_tasks`), само выбирает ближайшую незакрытую задачу и доводит её до конца
теми же умениями, что и свою программу (рецепты + ремесло). Так он может
пройти игру, даже если её никто не объяснял.

Если игра не умеет отдавать задачи — модуль сам выводит их из мира:
достижимые предметы из рецептов становятся задачами «сделать это».
"""
import time


class TaskTracker:
    def __init__(self, recipes):
        self.recipes = recipes
        self.tasks = []          # последний список от игры
        self.current = None      # выбранная задача
        self.done_ids = set()    # закрытые задачи
        self.last_poll = 0.0
        self.poll_interval = 5.0
        self.completed_count = 0
        self.fails = 0

    # ---------- ОПРОС ИГРЫ ----------

    def poll(self, adapter, inventory, now=None, force=False):
        """Спросить у игры список задач (не чаще poll_interval)."""
        now = now or time.time()
        if not force and (now - self.last_poll) < self.poll_interval:
            return self.tasks
        self.last_poll = now
        getter = getattr(adapter, 'get_tasks', None)
        tasks = None
        if callable(getter):
            try:
                tasks = getter()
            except Exception:
                tasks = None
        if not tasks:
            tasks = self._infer_tasks(inventory)
        self.tasks = [t for t in (tasks or []) if isinstance(t, dict) and t.get('name')]
        # отмечаем закрытые игрой (и сбрасываем текущую, если её закрыла игра)
        for t in self.tasks:
            if t.get('done') and t.get('id') is not None:
                self.done_ids.add(t['id'])
                if self.current is not None and self.current.get('id') == t['id']:
                    self._finish(self.current)
                    self.current = None
        return self.tasks

    def _infer_tasks(self, inventory):
        """Если игра молчит — вывести задачи из того, что можно сделать."""
        inferred = []
        for item, r in list(self.recipes.data.items()):
            if r.get('kind') != 'craft':
                continue
            if self._has(inventory, item):
                continue
            inferred.append({'id': 'craft_' + item, 'name': f'сделать {item}',
                             'target': item, 'count': 1, 'need': 'рецепт', 'done': False})
        return inferred

    # ---------- ВЫБОР ЗАДАЧИ ----------

    def next_goal(self, inventory):
        """Ближайшая незакрытая задача как цель для ремесла (или None)."""
        if self.current is not None:
            if self._goal_reached(self.current, inventory):
                self._finish(self.current)
                self.current = None
            else:
                return self._as_goal(self.current)

        task = self._pick_task(inventory)
        if not task:
            return None
        self.current = task
        self.fails = 0
        print(f"🎯 Задача игры: {task['name']}")
        return self._as_goal(task)

    def _pick_task(self, inventory):
        for t in self.tasks:
            if t.get('done'):
                continue
            if t.get('id') in self.done_ids:
                continue
            target = t.get('target')
            if target and self._has(inventory, target):
                self.done_ids.add(t.get('id'))
                continue
            # Задача-рецепт осиливается ремеслом; задача-действие (дверь,
            # соединение, поиск) — тем действием, что подсказывает игра или
            # смысл задачи. Игра ставит задачи — значит, они по силам.
            return t
        return None

    def _as_goal(self, task):
        target = task.get('target')
        goal = {
            'id': 'task_' + str(task.get('id')),
            'item': target,
            'name': task.get('name') or target,
            'need': task.get('need', ''),
            'count': task.get('count', 1),
            'craft': bool(target and self.recipes.is_craft(target)),
            'from_task': True,
        }
        if not (target and self.recipes.know(target)):
            goal['kind'] = 'do'
            goal['action'] = task.get('action') or self._infer_action(task)
            goal['params'] = task.get('params')
        return goal

    @staticmethod
    def _infer_action(task):
        """Если игра не указала действие — вывести его из смысла задачи."""
        text = (str(task.get('name', '')) + ' ' + str(task.get('need', ''))).lower()
        if any(w in text for w in ('двер', 'откр', 'использ', 'use')):
            return 'use'
        if any(w in text for w in ('соедин', 'смеш', 'combine', 'замок', 'ключ')):
            return 'combine'
        if any(w in text for w in ('найти', 'искать', 'собрать', 'добыть', 'gather')):
            return 'gather'
        if any(w in text for w in ('дойти', 'иди', 'выход', 'reach', 'go')):
            return 'step_forward'
        return 'look_around'

    def _goal_reached(self, task, inventory):
        target = task.get('target')
        if not target:
            return False
        need = int(task.get('count', 1) or 1)
        return self._count(inventory, target) >= need

    def _finish(self, task):
        self.done_ids.add(task.get('id'))
        self.completed_count += 1
        print(f"🏆 Задача выполнена: {task['name']}")

    def note_failure(self):
        self.fails += 1
        if self.fails >= 6:
            print(f"⏭️  Задача {self.current.get('name') if self.current else '?'} "
                  f"пока не по силам — вернусь позже")
            self.current = None
            self.fails = 0

    # ---------- СЧЁТ ----------

    @staticmethod
    def _count(inventory, item):
        total = 0
        for i in inventory or []:
            n = i.get('name', '')
            if n == item or item in n:
                total += i.get('count', 0)
        return total

    def _has(self, inventory, item):
        return self._count(inventory, item) > 0

    def summary(self):
        open_n = sum(1 for t in self.tasks if not t.get('done') and t.get('id') not in self.done_ids)
        if self.current:
            return f"делаю задачу: {self.current['name']}"
        if self.tasks:
            return f"задач игры: {open_n} открыто, выполнено {self.completed_count}"
        return "задач от игры нет"
