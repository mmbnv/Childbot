"""Фундаментальные понятия: законы мира, опыты и задачи игры."""
from tests import _env  # noqa: F401  (path + isolated cwd)

from core.concepts import ConceptLearner, extract_features
from core.experiment import Experimenter
from core.tasks import TaskTracker
from core.recipes import Recipes


def feats(**kw):
    base = {'x': 0.0, 'y': 64.0, 'z': 0.0, 'on_ground': True, 'support_below': True,
            'blocked': False, 'health': 20.0, 'food': 20.0, 'inventory_total': 0.0,
            'near_door': False, 'door_open': False, 'hostile': None, 'night': False}
    base.update(kw)
    return base


# --- extract_features: безопасные умолчания и сбор из тела ---
f = extract_features({'x': 3, 'on_ground': False, 'near_door': True},
                     {'inventory': [{'name': 'dirt', 'count': 5}]})
assert f['x'] == 3 and f['on_ground'] is False and f['near_door'] is True
assert f['inventory_total'] == 5
assert extract_features(None, None)['y'] == 0.0
print("extract_features: OK")


# --- Гравитация: нет опоры → падаю вниз ---
cl = ConceptLearner(file='/tmp/nonexistent_concepts.json')
for _ in range(6):
    cl.observe(feats(support_below=False, on_ground=False, y=64),
               feats(support_below=False, on_ground=False, y=63), 'step_forward',
               {'ok': True})
assert cl.knows('gravity'), cl.explain()
assert cl.confidence('gravity') > 0.7
print("Concept gravity: OK (%s)" % cl.summary())


# --- Опора: стою на твёрдом — не проваливаюсь ---
cl2 = ConceptLearner(file='/tmp/nonexistent_concepts2.json')
for _ in range(5):
    cl2.observe(feats(support_below=True, on_ground=True, y=64),
                feats(support_below=True, on_ground=True, y=64), 'step_forward', {'ok': True})
assert cl2.knows('support'), cl2.explain()
print("Concept support: OK")


# --- Стена: упёрся — не сдвинулся ---
cl3 = ConceptLearner(file='/tmp/nonexistent_concepts3.json')
for _ in range(5):
    cl3.observe(feats(blocked=True, x=0), feats(blocked=True, x=0), 'step_forward', {'ok': True})
assert cl3.knows('solid'), cl3.explain()
print("Concept solid: OK")


# --- Дверь: use рядом с дверью пропускает ---
cl4 = ConceptLearner(file='/tmp/nonexistent_concepts4.json')
for _ in range(4):
    cl4.observe(feats(near_door=True, door_open=False, x=0),
                feats(near_door=True, door_open=True, x=1), 'use', {'ok': True})
assert cl4.knows('passage'), cl4.explain()
print("Concept passage: OK")


# --- Соединение (химия): combine меняет инвентарь ---
cl5 = ConceptLearner(file='/tmp/nonexistent_concepts5.json')
for _ in range(4):
    cl5.observe(feats(inventory_total=2), feats(inventory_total=1), 'combine', {'ok': True})
assert cl5.knows('combine'), cl5.explain()
print("Concept combine: OK")


# --- Опасность/питание/инструмент ---
cl6 = ConceptLearner(file='/tmp/nonexistent_concepts6.json')
for _ in range(4):
    cl6.observe(feats(health=20, hostile=3.0), feats(health=18, hostile=None),
                'attack_hostile', {'ok': True})
    cl6.observe(feats(food=10), feats(food=16), 'eat_food', {'ok': True})
    cl6.observe(feats(inventory_total=0), feats(inventory_total=1), 'gather', {'ok': True})
assert cl6.knows('danger') and cl6.knows('nutrition') and cl6.knows('tool'), cl6.explain()
print("Concepts danger/nutrition/tool: OK")


# --- Совет поведению: в воздухе запрещено копать под собой ---
bonus, forbid = cl.advice(feats(support_below=False, on_ground=False), 'dig_down')
assert forbid is True
bonus2, forbid2 = cl4.advice(feats(near_door=True, door_open=False), 'use')
assert bonus2 > 0 and forbid2 is False
print("Concept advice: OK (forbid dig_down in air, value door)")


# --- Опыты: выбирается неизвестный закон, опыт безопасен ---
ex = Experimenter(cl, cooldown=0.0)
probe = ex.maybe_probe(feats(), now=1000.0)
assert probe is not None, "experimenter should pick a probe"
action, params, law, why = probe
assert action in ('jump_once', 'jump_forward', 'step_forward', 'gather', 'craft',
                  'smelt', 'eat_food', 'go_to_position', 'use'), action
assert law in cl.laws
ex.observe(law, True)
assert ex.summary()
print("Experimenter: OK (%s -> %s)" % (law, action))


# --- Задачи игры: берём, выполняем, отмечаем ---
class _TaskAdapter:
    def __init__(self):
        self.tasks = [
            {'id': 'a', 'name': 'добыть дерево', 'target': 'oak_log', 'count': 1, 'done': False},
            {'id': 'b', 'name': 'сделать верстак', 'target': 'crafting_table', 'count': 1, 'done': False},
        ]

    def get_tasks(self):
        return self.tasks


tt = TaskTracker(Recipes())
ad = _TaskAdapter()
# сначала ничего нет — берём первую задачу
tt.poll(ad, [], force=True)
g = tt.next_goal([])
assert g is not None and g['item'] == 'oak_log', g
# выполнили (игра отметила) — переходим к следующей
ad.tasks[0]['done'] = True
tt.poll(ad, [{'name': 'oak_log', 'count': 1}], force=True)
g2 = tt.next_goal([{'name': 'oak_log', 'count': 1}])
assert g2 is not None and g2['item'] == 'crafting_table', g2
print("TaskTracker: OK (%s -> %s)" % (g['item'], g2['item']))


# --- Задача-действие (не рецепт): выводим действие из смысла ---
class _ActAdapter:
    def get_tasks(self):
        return [{'id': 'x', 'name': 'открыть дверь', 'target': 'door_open',
                 'count': 1, 'done': False}]


tt2 = TaskTracker(Recipes())
tt2.poll(_ActAdapter(), [], force=True)
gd = tt2.next_goal([])
assert gd is not None and gd.get('kind') == 'do', gd
assert gd.get('action') == 'use', gd
print("TaskTracker do-task: OK (action=%s)" % gd.get('action'))


print("\nALL TESTS PASSED")
