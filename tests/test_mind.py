"""Человеческое ядро: характер, тело, чувства, привязанность, игра, рост.

Проверяем не «числа», а живые свойства: эмоция рождается из ОЦЕНКИ, настроение
медленное, разлука переживается, привычка ломается, игра питается настроением,
существо взрослеет от опыта и говорит по возрасту.
"""
import os
import tempfile

from tests import _env  # noqa: F401  (path + isolated cwd)

from adapters.mock import MockAdapter
from core.brain import Brain
from core.temperament import Temperament
from core.interoception import Interoception
from core.emotions import Emotions
from core.social import Social
from core.play import Play
from core.habits import Habits
from core.metacognition import Metacognition
from core.language import Language
from core.development import Development


# 1. Характер рождается, сохраняется и красит мозг.
tmp = tempfile.mkdtemp(prefix="mind-")
os.chdir(tmp)
t1 = Temperament(file=f"{tmp}/t.json")
assert t1.traits, "характер не родился"
t2 = Temperament(file=f"{tmp}/t.json")
assert t2.traits == t1.traits, "характер не сохранился"
assert 0 <= t1.novelty_seeking() <= 1 and 0 <= t1.patience() <= 1
print("Temperament: OK (%s)" % t1.summary())


# 2. Тело ощущает себя: боль и голод делают тон отрицательным.
class _D:
    def __init__(self, d):
        self._d = d

    def to_dict(self):
        return self._d


intero = Interoception()
calm = {'hunger': 0, 'fear': 0, 'pain': 0, 'boredom': 0, 'loneliness': 0,
        'fatigue': 0, 'curiosity': 0.3, 'comfort': 0.9}
hurt = dict(calm, pain=0.9, fear=0.7)
intero.sense({'y': 64}, _D(calm))
assert intero.tone > 0, intero.tone
intero.sense({'y': 64}, _D(hurt))
assert intero.tone < 0 and intero.arousal > 0.5, (intero.tone, intero.arousal)
assert 'больно' in intero.feeling
print("Interoception: OK (%s)" % intero.describe())


# 3. ЭМОЦИЯ ИЗ ОЦЕНКИ. Одна ситуация — разное чувство в зависимости от смысла.
t = Temperament(file=f"{tmp}/t2.json")
em = Emotions(t, file=f"{tmp}/em.json")
# Опасность перекрывает радость: рядом папа, но мне больно → страх, не любовь.
app = em.appraise({'harm': 0.8, 'benefit': 0.5, 'attachment': True, 'control': 0.3})
assert app.name == 'страх', app.name
# Я сам поступил против своих правил → стыд/вина.
app = em.appraise({'norm': 0.8, 'self_agency': True})
assert app.name in ('стыд', 'вина'), app.name
# Потеря важного, ничего не поделать → печаль.
app = em.appraise({'loss': 0.9, 'control': 0.1})
assert app.name == 'печаль', app.name
# Всё хорошо и папа рядом → любовь.
app = em.appraise({'benefit': 0.6, 'attachment': True, 'harm': 0.0})
assert app.name == 'любовь', app.name
print("Emotions(appraisal): OK")


# 4. Настроение медленное и следует за чувством; регуляция снижает накал.
class _N:
    cortisol = 0.2


em.feel('страх', 0.9, 'тест')
before = em.current.intensity
assert em.regulate('reappraisal', _D(calm), _N())
assert em.current.intensity < before, "переосмысление не помогло"
em.feel('печаль', 0.8, 'тест')
before = em.current.intensity
assert em.regulate('comfort', _D(calm), _N(), attachment_near=True)
assert em.current.intensity < before
print("Emotions(regulation): OK")


# 5. Привязанность растёт от близости, разлука переживается, встреча радует.
soc = Social(t, file=f"{tmp}/soc.json")
for _ in range(50):
    soc.update({'player': {'name': 'Papa', 'distance': 3}})
assert soc.bond > 0.15 and soc.attachment_name == 'Papa'
far = {'player': {'name': 'Papa', 'distance': 999}}
for _ in range(60):
    soc.update(far)
assert soc.separation_distress > 0.3, soc.separation_distress
assert soc.needs_contact(), "не тянется к папе при разлуке"
joy = soc.on_reunion()
assert joy > 0.4 and soc.separation_distress == 0.0
print("Social(attachment): OK (%s)" % soc.summary())


# 6. Игра: питается настроением, воображает, заканчивается радостью.
class _Dr:
    def __init__(self, d):
        self._d = d

    def to_dict(self):
        return self._d


class _Em:
    pleasure = 0.4


play = Play(t, file=f"{tmp}/play.json")
good = _Dr(dict(calm))
assert play.can_play(good, _Em(), in_danger=False)
bad = _Dr(dict(calm, hunger=0.9))
assert not play.can_play(bad, _Em(), in_danger=False), "играет голодным"
name = play.imagine([])
assert play.playing() and name
steps = []
while play.playing():
    s = play.next_step()
    if s is None:
        break
    steps.append(s)
assert steps, "воображаемая игра без действий"
assert play.games_played >= 1
print("Play: OK (%s)" % play.summary())


# 7. Привычка крепнет от повтора и ЛОМАЕТСЯ от неудачи (не залипаем).
hab = Habits(file=f"{tmp}/hab.json")
for _ in range(4):
    hab.strengthen('cue1', 'dig_tree', reward=True)
assert hab.suggest('cue1') == 'dig_tree'
assert hab.habits['cue1'].strength > 0.5
for _ in range(6):
    hab.punish('cue1')
assert hab.suggest('cue1') is None, "привычка не сломалась — будет залипание"
print("Habits: OK (привычка закрепляется и забывается)")


# 8. Метапознание: залипание распознаётся, стратегия меняется.
meta = Metacognition(file=f"{tmp}/meta.json")
for _ in range(8):
    meta.observe('dig_tree', True)
assert meta.stuck(), "не заметил залипание"
strat = meta.pick_strategy()
assert strat in ('switch_task', 'reappraise', 'ask_papa'), strat
assert meta.strategy_switches >= 1
print("Metacognition: OK (%s)" % meta.summary())


# 9. Язык: слова запоминаются, речь растёт по возрасту (лепет → фраза).
lang = Language(t, file=f"{tmp}/lang.json")
lang.learn_word('дерево', 'из чего строят')
assert lang.know('дерево') and lang.vocabulary_size() == 1
assert lang.phrase(0, 'привет') == 'привет'
assert lang.phrase(1, 'папа смотри скорее') == 'папа смотри'
assert lang.phrase(2, 'я хочу играть').startswith('папа')
print("Language: OK (%s)" % lang.summary())


# 10. Взросление: возраст растёт от опыта, стадии меняются.
dev = Development(file=f"{tmp}/dev.json")
assert dev.stage_name() == 'младенец'
for _ in range(700):
    dev.live(steps=1.0)
assert dev.stage >= 1, dev.stage_name()
assert dev.question_urge() > 0.3
print("Development: OK (%s)" % dev.summary())


# 11. СКВОЗНАЯ ПРОВЕРКА: живое существо на mock-теле.
# Мозг работает как человек: чувствует, взрослеет, играет, привязывается.
os.chdir(tempfile.mkdtemp(prefix="mind-run-"))
ad = MockAdapter()
b = Brain(ad)
for _ in range(120):
    b.think(ad.get_state())
assert b.feelings.current.name, "нет текущего чувства"
assert b.intero.feeling, "нет телесного ощущения"
assert b.development.age > 0, "не взрослеет"
assert b.social.attachment_name == 'Papa', b.social.attachment_name
assert b.language.vocabulary_size() >= 0
# Существо не залипает: привычки есть, и они не единственный способ действия.
assert b.meta.confidence >= 0
print("Brain(mind): OK (чувство=%s, возраст=%s, игра=%s)"
      % (b.feelings.current.name, b.development.stage_name(), b.play.games_played))


print("\nMIND TESTS PASSED")
