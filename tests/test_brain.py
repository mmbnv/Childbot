"""Ядро мозга: нейроколонна, предиктор, внимание, память, драйвы, план."""
import tempfile

from tests import _env  # noqa: F401  (path + isolated cwd)
import numpy as np

from core.neural_column import NeuralColumn
from core.predictor import Predictor
from core.global_workspace import GlobalWorkspace
from core.working_memory import WorkingMemory
from core.episodic_memory import EpisodicMemory
from core.drives import Drives
from core.cognition import SymbolicMemory
from core.planner import Planner

import time as _t


# --- NeuralColumn: разреженность, обучение, imagine не портит состояние, save/load
nc = NeuralColumn(20, n_hidden=32, n_output=8)
x = np.random.rand(20)
h, out = nc.forward(x)
assert h.shape == (32,) and out.shape == (8,)
assert (h >= 0).all()
k = max(1, int(32 * 0.1))
assert int((h > 0).sum()) <= k, f"sparsity violated: {(h > 0).sum()}"
target = np.ones(8) * 0.8
errs = []
for _ in range(60):
    h, out = nc.forward(x)
    errs.append(np.mean(np.abs(target - out)))
    nc.learn(x, h, out, target, dopamine=1.0, lr=0.05)
assert errs[-1] < errs[0], f"no learning: {errs[0]:.3f} -> {errs[-1]:.3f}"
p0 = nc.prev_h.copy()
nc.imagine(x, steps=3)
assert np.allclose(p0, nc.prev_h), "imagine mutated state"
with tempfile.TemporaryDirectory() as d:
    p = f"{d}/col.npz"
    nc.save(p)
    nc2 = NeuralColumn(20, n_hidden=32, n_output=8)
    assert nc2.load(p)
    h1, _ = nc.forward(x, update_state=False)
    h2, _ = nc2.forward(x, update_state=False)
    assert np.allclose(h1, h2)
print("NeuralColumn: OK (learned %.3f -> %.3f, %d synapses alive)" % (
    errs[0], errs[-1], nc.stats()['alive_synapses']))


# --- Predictor: учится связи действие→облегчение
pr = Predictor()
drives = {'hunger': 0.8, 'fear': 0.0, 'pain': 0.0, 'boredom': 0.0,
          'loneliness': 0.0, 'fatigue': 0.0, 'curiosity': 0.0, 'comfort': 0.5}
state = {'health': 20, 'food': 6, 'is_night': False, 'player': None,
         'nearest_hostile': None}
for _ in range(200):
    pr.observe_relief('eat_food', 'hunger', state, 1.0, learning_rate=0.9)
    pr.observe_relief('find_and_attack', 'hunger', state, 1.0, learning_rate=0.9)
r_eat = pr.predict_relief('eat_food', drives, state)
r_dig = pr.predict_relief('dig_down', drives, state)
assert r_eat > r_dig, f"predictor didn't learn: eat={r_eat:.3f} dig={r_dig:.3f}"
best, _ = pr.best_action(drives, state, ['eat_food', 'dig_down', 'look_up'])
assert best == 'eat_food', best
assert isinstance(pr.rollout(drives, state, ['eat_food']), float)
print("Predictor: OK (eat %.3f > dig %.3f; best=%s)" % (r_eat, r_dig, best))


# --- GlobalWorkspace: побеждает самый значимый сигнал
gw = GlobalWorkspace(dwell_sec=0.0)
gw.submit('threat', 'опасность', 2.0)
gw.submit('hunger', 'голод', 1.0)
f = gw.compete()
assert f.channel == 'threat'
assert gw.is_focused_on('threat')
print("GlobalWorkspace: OK (focus=%s)" % f.channel)


# --- WorkingMemory: ёмкость ~7 слотов
wm = WorkingMemory()
for i in range(12):
    wm.hold(f'k{i}', i, salience=1.0)
assert len(wm.slots) <= wm.CAPACITY, len(wm.slots)
print("WorkingMemory: OK (capacity respected: %d/%d)" % (len(wm.slots), wm.CAPACITY))


# --- EpisodicMemory: поиск по эмоционально значимому
em = EpisodicMemory(file=tempfile.mktemp(suffix='.json'))
em.remember("меня укусил зомби", "урон", feeling='боль', result='danger',
            valence=-0.9, importance=1.0)
em.remember("я поел", "eat_food", feeling='сытость', result='ok',
            valence=0.4, importance=0.5)
assert len(em.recall_similar('зомби')) == 1
assert em.salient_memories(1)[0].what == "меня укусил зомби"
print("EpisodicMemory: OK (%s)" % em.summary())


# --- Drives: угроза/ночь/боль поднимают напряжение
d = Drives()
st = {'food': 4, 'health': 6, 'is_night': True,
      'nearest_hostile': {'distance': 3}, 'recent_damage': True, 'time_of_day': 15000}
for _ in range(10):
    d.tick(st, is_new_cell=False)
assert d.hunger > 0.5 and d.fear > 0.5 and d.pain > 0.3
assert d.tension() > 2.0
print("Drives: OK (tension %.2f, dominant=%s)" % (d.tension(), d.dominant()))


# --- Planner: строит план из выученного опыта
sm = SymbolicMemory.__new__(SymbolicMemory)
sm.objects = {'cow': [{'x': 10, 'y': 64, 'z': 5, 'seen': _t.time()}]}
sm.effects = {}
sm.places = {}
pl = Planner(sm)
dr = Drives()
dr.hunger = 0.9
plan = pl.make_plan(dr, {'nearest_hostile': None, 'is_night': False}, predictor=pr)
assert plan is not None and plan.actions(), plan
assert plan.actions()[0] in ('eat_food', 'find_and_attack'), plan.actions()
print("Planner: OK (plan=%s)" % plan.actions())


print("\nALL TESTS PASSED")
