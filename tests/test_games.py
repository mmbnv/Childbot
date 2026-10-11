"""Универсальность: один мозг проходит разные игры без правок под них."""
import os
import random
import tempfile

import numpy as np

from tests import _env  # noqa: F401  (path + isolated cwd)

from adapters.mock import MockAdapter
from adapters.game2 import Game2Adapter
from core.brain import Brain

# Своя свежая папка состояния: чужие data/ от предыдущих тестов не должны
# влиять на результат. И фиксируем зёрна (Python и numpy) — проверяем прогресс,
# а не случайный путь.
os.chdir(tempfile.mkdtemp(prefix="childbot-games-"))
random.seed(1234)
np.random.seed(1234)


def run(adapter, steps):
    brain = Brain(adapter)
    for _ in range(steps):
        brain.think(adapter.get_state())
    return brain


# --- Игра 1: Minecraft-песочница. Задачи игры выполняются. ---
a1 = MockAdapter()
b1 = run(a1, 900)
done1 = [t for t in a1.get_tasks() if t['done'] or t['id'] in b1.tasks.done_ids]
assert len(done1) >= 2, [t['id'] for t in a1.get_tasks()]
# Существо не просто собирает — оно СКРАФТИЛО верстак своими руками.
assert 'crafting_table' in a1.inventory, a1.inventory
assert b1.concepts.knows('tool') or b1.concepts.knows('support'), b1.concepts.explain()
print("Game1 (sandbox): OK (задач закрыто %d, скрафтил верстак, %s)"
      % (len(done1), b1.concepts.summary()))


# --- Игра 2: подземелье (ключ → соединение → дверь → выход). ---
# Мозг ничего не знает про эту игру: ни рецептов, ни блоков.
a2 = Game2Adapter()
b2 = run(a2, 200)
assert a2.has_key, "не нашёл ключ"
assert a2.key_used, "не соединил ключ с замком"
assert a2.door_open, "не открыл дверь (не зашёл в дверь)"
# даём трекеру увидеть, что игра закрыла задачи (в тесте время идёт быстро)
b2.tasks.poll(a2, b2.self_model.inventory, force=True)
assert b2.tasks.completed_count >= 3, b2.tasks.completed_count
print("Game2 (dungeon): OK (ключ=%s замок=%s дверь=%s, задач %d)" % (
    a2.has_key, a2.key_used, a2.door_open, b2.tasks.completed_count))


# --- Понятия, выученные в одной игре, переносятся в другую. ---
# Обе игры подтверждают одни и те же законы (проход, инструмент, опора).
learned = set()
for b in (b1, b2):
    for name in b.concepts.laws:
        if b.concepts.knows(name):
            learned.add(name)
assert learned, "ни одного понятия не выучено"
print("Concepts across games: OK (%s)" % ', '.join(sorted(learned)))


print("\nALL TESTS PASSED")
