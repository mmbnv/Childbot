"""
Recipes — знание о крафте: из чего что делается.

Это «семантическая» память о ремесле, а не о мире. По ней существо умеет
разложить желаемую вещь на шаги: что добыть, что скрафтить сначала, что
собрать в конце. Так ребёнок учится: сначала палка, потом кирка, потом
камень, потом инструмент получше.

Граф намеренно небольшой, но с настоящими зависимостями (доска → палка →
кирка → каменная кирка → железная кирка), чтобы прогрессия была сквозной.
"""
import json
import os


RECIPES_FILE = "data/recipes.json"


# item -> {'need': {ingredient: count}, 'table': bool, 'from': [blocks],
#          'kind': 'craft' | 'gather'}
#
# 'from' — из каких блоков мира добывается предмет (для добычи).
# 'kind' — 'gather' значит «взять в мире», 'craft' — «сделать руками/верстаком».
RECIPES = {
    # --- дерево ---
    'oak_log':         {'kind': 'gather', 'from': ['oak_log', 'log'], 'need': {}},
    'birch_log':       {'kind': 'gather', 'from': ['birch_log', 'log'], 'need': {}},
    'oak_planks':      {'kind': 'craft', 'need': {'oak_log': 1}, 'table': False, 'yield': 4},
    'birch_planks':    {'kind': 'craft', 'need': {'birch_log': 1}, 'table': False, 'yield': 4},
    'stick':           {'kind': 'craft', 'need': {'oak_planks': 2}, 'table': False, 'yield': 4},
    'crafting_table':  {'kind': 'craft', 'need': {'oak_planks': 4}, 'table': False, 'yield': 1},

    # --- камень и инструменты ---
    'cobblestone':     {'kind': 'gather', 'from': ['stone'], 'need': {'wooden_pickaxe': 1}},
    'wooden_pickaxe':  {'kind': 'craft', 'need': {'oak_planks': 3, 'stick': 2}, 'table': True, 'yield': 1},
    'stone_pickaxe':   {'kind': 'craft', 'need': {'cobblestone': 3, 'stick': 2}, 'table': True, 'yield': 1},
    'stone_sword':     {'kind': 'craft', 'need': {'cobblestone': 2, 'stick': 1}, 'table': True, 'yield': 1},
    'stone_axe':       {'kind': 'craft', 'need': {'cobblestone': 3, 'stick': 2}, 'table': True, 'yield': 1},

    # --- железо ---
    'iron_ore':        {'kind': 'gather', 'from': ['iron_ore', 'deepslate_iron_ore'],
                        'need': {'stone_pickaxe': 1}},
    'raw_iron':        {'kind': 'gather', 'from': ['iron_ore', 'deepslate_iron_ore'],
                        'need': {'stone_pickaxe': 1}},
    # плавится в печи, а не крафтится: kind='smelt'
    'iron_ingot':      {'kind': 'smelt', 'need': {'raw_iron': 1, 'coal': 1}, 'table': False, 'yield': 1},
    'furnace':         {'kind': 'craft', 'need': {'cobblestone': 8}, 'table': True, 'yield': 1},
    'iron_pickaxe':    {'kind': 'craft', 'need': {'iron_ingot': 3, 'stick': 2}, 'table': True, 'yield': 1},
    'iron_sword':      {'kind': 'craft', 'need': {'iron_ingot': 2, 'stick': 1}, 'table': True, 'yield': 1},

    # --- еда и выживание ---
    'bread':           {'kind': 'craft', 'need': {'wheat': 3}, 'table': True, 'yield': 1},
    'wheat':           {'kind': 'gather', 'from': ['wheat'], 'need': {}},
    'torch':           {'kind': 'craft', 'need': {'coal': 1, 'stick': 1}, 'table': False, 'yield': 4},
    'coal':            {'kind': 'gather', 'from': ['coal_ore', 'deepslate_coal_ore'], 'need': {'wooden_pickaxe': 1}},

    # --- защита ---
    'iron_helmet':     {'kind': 'craft', 'need': {'iron_ingot': 5}, 'table': True, 'yield': 1},
    'iron_chestplate': {'kind': 'craft', 'need': {'iron_ingot': 8}, 'table': True, 'yield': 1},
    'iron_leggings':   {'kind': 'craft', 'need': {'iron_ingot': 7}, 'table': True, 'yield': 1},
    'iron_boots':      {'kind': 'craft', 'need': {'iron_ingot': 4}, 'table': True, 'yield': 1},

    # --- база ---
    'wooden_door':     {'kind': 'craft', 'need': {'oak_planks': 6}, 'table': True, 'yield': 3},
    'chest':           {'kind': 'craft', 'need': {'oak_planks': 8}, 'table': True, 'yield': 1},
    'bed':             {'kind': 'craft', 'need': {'oak_planks': 3, 'white_wool': 3}, 'table': True, 'yield': 1},
    'white_wool':      {'kind': 'gather', 'from': ['white_wool', 'sheep'], 'need': {}},
}


class Recipes:
    def __init__(self, file=RECIPES_FILE):
        self.file = file
        self.data = dict(RECIPES)
        self.learned = {}          # выученные существом рецепты (переживают перезапуск)
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                learned = json.load(f).get('learned', {})
            for k, v in learned.items():
                self.data[k] = v
                self.learned[k] = v
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'learned': self.learned}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def know(self, item):
        return item in self.data

    def get(self, item):
        return self.data.get(item)

    def learn(self, item, recipe):
        """Запомнить рецепт навсегда (существо «изучило» крафт)."""
        self.data[item] = recipe
        self.learned[item] = recipe
        self.save()

    def is_craft(self, item):
        r = self.data.get(item)
        return bool(r) and r.get('kind') == 'craft'

    def is_gather(self, item):
        r = self.data.get(item)
        return bool(r) and r.get('kind') == 'gather'

    def is_smelt(self, item):
        r = self.data.get(item)
        return bool(r) and r.get('kind') == 'smelt'

    def sources(self, item):
        """Из каких блоков мира добывается предмет."""
        r = self.data.get(item)
        return list(r.get('from', [])) if r else []

    def needs_table(self, item):
        r = self.data.get(item)
        return bool(r) and r.get('table', False)

    def base_ingredients(self, item):
        """Разложить предмет на конечные (добываемые) ингредиенты.

        Возвращает {base_item: total_count} — сколько чего реально нужно
        набрать в мире, с учётом промежуточных крафтов.
        """
        result = {}

        def walk(name, mult, seen):
            if name in seen:          # защита от циклов
                result[name] = result.get(name, 0) + mult
                return
            r = self.data.get(name)
            if not r or r.get('kind') == 'gather' or not r.get('need'):
                result[name] = result.get(name, 0) + mult
                return
            per = r.get('yield', 1) or 1
            need_batches = -(-mult // per)   # ceil
            if r.get('table') and name != 'crafting_table':
                walk('crafting_table', need_batches, seen | {name})
            if r.get('kind') == 'smelt':
                walk('furnace', need_batches, seen | {name})
            for ing, cnt in r['need'].items():
                walk(ing, need_batches * cnt, seen | {name})

        walk(item, 1, set())
        return result

    def plan(self, item):
        """Пошаговый план крафта: список шагов от сырья к цели.

        Каждый шаг — словарь:
          {'action': 'gather'|'craft'|'place_table', 'item', 'need', 'table'}
        Порядок топологический: сначала то, что нужно раньше.
        """
        steps = []
        done = set()

        def walk(name):
            if name in done:
                return
            r = self.data.get(name)
            if not r:
                return
            if r.get('kind') == 'gather':
                # сначала инструмент, которым это добывается (кирка и т.п.)
                for ing in r.get('need', {}):
                    walk(ing)
                steps.append({'action': 'gather', 'item': name,
                              'from': self.sources(name), 'need': r.get('need', {})})
                done.add(name)
                return
            for ing in r.get('need', {}):
                walk(ing)
            if r.get('table') and name != 'crafting_table':
                walk('crafting_table')
            if r.get('kind') == 'smelt':
                walk('furnace')
                steps.append({'action': 'smelt', 'item': name,
                              'need': r.get('need', {}), 'table': False})
            else:
                steps.append({'action': 'craft', 'item': name,
                              'need': r.get('need', {}), 'table': r.get('table', False)})
            done.add(name)

        walk(item)
        return steps

    def craftable_now(self, item, inventory):
        """Можно ли прямо сейчас скрафтить предмет (всё есть в инвентаре)."""
        r = self.data.get(item)
        if not r or r.get('kind') != 'craft':
            return False
        return all(self._count(inventory, ing) >= cnt
                   for ing, cnt in r.get('need', {}).items())

    @staticmethod
    def _count(inventory, item):
        total = 0
        for i in inventory:
            n = i.get('name', '')
            if n == item or n.endswith('_' + item) or item in n:
                total += i.get('count', 0)
        return total

    def summary(self):
        crafts = [k for k, v in self.data.items() if v.get('kind') == 'craft']
        return f"знаю {len(crafts)} рецептов, выучил {len(self.learned)}"
