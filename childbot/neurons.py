"""Known FAFB neurons Childbot uses to sense and act.

Root ids are from the FlyWire FAFB v783 release and were checked against the
public Codex cell-type annotation
(``codex/data/fafb/783/consolidated_cell_types.csv.gz``):

* ``SUGAR_GRNS`` - the 21 neurons fly-brain drives in its ``sugar`` experiment
  (annotated ``LB3``, sweet-sensing receptor neurons).
* ``P9_DESCENDING`` - the two ``DNp09`` descending neurons fly-brain drives in
  its ``p9`` experiment; activity is a forward-walking command.
* ``ESCAPE_DESCENDING`` - the two ``DNp01`` giant-fibre neurons; activity is the
  classic escape/avoidance command.

If an id is absent from the loaded connectome (for example under
``subset_size``) the corresponding channel is reported as unavailable rather
than crashing the simulation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NeuronChannel:
    """A named group of FlyWire neurons driving one behaviour."""

    name: str
    description: str
    root_ids: tuple[int, ...]


# Sugar gustatory receptor neurons (from fly-brain EXPERIMENTS['sugar']).
SUGAR_GRNS = NeuronChannel(
    name="sugar",
    description="Sugar gustatory receptor neurons; high rate = sweet taste.",
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

# P9 (DNp09) descending neurons: forward-walking command (fly-brain EXPERIMENTS['p9']).
P9_DESCENDING = NeuronChannel(
    name="walk",
    description="DNp09 (P9) descending neurons; activity drives forward walking.",
    root_ids=(
        720575940627652358,  # DNp09 left
        720575940635872101,  # DNp09 right
    ),
)

# DNp01 giant-fibre neurons: the classic escape / avoidance command.
ESCAPE_DESCENDING = NeuronChannel(
    name="escape",
    description="DNp01 giant-fibre descending neurons; activity = threat response.",
    root_ids=(
        720575940622838154,  # DNp01 left
        720575940632499757,  # DNp01 right
    ),
)

CHANNELS: tuple[NeuronChannel, ...] = (SUGAR_GRNS, P9_DESCENDING, ESCAPE_DESCENDING)

# Which channels Childbot can stimulate, and the default drive (Hz).
STIMULUS_CHANNELS: dict[str, NeuronChannel] = {
    "sugar": SUGAR_GRNS,
    "walk": P9_DESCENDING,
    "escape": ESCAPE_DESCENDING,
}

# Which channels Childbot reads to form a decision.
READOUT_CHANNELS: dict[str, NeuronChannel] = {
    "walk": P9_DESCENDING,
    "escape": ESCAPE_DESCENDING,
}

DEFAULT_STIM_RATE_HZ = 200.0


def resolve_indices(channels, index_of) -> tuple[list[int], list[int]]:
    """Split channel root ids into known indices and unknown ids.

    ``index_of`` maps a FlyWire id to a matrix index and raises ``KeyError`` for
    ids the current connectome does not contain.
    """
    known: list[int] = []
    unknown: list[int] = []
    for channel in channels:
        for root_id in channel.root_ids:
            try:
                known.append(index_of(int(root_id)))
            except KeyError:
                unknown.append(int(root_id))
    return known, unknown
