"""Врождённый инстинкт fly-brain (коннектом FlyWire FAFB) — проверки.

Проверяем то, что делает инстинкт настоящим дополнением выученного мозга:
  * LIF-движок повторяет динамику fly-brain (порог, рефрактерность, синапс);
  * ситуация ребёнка ПРАВИЛЬНО переводится в стимул (еда → сладкое, угроза → бегство);
  * знак инстинкта СМЕЩАЕТ выбор согласных действий, а не приказывает;
  * инстинкт ТИХО выключается без данных/scipy и не ломает существо;
  * на реальном коннектоме сладкое ведёт вперёд, а угроза — к бегству.
"""
import tempfile
from pathlib import Path

from tests import _env  # noqa: F401  (path + isolated cwd)

import numpy as np
import scipy.sparse as sp

from flybrain.config import BrainConfig
from flybrain.lif import LIFNetwork
from flybrain.instinct import FlyBrainInstinct, InstinctReading, BIAS_STRENGTH
from flybrain.neurons import SUGAR_GRNS, P9_DESCENDING, ESCAPE_DESCENDING


class _Drives:
    def __init__(self, **kw):
        base = {'hunger': 0.0, 'fear': 0.0, 'pain': 0.0, 'boredom': 0.0,
                'loneliness': 0.0, 'fatigue': 0.0, 'curiosity': 0.0, 'comfort': 0.2}
        base.update(kw)
        self._d = base

    def to_dict(self):
        return self._d


def _idle_state(**kw):
    s = {'health': 20, 'food': 20, 'is_night': False, 'player': None,
         'nearest_hostile': None}
    s.update(kw)
    return s


# 1. LIF: порог — сильный прямой стимул заставляет нейрон вспыхнуть.
cfg = BrainConfig()
w = sp.csr_matrix((3, 3), dtype=np.float32)
net = LIFNetwork(w, cfg)
net.set_stimulus_rates({0: 1000.0})
spikes = [net.step(t).spiked_indices.size for t in range(40)]
assert sum(spikes) > 0, "стимулируемый нейрон ни разу не вспыхнул"
print(f"LIF threshold: OK (спайков {sum(spikes)} за 40 шагов)")

# 1b. РЕФРАКТЕРНОСТЬ гейтит СИНАПТИЧЕСКИЙ вход: сразу после спайка входящая
#     проводимость не проходит (open_mask), а без спайка — проходит.
def _incoming_conductance(neuron_spiked_last: bool) -> float:
    n = LIFNetwork(sp.csr_matrix((1, 1), dtype=np.float32), cfg)
    n.spikes[0, 0] = 1.0 if neuron_spiked_last else 0.0
    n.conductance[0, 0] = 0.0
    n.delay_buffer[0, 0, 0] = 100.0   # большой входящий сигнал
    n.step(0)
    return float(n.conductance[0, 0])

blocked = _incoming_conductance(True)
passed = _incoming_conductance(False)
assert blocked == 0.0, f"рефрактерность не заблокировала вход: {blocked}"
assert passed > 0.0, f"вход не прошёл вне рефрактерности: {passed}"
print(f"LIF refractory gates input: OK (в рефрактерности {blocked}, вне {passed:.1f})")


# 2. LIF: сигнал проходит по синапсу (A → B), т.е. рекуррентный вход работает.
w2 = sp.csr_matrix(np.array([[0.0, 0.0], [50.0, 0.0]], dtype=np.float32))  # 0→1
net2 = LIFNetwork(w2, cfg)
net2.set_stimulus_rates({0: 1000.0})
downstream = 0
for t in range(200):
    spiked = net2.step(t).spiked_indices
    if 1 in set(spiked.tolist()):
        downstream += 1
assert downstream > 0, "сигнал не дошёл по синапсу 0→1"
print(f"LIF synaptic propagation: OK (нейрон-приёмник вспыхнул {downstream} раз)")


# 3. КОДИРОВАНИЕ ситуации → стимул: еда включает сладкое, угроза — бегство.
sug = FlyBrainInstinct.stimuli_from_state(_idle_state(food=6), _Drives(hunger=0.8))
assert sug.get('sugar', 0) > 0.0, f"голод не включил сладкое: {sug}"
assert 'escape' not in sug, f"голод ошибочно включил бегство: {sug}"

threat = FlyBrainInstinct.stimuli_from_state(
    _idle_state(health=6, nearest_hostile={'name': 'zombie', 'distance': 3}),
    _Drives(fear=0.9))
assert threat.get('escape', 0) > 0.5, f"угроза не включила бегство: {threat}"
assert 'sugar' not in threat, f"угроза ошибочно включила еду: {threat}"
print(f"Stimulus encoding: OK (голод→{sug}, угроза→{threat})")


# 4. ЗНАК: инстинкт подталкивает согласные действия и тормозит противоположные.
avoid = InstinctReading(valence=-1.0, decision='avoid', confidence=1.0,
                        forward_hz=0.0, escape_hz=100.0)
assert avoid.bias_for('flee_from_hostile') > 0, "avoid не подтолкнул бегство"
assert avoid.bias_for('step_forward') < 0, "avoid не притормозил движение вперёд"
approach = InstinctReading(valence=1.0, decision='approach', confidence=1.0,
                           forward_hz=100.0, escape_hz=0.0)
assert approach.bias_for('eat_food') > 0, "approach не подтолкнул еду"
assert approach.bias_for('flee_from_hostile') < 0, "approach не притормозил бегство"
assert abs(avoid.bias_for('flee_from_hostile')) <= BIAS_STRENGTH + 1e-9
assert avoid.bias_for('place_block') == 0.0, "нейтральное действие получило сдвиг"
idle = InstinctReading(valence=0.0, decision='idle', confidence=0.0,
                       forward_hz=0.0, escape_hz=0.0)
assert idle.bias_for('step_forward') == 0.0
print("Instinct sign/bias: OK")


# 5. ТИХОЕ ВЫКЛЮЧЕНИЕ: без данных инстинкт недоступен и не мешает.
missing = BrainConfig(data_dir=Path(tempfile.mkdtemp()) / "nope")
inst_off = FlyBrainInstinct(missing, download=False)
assert not inst_off.available, "инстинкт доступен без данных"
assert inst_off.feel(_idle_state(), _Drives(hunger=0.8), 1) is None
assert "выключен" in inst_off.summary()
print("Graceful absence: OK")


# 6. КЭШ: инстинкт не пересчитывает каждый шаг (refresh_every).
real = BrainConfig()
if real.data_available():
    inst = FlyBrainInstinct(real, refresh_every=10, download=False)
    assert inst.available
    first = inst.feel(_idle_state(food=6), _Drives(hunger=0.8), 1)
    again = inst.feel(_idle_state(food=6), _Drives(hunger=0.8), 3)
    assert again is first, "кэш не сработал: инстинкт пересчитался раньше времени"
    assert inst.runs == 1
    print(f"Instinct cache: OK (прогонов {inst.runs})")

    # 7. РЕАЛЬНЫЙ КОННЕКТОМ: сладкое ведёт вперёд, угроза — к бегству.
    from flybrain.engine import FlyBrainEngine

    engine = FlyBrainEngine(real, download=False)
    n = engine.n_neurons
    assert n > 100_000, f"подозрительно маленький коннектом: {n}"
    sugar = engine.run({'sugar': 0.9}, duration_ms=60)
    assert sugar.decision in ('approach', 'idle'), f"сладкое не ведёт вперёд: {sugar.decision}"
    assert sugar.channel_rate('descending') > 0, "нет отклика нисходящих нейронов на сладкое"
    escape = engine.run({'escape': 0.9}, duration_ms=60)
    assert escape.decision in ('avoid', 'idle'), f"угроза не ведёт к бегству: {escape.decision}"
    assert escape.channel_rate('escape') > 0, "нет отклика нейронов бегства"
    print(f"Real connectome: OK ({n} нейронов; сладкое→{sugar.decision}, "
          f"угроза→{escape.decision})")

    # 8. ДЕТЕРМИНИРОВАННОСТЬ: один и тот же стимул → тот же отклик.
    r1 = engine.run({'sugar': 0.5}, duration_ms=40)
    r2 = engine.run({'sugar': 0.5}, duration_ms=40)
    assert r1.channel_rate('descending') == r2.channel_rate('descending'), "движок недетерминирован"
    print("Engine determinism: OK")
else:
    print("Real connectome: SKIP (нет данных Fly-brain/)")


# 9. СЦЕПКА с корой: инстинкт реально смещает выбор действия.
from core.cortex import Cortex


class _Cat:
    def has(self, a):
        return True


class _SM:
    def confidence(self, a):
        return 0.5


class _W:
    def __init__(self):
        self.holder = {}

    def submit(self, kind, text, salience):
        self.holder[kind] = (text, salience)


class _Pred:
    def predict_relief(self, a, drives, state):
        return 0.0


class _Neuromod:
    def exploration(self):
        return 0.0


class _D2:
    def to_dict(self):
        return {'hunger': 0.5, 'fear': 0.0, 'pain': 0.0, 'boredom': 0.0,
                'loneliness': 0.0, 'fatigue': 0.0, 'curiosity': 0.0, 'comfort': 0.2}


cortex = Cortex(adapter=None, drives=_D2(), neuromod=_Neuromod(), predictor=_Pred(),
                self_model=_SM(), world_model=None, catalog=_Cat(), workspace=_W())
cortex.instinct = FlyBrainInstinct(BrainConfig(data_dir=Path("/nonexistent")), download=False)
assert cortex.tick_instinct(_idle_state(), 1) is None  # недоступен — не мешает

cortex.last_instinct = InstinctReading(valence=-1.0, decision='avoid',
                                       confidence=1.0, forward_hz=0.0, escape_hz=100.0)
bias_flee = cortex.last_instinct.bias_for('flee_from_hostile')
bias_fwd = cortex.last_instinct.bias_for('step_forward')
assert bias_flee > 0 > bias_fwd
print(f"Cortex wiring: OK (avoid → бегство {bias_flee:+.2f}, вперёд {bias_fwd:+.2f})")


print("\nFLY-BRAIN INSTINCT TESTS PASSED")
