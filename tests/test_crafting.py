"""Крафт и учебная программа: дерево → верстак → кирка → камень → железо."""
import os
import tempfile

from tests import _env  # noqa: F401  (path + isolated cwd)

from core.recipes import Recipes
from core.curriculum import Curriculum
from core.crafting import CraftingSkill
from adapters.mock import MockAdapter


# --- Recipes: разложение цели на сырьё и топологический порядок ---
r = Recipes(file=tempfile.mktemp(suffix='.json'))

base = r.base_ingredients('wooden_pickaxe')
# всё дерево в итоге — бревно: 3 доски (1 бревно) + палки (1 бревно) + верстак (1 бревно)
assert base.get('oak_log', 0) >= 3, base
print("base_ingredients: OK ->", base)

plan = r.plan('wooden_pickaxe')
actions = [s['action'] for s in plan]
items = [s['item'] for s in plan]
assert 'craft' in actions and 'gather' in actions, plan
# порядок: сначала добыча дерева, потом доски, потом палки, потом верстак, потом кирка
assert items.index('oak_log') < items.index('oak_planks'), items
assert items.index('oak_planks') < items.index('stick'), items
assert items.index('stick') < items.index('wooden_pickaxe'), items
assert 'crafting_table' in items, items  # кирке нужен верстак
print("plan: OK ->", items)

# каменная кирка тянет деревянную (нужна для камня)
plan2 = r.plan('stone_pickaxe')
items2 = [s['item'] for s in plan2]
assert items2.index('wooden_pickaxe') < items2.index('cobblestone'), items2
assert items2.index('cobblestone') < items2.index('stone_pickaxe'), items2
print("stone chain: OK ->", items2)

# железо тянет печь и каменную кирку
base3 = r.base_ingredients('iron_pickaxe')
assert base3.get('raw_iron', 0) >= 3, base3
print("iron chain: OK ->", base3)


# --- Curriculum: цель берётся из инвентаря и растёт ступенями ---
c = Curriculum(r, file=tempfile.mktemp(suffix='.json'))
inv = []
g = c.next_goal(inv)
assert g['item'] == 'oak_log', g
inv = [{'name': 'oak_log', 'count': 1}]
g = c.next_goal(inv)          # бревно есть → перешёл к доскам
assert g['item'] == 'oak_planks', g
assert 'wood' in c.done, c.done
inv += [{'name': 'oak_planks', 'count': 4}]
g = c.next_goal(inv)
assert g['item'] == 'stick', g
print("curriculum: OK ->", c.summary(), c.done)


# --- CraftingSkill: доводит цель до готовности на mock-теле ---
a = MockAdapter()
rec = Recipes(file=tempfile.mktemp(suffix='.json'))
cur = Curriculum(rec, file=tempfile.mktemp(suffix='.json'))
def sense():
    return a.get_self()['inventory']


sk = CraftingSkill(rec, cur, a.action, max_depth=12, sense=sense)

for i in range(900):
    inv = a.get_self()['inventory']
    sk.tick(inv)
    if cur.all_done():
        break

assert a.inventory.get('wooden_pickaxe', 0) >= 1, a.inventory
assert a.inventory.get('stone_pickaxe', 0) >= 1, a.inventory
assert a.inventory.get('crafting_table', 0) >= 1, a.inventory
assert a.inventory.get('iron_pickaxe', 0) >= 1, a.inventory
assert a.inventory.get('bed', 0) >= 1, a.inventory
assert a.inventory.get('bow', 0) >= 1, a.inventory
print("crafting skill: OK -> выучил", cur.progress(), "| инвентарь:",
      {k: v for k, v in a.inventory.items() if v})
# вся программа пройдена целиком: от дерева до лука
assert cur.all_done(), cur.progress()
assert len(cur.done) == len(cur.steps), cur.done

# бесконечный режим: после программы существо поддерживает снаряжение
inv = [{'name': 'iron_pickaxe', 'count': 1}]
goal = cur.next_goal(inv)
assert goal is not None and goal['id'].startswith('keep_'), goal
print("endless upkeep: OK ->", goal['name'])


# --- взаимозаменяемость: любое дерево — дерево ---
from core.recipes import count_in, material_family, has_tool

assert material_family('birch_log') == material_family('oak_log') == 'log'
assert material_family('birch_planks') == 'planks'
assert count_in([{'name': 'birch_log', 'count': 5}], 'oak_log') == 5
assert has_tool([{'name': 'iron_pickaxe', 'count': 1}], 'wooden_pickaxe')
assert not has_tool([{'name': 'wooden_pickaxe', 'count': 1}], 'iron_pickaxe')
print("family: OK -> берёза засчитывается как дуб, железная кирка вместо деревянной")


# --- регрессия живого тупика: тело отвечает ok, но вещь не появляется ---
class StuckBody(MockAdapter):
    """Тело врёт «добыл», а инвентарь не меняется (нет нужного блока рядом)."""

    def __init__(self):
        super().__init__()
        self.inventory = {'dirt': 10, 'stick': 1}
        self.gathers = 0

    def action(self, action, params=None):
        if action == 'gather':
            self.gathers += 1
            return {'ok': True, 'result': {'ok': True, 'gathered': 'oak_log'}}
        return super().action(action, params)


stuck = StuckBody()
rec2 = Recipes(file=tempfile.mktemp(suffix='.json'))
cur2 = Curriculum(rec2, file=tempfile.mktemp(suffix='.json'))
sk2 = CraftingSkill(rec2, cur2, stuck.action, max_depth=12,
                    sense=lambda: stuck.get_self()['inventory'])
for i in range(60):
    sk2.tick(stuck.get_self()['inventory'])
# без проверки прогресса он бы копал бесконечно; теперь цикл прекращается
assert stuck.gathers <= 12, stuck.gathers
print("no-progress guard: OK -> перестал долбить одно и то же (", stuck.gathers, "попыток)")


# --- берёзовый мир: дуба нет, а прогресс всё равно идёт ---
class BirchBody(MockAdapter):
    def __init__(self):
        super().__init__()
        self.inventory = {'birch_log': 40, 'dirt': 10}

    def action(self, action, params=None):
        params = params or {}
        if action == 'gather':
            name = params.get('name') or (params.get('from') or ['oak_log'])[0]
            if name in ('oak_log', 'log', 'birch_log'):
                self._add('birch_log', 1)
                return {'ok': True, 'result': {'ok': True, 'gathered': 'birch_log'}}
        return super().action(action, params)


birch = BirchBody()
rec3 = Recipes(file=tempfile.mktemp(suffix='.json'))
cur3 = Curriculum(rec3, file=tempfile.mktemp(suffix='.json'))
sk3 = CraftingSkill(rec3, cur3, birch.action, max_depth=12,
                    sense=lambda: birch.get_self()['inventory'])
for i in range(400):
    sk3.tick(birch.get_self()['inventory'])
    if cur3.all_done():
        break
assert cur3.progress().split('/')[0] != '0', cur3.progress()
assert birch.inventory.get('wooden_pickaxe', 0) >= 1, birch.inventory
print("birch world: OK -> прогресс без дуба:", cur3.progress())


print("\nCRAFTING/CURRICULUM TESTS PASSED")
