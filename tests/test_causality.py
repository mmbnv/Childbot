"""Причинно-следственный разум: почему не вышло и что помогает.

Проверяем, что существо не просто терпит неудачу, а разбирает её на причину,
помнит её, выводит средство и обходные пути, и что всё это переносится между
играми (опирается на признаки, а не на конкретные блоки).
"""
import os
import tempfile

from tests import _env  # noqa: F401  (path + isolated cwd)

from core.causality import Reasoner
from core.recipes import Recipes


r = Recipes(file=tempfile.mktemp(suffix='.json'))
cause_file = tempfile.mktemp(suffix='.json')
reasoner = Reasoner(file=cause_file, recipes=r)


# --- разбор причин из прямого сообщения тела ---
c = reasoner.explain('gather', {'name': 'stone'}, False, 'out_of_reach')
assert c is not None and c.key == 'reach', c and c.key
assert any(a == 'step_forward' for a, _ in c.plan), c.plan
print("reach: OK ->", c.text, "| план:", [a for a, _ in c.plan])

c = reasoner.explain('gather', {'name': 'cobblestone'}, False, 'no_tool')
assert c.key == 'tool', c.key
# средство — конкретный инструмент из рецептов
assert c.action == 'craft' and c.params and c.params.get('name') == 'wooden_pickaxe', \
    (c.action, c.params)
print("tool: OK -> нужно:", c.params.get('name'))

c = reasoner.explain('use', {}, False, 'locked')
assert c.key == 'locked' and c.need == 'ключ', (c.key, c.need)
assert any(a in ('gather', 'combine') for a, _ in c.plan), c.plan
print("locked: OK ->", c.text, "| план:", [a for a, _ in c.plan])

c = reasoner.explain('craft', {'name': 'wooden_pickaxe'}, False, 'no_crafting_table')
assert c.key == 'no_table' and c.need == 'верстак', (c.key, c.need)
print("no_table: OK ->", c.text)

c = reasoner.explain('craft', {'name': 'iron_ingot'}, False, 'no_materials',
                     before={'_inventory': []})
assert c.key == 'materials' and c.need, (c.key, c.need)
print("materials: OK -> не хватает:", c.need)


# --- разбор причин из признаков мира (тело промолчало) ---
c = reasoner.explain('step_forward', None, False, '', before={'blocked': True})
assert c.key == 'solid', c.key
assert any(a in ('dig_forward', 'step_left', 'step_right') for a, _ in c.plan), c.plan
print("solid: OK ->", c.text, "| план:", [a for a, _ in c.plan])

c = reasoner.explain('dig_down', None, False, '', before={'support_below': False})
assert c.key == 'no_support', c.key
print("no_support: OK ->", c.text)

c = reasoner.explain('attack_hostile', None, False, '', before={'hostile': None})
assert c.key == 'no_target', c.key
print("no_target: OK ->", c.text)


# --- память о причинах: копится и переживает перезапуск ---
for _ in range(3):
    reasoner.explain('use', {}, False, 'locked')
b = reasoner.beliefs['locked']
assert b['count'] >= 4, b
assert b['need'] == 'ключ', b
print("memory: OK ->", reasoner.summary())

reasoner.save()
reasoner2 = Reasoner(file=cause_file, recipes=r)
assert reasoner2.beliefs.get('locked', {}).get('count', 0) >= 4, reasoner2.beliefs
print("persist: OK -> причины помнятся между запусками")


# --- средство помогло → причина решена ---
before_fixed = reasoner.beliefs['locked'].get('fixed', 0)
c = reasoner.explain('use', {}, False, 'locked')
reasoner.note_fix(c)
assert reasoner.beliefs['locked']['fixed'] > before_fixed, reasoner.beliefs['locked']
print("fixed: OK ->", reasoner.beliefs['locked'])


# --- подсказка поведению: причина запрещает вредное и ценит средство ---
bonus, forbid = reasoner.advice({'support_below': False}, 'dig_down')
assert forbid, (bonus, forbid)
print("advice forbid: OK -> копать вниз без опоры запрещено")

bonus, forbid = reasoner.advice({'support_below': True}, 'step_forward',
                                params=None)
assert not forbid, (bonus, forbid)
print("advice allow: OK")


# --- размышление вслух о причине ---
r3 = Reasoner(file=tempfile.mktemp(suffix='.json'), recipes=r)
for _ in range(2):
    r3.explain('step_forward', None, False, '', before={'blocked': True})
r3.reflection_interval = 0
thought = r3.reflect({}, now=1.0)
assert thought and ('не выходит' in thought or 'научился' in thought), thought
print("reflect: OK ->", thought)


# --- универсальность: та же причина работает в другой игре ---
# В «подземелье» дверь заперта, пока не соединишь ключ с замком.
c = reasoner.diagnose('use', {}, 'locked', {})
assert c.key == 'locked' and any(a == 'combine' for a, _ in c.plan), c.plan
print("cross-game: OK -> 'заперто' лечится соединением в любой игре")


# --- сквозная проверка: тело честно отказывает, мозг понимает почему ---
from adapters.mock import MockAdapter

a = MockAdapter()
res = a.action('gather', {'name': 'cobblestone'})
inner = res.get('result', res)
assert inner.get('ok') is False and inner.get('reason') == 'no_tool', inner
c = reasoner.diagnose('gather', {'name': 'cobblestone'}, inner['reason'], {})
assert c.key == 'tool' and c.params.get('name') == 'wooden_pickaxe', c.params
print("integration: OK -> без кирки камень не бьётся, нужно:", c.params.get('name'))

a.inventory['wooden_pickaxe'] = 1     # инструмент добыт — причина устранена
res2 = a.action('gather', {'name': 'cobblestone'})
assert res2.get('result', res2).get('ok') is True, res2
print("integration: OK -> с киркой камень добывается")


print("\nCAUSALITY TESTS PASSED")
