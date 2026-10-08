"""Речь: команды, приветствия, разговор, имитация, плейсхолдеры LLM."""
from tests import _env  # noqa: F401  (path + isolated cwd)

from adapters.mock import MockAdapter
from core.actions import ActionsCatalog
from core.adaptive_intent import AdaptiveIntent
from core.brain import Brain
from core.goals import GoalManager, MAX_HISTORY
from core.self_model import SelfModel


# 1. Команда-подсказка → цель
ad = MockAdapter()
b = Brain(ad)
state = ad.get_state()
b.respond_to_message({'name': 'Papa', 'text': 'подойди ко мне'}, state)
assert b.goals.current is not None, "команда не распознана"
assert b.goals.current.action == 'go_to_player', b.goals.current.action
print("Команда: OK ->", b.goals.current.action)

# 2. Имитация: повторить последнее действие папы
ad._player_actions.append({'player': 'Papa', 'action': 'swing',
                           'x': 5, 'y': 64, 'z': 5, 'yaw': 0, 'pitch': 0,
                           'target': {'name': 'oak_log', 'x': 5, 'y': 64, 'z': 6},
                           'time': 0})
assert b.imitate_player(), "имитация не сработала"
assert 'mimic_last' in ad._actions_seen, "mimic_last не вызван"
print("Имитация: OK (запомнил oak_log в мире)")

# 3. Разговор (без LLM) не падает и не ставит цель
b.goals.current = None
b.respond_to_message({'name': 'Papa', 'text': 'ты молодец'}, state)
assert b.goals.current is None, "разговор поставил цель"
print("Разговор: OK (цель не поставлена)")

# 4. Полный think() с сообщением в очереди — команда выполняется
ad.push_message('Papa', 'прыгни')
b.think(ad.get_state())
assert 'jump_once' in ad._actions_seen, ad._actions_seen[-5:]
print("Цикл с сообщением: OK -> jump_once")


# 5. LLM-плейсхолдеры не должны становиться ответом
ai = AdaptiveIntent(ActionsCatalog(MockAdapter()))
assert ai._clean_say('<фраза ребёнка>') is None
assert ai._clean_say('{say}') is None
assert ai._clean_say('  <текст>  ') is None
assert ai._clean_say('Я тебя люблю, папа!') == 'Я тебя люблю, папа!'
assert ai._clean_say('Hello world test') is None
print("Placeholder filter: OK")

# 6. Приветствие — разговор, а не команда
assert ai._is_chatter('Привет! Я тут.')
assert ai._is_chatter('привет')
assert ai._is_chatter('как дела?')
assert not ai._is_chatter('иди сюда')
assert not ai._is_chatter('построй дом')
print("Greeting=chatter: OK")

# 7. История целей ограничена и сохраняется
import os
import tempfile
tmp = tempfile.mktemp(suffix='.json')
gm = GoalManager(file=tmp)
for i in range(MAX_HISTORY + 50):
    gm.set_goal(f'цель {i}', 'step_forward')
    gm.complete(True, {'ok': True})
assert len(gm.history) <= MAX_HISTORY, len(gm.history)
gm2 = GoalManager(file=tmp)
assert len(gm2.history) == len(gm.history) and gm2.history
print("Goals cap+persist: OK (%d)" % len(gm.history))
os.remove(tmp)

# 8. Автобиография без повторов подряд
sm = SelfModel(MockAdapter())
sm.add_narrative("нашёл новое место")
sm.add_narrative("нашёл новое место")
sm.add_narrative("нашёл новое место")
assert len([x for x in sm.narrative if x['event'] == "нашёл новое место"]) == 1
sm.add_narrative("увидел папу")
sm.add_narrative("нашёл новое место")
assert len([x for x in sm.narrative if x['event'] == "нашёл новое место"]) == 2
print("Narrative dedupe: OK")


print("\nSPEECH/IMITATION TESTS PASSED")
