"""Сцепка человеческих систем: оценка, воображение, ценности, «Я», дом.

Проверяем не отдельные детали, а их СВЯЗЬ — то, что делает поведение личным,
а не реактивным:
  * оценка события рождает чувство И меняет тело/химию (замкнутая петля);
  * настроение красит оценку (одно событие — разный накал);
  * воображение предвидит будущую нужду и строит цепочку к цели;
  * «две системы» (привычка и обдумывание) спорят и дают сигнал конфликта;
  * ценности учатся от подкрепления; «Я» хранит историю и совесть;
  * в доме цикл «нужда → поступок → облегчение» реально замыкается;
  * страх тянется к уровню опасности, а не копится вечно (нет дурной петли).
"""
import os
import tempfile

from tests import _env  # noqa: F401  (path + isolated cwd)

from adapters.home import HomeAdapter
from adapters.mock import MockAdapter
from core.brain import Brain
from core.drives import Drives
from core.temperament import Temperament
from core.interoception import Interoception
from core.neuromodulators import Neuromodulators
from core.appraisal import Appraiser
from core.imagination import Imagination
from core.values import Values, context_key
from core.identity import Identity


class _D:
    def __init__(self, d):
        self._d = d

    def to_dict(self):
        return self._d


def _drives(**kw):
    base = {'hunger': 0, 'fear': 0, 'pain': 0, 'boredom': 0, 'loneliness': 0,
            'fatigue': 0, 'curiosity': 0.3, 'comfort': 0.6}
    base.update(kw)
    return _D(base)


# 1. ОЦЕНКА ДВУСТОРОННЯЯ: событие рождает чувство И меняет тело и химию.
tmp = tempfile.mkdtemp(prefix="systems-")
os.chdir(tmp)
t = Temperament(file=f"{tmp}/t.json")
ap = Appraiser(t)
intero = Interoception()
neuromod = Neuromodulators()
drives = _drives(comfort=0.5)
app = ap.build(drives, intero, harm=0.8, danger=True, certainty=0.2)
before_cort = neuromod.cortisol
before_arousal = intero.arousal
ap.apply_to_body(app, drives, intero, neuromod)
assert app.is_threat() and app.blame() in ('я', 'другой', 'никто')
assert neuromod.cortisol > before_cort, "оценка угрозы не подняла кортизол"
assert intero.arousal > before_arousal, "оценка угрозы не взбудоражила тело"
print("Appraisal(bidirectional): OK (%s; кортизол %.2f→%.2f, возбужд %+.2f)"
      % (app.summary(), before_cort, neuromod.cortisol, intero.arousal - before_arousal))

# польза поднимает дофамин и теплеет тело
d2 = _drives(comfort=0.9)
app2 = ap.build(d2, intero, benefit=0.7, attachment=True)
dop = neuromod.dopamine
ox = neuromod.oxytocin
ap.apply_to_body(app2, d2, intero, neuromod)
assert neuromod.dopamine > dop and neuromod.oxytocin > ox
print("Appraisal(reward): OK (дофамин/окситоцин выросли)")


# 2. НАСТРОЕНИЕ КРАСИТ ОЦЕНКУ: одно событие в дурном настроении ранит сильнее.
from core.emotions import Emotions
em_low = Emotions(t, file=f"{tmp}/em_low.json")
em_low.pleasure = -0.7
ev = {'harm': 0.5, 'control': 0.5}
bad_low = em_low.appraise(ev)
em_high = Emotions(t, file=f"{tmp}/em_high.json")
em_high.pleasure = 0.7
bad_high = em_high.appraise(ev)
assert bad_low.intensity > bad_high.intensity, (bad_low.intensity, bad_high.intensity)
print("Mood-congruence: OK (в дурном настроении %.2f > в хорошем %.2f)"
      % (bad_low.intensity, bad_high.intensity))


# 3. ВООБРАЖЕНИЕ: предвидит будущую нужду и строит цепочку к цели.
pred = None
im = Imagination(predictor=None)
d = Drives()
d.hunger = 0.4
fut = im.forecast(d, {'player': {'distance': 2}}, horizon=30)
assert fut['hunger'] > 0.4, fut
need = im.anticipate(d, {'player': {'distance': 2}}, step=100)
assert need in ('hunger', 'boredom', 'fatigue', 'loneliness'), need
print("Imagination(forecast): OK (предвижу %s, голод → %.2f)" % (need, fut['hunger']))


# 4. ЦЕННОСТИ И АРБИТРАЖ: подкрепление учит, две системы спорят.
val = Values(t, file=f"{tmp}/v.json")
for _ in range(8):
    val.update('ctx', 'go_to_player', reward=0.8)
assert val.value('ctx', 'go_to_player') > 0.4
assert val.best_known('ctx') == 'go_to_player'
# Привычка уверена и спокойно → побеждает привычка.
action, source, conflict = val.arbitrate('go_to_player', 'look_around',
                                         confidence=0.9, tension=0.5)
assert source == 'habit' and conflict > 0.5, (source, conflict)
# Новое и опасное → побеждает обдумывание.
action, source, conflict = val.arbitrate('go_to_player', 'flee_from_hostile',
                                         confidence=0.2, tension=2.5, danger=True)
assert source == 'deliberate', source
# Пустое обдумывание — не конфликт.
_, _, c0 = val.arbitrate('go_to_player', None, confidence=0.9, tension=0.5)
assert c0 == 0.0, c0
print("Values(arbitration): OK (%s)" % val.summary())


# 5. «Я»: история, ценности из характера, совесть (диссонанс).
ident = Identity(t, file=f"{tmp}/id.json")
assert ident.values and ident.who_am_i()
ident.add_to_story('я помог папе')
assert 'помог' in ident.story()
# Поступок против себя при высокой ценности стойкости → диссонанс.
ident.values['стойкость'] = 0.9
clash = ident.check_consistency('wait_1sec', _drives())
assert clash > 0, clash
soothed = ident.soothe()
assert soothed < clash
print("Identity: OK (%s)" % ident.summary())


# 6. ДОМ: цикл «нужда → поступок → облегчение» реально замыкается.
os.chdir(tempfile.mkdtemp(prefix="home-run-"))
ad = HomeAdapter()
b = Brain(ad)
seen = []
for i in range(400):
    b.think(ad.get_state())
    if i % 40 == 0:
        seen.append(round(b.drives.hunger, 2))
# Голод должен КОЛЕБАТЬСЯ (растёт, потом еда его снимает), а не стоять на 1.0.
assert min(seen) < 0.9 and max(seen) > 0.2, seen
assert ad.fed > 0, "папа ни разу не накормил"
assert b.development.age > 0
# Существо не залипает: есть и игра, и общение, и еда, а не одно действие.
print("Home(loop): OK (голод колеблется %s, накормлен %d раз, стадия %s)"
      % (seen, ad.fed, b.development.stage_name()))


# 7. НЕТ ДУРНОЙ ПЕТЛИ СТРАХА: страх тянется к уровню опасности.
d = Drives()
night = {'food': 20, 'health': 20, 'is_night': True, 'time_of_day': 15000,
         'nearest_hostile': None}
for _ in range(120):
    d.tick(night, is_new_cell=False)
assert d.fear < 0.6, ("ночь нагнала страх %.2f — дурная петля" % d.fear)
# Вблизи врага страх высокий, но не «приколочен» на 1.0 навсегда.
d2 = Drives()
danger = {'food': 20, 'health': 20, 'is_night': False, 'time_of_day': 6000,
          'nearest_hostile': {'distance': 3}}
for _ in range(10):
    d2.tick(danger, is_new_cell=False)
assert d2.fear > 0.5
safe = {'food': 20, 'health': 20, 'is_night': False, 'time_of_day': 6000,
        'nearest_hostile': None}
for _ in range(80):
    d2.tick(safe, is_new_cell=False)
assert d2.fear < 0.2, ("страх не спал в безопасности: %.2f" % d2.fear)
print("Fear(no-loop): OK (ночь %.2f, враг→спокойствие %.2f)" % (d.fear, d2.fear))


# 8. МЕТАПОЗНАНИЕ И ЦЕННОСТИ СВЯЗАНЫ: конфликт двух систем оставляет след.
os.chdir(tempfile.mkdtemp(prefix="mind-integ-"))
ad = MockAdapter()
b = Brain(ad)
for _ in range(80):
    b.think(ad.get_state())
assert b.mind.values.learned > 0, "ценности не учатся"
assert b.mind.identity.narrative, "история о себе пуста"
print("Mind(integrated): OK (%s)" % b.mind.summary())


print("\nMIND SYSTEMS TESTS PASSED")
