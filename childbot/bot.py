"""Childbot: the agent that turns brain readings into replies.

The bot keeps a small associative memory so the same sensory situation is not
re-simulated every time, and so it can report what it has learned. The brain
makes the decision; the bot handles language, memory, and the reply.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from childbot.brain import BrainReading, FlyBrain, FlyBrainRemote
from childbot.bridge import FlyBrainBridge
from childbot.config import BrainConfig


def build_brain(config: BrainConfig | None = None, *, download: bool = True):
    """Choose a brain backend from the config, in priority order.

    1. ``CHILDBOT_FLYBRAIN_HOME`` -> drive an installed fly-brain checkout.
    2. ``CHILDBOT_FLYBRAIN_URL``  -> talk to a running fly-brain service.
    3. Otherwise                  -> run the local LIF engine.
    """
    config = config or BrainConfig()
    if config.flybrain_home:
        return FlyBrainBridge(home=config.flybrain_home, config=config)
    if config.flybrain_url:
        return FlyBrainRemote(config.flybrain_url)
    return FlyBrain(config, download=download)


@dataclass
class MemoryEntry:
    situation: str
    decision: str
    confidence: float
    hits: int = 1


@dataclass
class Childbot:
    """A fly-brain-driven agent with a small associative memory."""

    brain: object
    config: BrainConfig = field(default_factory=BrainConfig)
    memory_path: Path | None = None
    memory: dict[str, MemoryEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.memory_path and Path(self.memory_path).exists():
            self._load_memory()

    def respond(
        self,
        situation: str,
        *,
        intensity: float = 1.0,
        duration_ms: float = 100.0,
        use_memory: bool = True,
    ) -> dict:
        """Decide how to react to ``situation`` and return a structured reply."""
        key = situation.strip().lower()

        if use_memory and key in self.memory:
            entry = self.memory[key]
            entry.hits += 1
            self._save_memory()
            return {
                "situation": situation,
                "decision": entry.decision,
                "confidence": entry.confidence,
                "source": "memory",
                "hits": entry.hits,
                "reply": self._phrase(entry.decision, situation),
            }

        reading: BrainReading = self.brain.decide(
            situation, intensity=intensity, duration_ms=duration_ms
        )
        self.memory[key] = MemoryEntry(
            situation=situation,
            decision=reading.decision,
            confidence=reading.confidence,
        )
        self._save_memory()

        return {
            "situation": situation,
            "decision": reading.decision,
            "confidence": reading.confidence,
            "source": "brain",
            "channels": {
                name: {"rate_hz": ch.rate_hz, "spikes": ch.spikes}
                for name, ch in reading.channels.items()
            },
            "simulated_ms": reading.simulated_ms,
            "note": reading.note,
            "reply": self._phrase(reading.decision, situation),
        }

    @staticmethod
    def _phrase(decision: str, situation: str) -> str:
        phrases = {
            "approach": f"'{situation}' looks rewarding - moving toward it.",
            "avoid": f"'{situation}' reads as a threat - backing away.",
            "idle": f"'{situation}' produced no strong drive - holding still.",
        }
        return phrases.get(decision, f"'{situation}' -> {decision}")

    def _load_memory(self) -> None:
        raw = json.loads(Path(self.memory_path).read_text())
        self.memory = {
            key: MemoryEntry(**entry) for key, entry in raw.get("entries", {}).items()
        }

    def _save_memory(self) -> None:
        if not self.memory_path:
            return
        path = Path(self.memory_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "entries": {
                        key: {
                            "situation": e.situation,
                            "decision": e.decision,
                            "confidence": e.confidence,
                            "hits": e.hits,
                        }
                        for key, e in self.memory.items()
                    }
                },
                indent=2,
            )
        )
