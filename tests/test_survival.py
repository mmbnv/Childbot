"""Выживание: яма, чёрный список, самоокапывание, анти-повтор."""
from tests import _env  # noqa: F401  (path + isolated cwd)

from adapters.mock import MockAdapter
from core.brain import Brain
from core.cortex import ACTION_POOL


class PitAdapter(MockAdapter):
    """Тело, которое сообщает, что стоит в яме."""
    def __init__(self):
        super().__init__()
        self.pit = True

    def get_state(self):
        s = super().get_state()
        s['in_pit'] = self.pit
        return s


class BlackCellAdapter(MockAdapter):
    """Тело, стоящее в клетке (0,0)."""
    def get_state(self):
        s = super().get_state()
        s['x'] = 0.0
        s['z'] = 0.0
        s['in_pit'] = False
        return s


# 1. В яме — выбирается escape_pit
a = PitAdapter()
b = Brain(a)
a._actions_seen.clear()
b.think(a.get_state())
assert 'escape_pit' in a._actions_seen, a._actions_seen
print("Pit escape: OK ->", a._actions_seen[-1])

# 2. В чёрной клетке — уходит, а не топчется
a = BlackCellAdapter()
b = Brain(a)
b.memory.blacklisted_cells.add((0, 0))
a._actions_seen.clear()
b.think(a.get_state())
last = a._actions_seen[-1]
assert last in ('go_to_player', 'step_forward'), a._actions_seen
print("Blacklist leave: OK ->", last)

# 3. Свободный выбор никогда не копает под собой и не зависает
assert 'dig_down' not in ACTION_POOL
assert 'stay_here' not in ACTION_POOL
assert 'wait_1sec' not in ACTION_POOL
print("Pool: OK -> dig_down/stay_here/wait_1sec исключены")

# 4. Анти-повтор: одно действие не выбирается три раза подряд
a = MockAdapter()
b = Brain(a)
seq = [b.cortex.choose_action(a.get_state()) for _ in range(30)]
for i in range(2, len(seq)):
    assert not (seq[i] == seq[i - 1] == seq[i - 2]), (i, seq[i - 2:i + 1])
print("Anti-repeat: OK -> нет трёх одинаковых подряд")


print("\nSURVIVAL TESTS PASSED")
