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
sk = CraftingSkill(rec, cur, a.action, max_depth=12)

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


print("\nCRAFTING/CURRICULUM TESTS PASSED")
