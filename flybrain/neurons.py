"""Нейроны FAFB, которыми существо «чувствует» и «действует».

Root id — из релиза FlyWire FAFB v783 и сверены с публичной аннотацией Codex:

* ``SUGAR_GRNS`` — 21 нейрон, которые fly-brain стимулирует в опыте ``sugar``
  (тип ``LB3``, вкусовые рецепторы сладкого).
* ``P9_DESCENDING`` — два нисходящих нейрона ``DNp09`` (опыт ``p9`` fly-brain);
  активность = команда идти вперёд.
* ``ESCAPE_DESCENDING`` — два гигантских волокна ``DNp01``; активность =
  врождённая реакция бегства.

Берём только проверяемые каналы: сенсорный вход (сладкое) и нисходящий выход
(ходьба/бегство). Нейроны, которых нет в загруженном коннектоме (например, при
``subset_size``), помечаются недоступными, а не ломают симуляцию.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NeuronChannel:
    """Именованная группа нейронов FlyWire под одно поведение."""

    name: str
    description: str
    root_ids: tuple[int, ...]


# Вкус сладкого (опыт fly-brain EXPERIMENTS['sugar']).
SUGAR_GRNS = NeuronChannel(
    name="sugar",
    description="Вкусовые рецепторы сладкого (LB3); высокая частота = еда.",
    root_ids=(
        720575940624963786,
        720575940630233916,
        720575940637568838,
        720575940638202345,
        720575940617000768,
        720575940630797113,
        720575940632889389,
        720575940621754367,
        720575940621502051,
        720575940640649691,
        720575940639332736,
        720575940616885538,
        720575940639198653,
        720575940639259967,
        720575940617937543,
        720575940632425919,
        720575940633143833,
        720575940612670570,
        720575940628853239,
        720575940629176663,
        720575940611875570,
    ),
)

# Нисходящие DNp09 (P9): команда ходьбы вперёд (опыт fly-brain EXPERIMENTS['p9']).
P9_DESCENDING = NeuronChannel(
    name="walk",
    description="Нисходящие DNp09 (P9); активность ведёт вперёд.",
    root_ids=(
        720575940627652358,  # DNp09 слева
        720575940635872101,  # DNp09 справа
    ),
)

# Гигантские волокна DNp01: врождённая реакция бегства/избегания.
ESCAPE_DESCENDING = NeuronChannel(
    name="escape",
    description="Гигантские волокна DNp01; активность = реакция бегства.",
    root_ids=(
        720575940622838154,  # DNp01 слева
        720575940632499757,  # DNp01 справа
    ),
)

CHANNELS: tuple[NeuronChannel, ...] = (
    SUGAR_GRNS,
    P9_DESCENDING,
    ESCAPE_DESCENDING,
)

# Чем существо может стимулировать мозг, и частота по умолчанию (Гц).
STIMULUS_CHANNELS: dict[str, NeuronChannel] = {
    "sugar": SUGAR_GRNS,
    "walk": P9_DESCENDING,
    "escape": ESCAPE_DESCENDING,
}

DEFAULT_STIM_RATE_HZ = 200.0


def resolve_indices(channels, index_of) -> tuple[list[int], list[int]]:
    """Разделить root id каналов на известные индексы и отсутствующие id."""
    known: list[int] = []
    unknown: list[int] = []
    for channel in channels:
        for root_id in channel.root_ids:
            try:
                known.append(index_of(int(root_id)))
            except KeyError:
                unknown.append(int(root_id))
    return known, unknown
