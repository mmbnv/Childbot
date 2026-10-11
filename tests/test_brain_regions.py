"""Распределённый мозг и субъективный приор — по трём работам 2025–2026.

Проверяем то, что отличает живое решение от «одной коробки»:
  * области ГЕТЕРОГЕННЫ (у каждой своя возбудимость) — PNAS 2026;
  * связи ДВУНАПРАВЛЕННЫ (сенсорные зоны «видят» ожидания) — PNAS про S1;
  * решение РАСПРЕДЕЛЕНО: голос областей меняет выбор действия — IBL 2025;
  * есть RAMP (накопление свидетельства) и адаптация — IBL 2025;
  * перегруженная область уходит в ЛОКАЛЬНЫЙ сон — PNAS 2026;
  * субъективный приор помнит ~6 прошлых исходов и смещает выбор — IBL 2025.
"""
import os

from tests import _env  # noqa: F401  (path + isolated cwd)

from core.brain_regions import BrainRegions, CONNECTIVITY
from core.prior import Prior
from core.temperament import Temperament

# 1. ГЕТЕРОГЕННОСТЬ: области различаются по возбудимости (не однородный шум).
br = BrainRegions(Temperament())
ex = {n: round(r.excitability(), 3) for n, r in br.regions.items()}
assert len(set(ex.values())) > 1, f"области одинаковы: {ex}"
print(f"Heterogeneity: OK ({ex})")

# 2. ДВУНАПРАВЛЕННОСТЬ: сенсор ↔ ассоциация ↔ мотор (обратная связь, PNAS).
assert 'association' in CONNECTIVITY['sensory']
assert 'sensory' in CONNECTIVITY['association']   # нисходящая связь
assert 'motor' in CONNECTIVITY['association']
assert 'association' in CONNECTIVITY['motor']
print("Bidirectional connectivity: OK")

# 3. RAMP: свидетельство к решению накапливается, затем адаптация его гасит.
br2 = BrainRegions(Temperament())
for _ in range(12):
    br2.tick({'stimulus': 0.8, 'urgency': 0.8}, reward=0.8)
peak = br2.ramp
assert peak > 0.2, f"ramp не накопился: {peak}"
for _ in range(60):
    br2.tick({'stimulus': 0.8, 'urgency': 0.8}, reward=0.8)
assert br2.regions['motor'].adaptation > 0.0
assert br2.ramp < peak, f"нет адаптации: {peak} -> {br2.ramp}"
print(f"Ramp+adaptation: OK (пик {peak:.2f} -> {br2.ramp:.2f})")

# 4. РАСПРЕДЕЛЁННОЕ ГОЛОСОВАНИЕ: разные действия получают разный вклад.
br3 = BrainRegions(Temperament())
for _ in range(40):
    br3.tick({'stimulus': 0.9, 'urgency': 0.9}, reward=0.9)
d = {'hunger': 0.2, 'fear': 0.2, 'pain': 0.0, 'boredom': 0.1,
     'loneliness': 0.1, 'fatigue': 0.0, 'curiosity': 0.5, 'comfort': 0.2}
gather = br3.vote('dig_tree', d, {})
flee = br3.vote('flee_from_hostile', d, {})
assert gather > 0.0 and flee > 0.0
assert abs(gather - flee) > 1e-6, "области голосуют одинаково — это не распределённо"
print(f"Distributed vote: OK (gather={gather:.3f}, flee={flee:.3f})")

# 5. ЛОКАЛЬНЫЙ СОН: перегруженная область засыпает и просыпается после отдыха.
br4 = BrainRegions(Temperament())
for _ in range(400):
    br4.tick({'stimulus': 1.0, 'urgency': 1.0}, reward=1.0)
assert br4.local_sleeps > 0, "локальный сон ни разу не возник"
for _ in range(400):
    br4.tick({'stimulus': 0.0, 'urgency': 0.0}, reward=0.0)
assert any(not r.asleep for r in br4.regions.values())
print(f"Local sleep: OK (срабатываний {br4.local_sleeps})")

# 6. ПРИОР учится на исходах и смещает ожидание в знакомой ситуации.
pf = "/tmp/_test_prior.json"
if os.path.exists(pf):
    os.remove(pf)
p = Prior(file=pf)
ctx = "hunger|спокойно|один|день"
for _ in range(8):
    p.observe(ctx, 'eat_food', 1.0)
assert p.predict(ctx, 'eat_food') > 0.5
assert p.predict(ctx, 'jump_forward') == 0.0
assert p.context_prior(ctx) > 0.3
print(f"Prior learns+biases: OK (eat_food={p.predict(ctx,'eat_food'):.2f})")

# 7. ОКНО ПРИОРА: помним ограниченное число исходов (~6), как в IBL 2025.
p2 = Prior(file="/tmp/_test_prior2.json")
p2.beliefs, p2.history = {}, {}
for i in range(20):
    p2.observe("c", 'a', 1.0 if i % 2 == 0 else -1.0)
assert len(p2.history["c"]) <= Prior.WINDOW
print(f"Prior window: OK ({len(p2.history['c'])} <= {Prior.WINDOW})")

# 8. ПРИОР переживает перезапуск (ожидания мира сохраняются).
pf3 = "/tmp/_test_prior3.json"
if os.path.exists(pf3):
    os.remove(pf3)
p3 = Prior(file=pf3)
for _ in range(6):
    p3.observe("ctx", "act", 0.9)
p3.save()
q = Prior(file=pf3)
assert q.predict("ctx", "act") > 0.5
assert q.updates == p3.updates
print("Prior persistence: OK")


print("\nBRAIN REGIONS TESTS PASSED")
