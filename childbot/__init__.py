"""Childbot: an agent whose decisions are driven by a fly-brain connectome model.

The heavy *Drosophila* brain emulation lives in the separate ``fly-brain``
project (https://github.com/eonsystemspbc/fly-brain). This package connects
Childbot to that model in three ways:

* :class:`childbot.brain.FlyBrain` runs the same leaky integrate-and-fire (LIF)
  network locally, straight over the public FlyWire FAFB connectome.
* :class:`childbot.bridge.FlyBrainBridge` drives an installed ``fly-brain``
  checkout and reads back its spike output.
* :class:`childbot.brain.FlyBrainRemote` talks to a running fly-brain service.

See ``README.md`` for setup and the ``python -m childbot`` CLI.
"""

from childbot.bot import Childbot
from childbot.brain import FlyBrain, FlyBrainRemote
from childbot.bridge import FlyBrainBridge
from childbot.config import BrainConfig
from childbot.connectome import Connectome

__all__ = [
    "BrainConfig",
    "Childbot",
    "Connectome",
    "FlyBrain",
    "FlyBrainBridge",
    "FlyBrainRemote",
]

__version__ = "0.1.0"
