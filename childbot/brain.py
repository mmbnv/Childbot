"""The Childbot brain: stimulus encoding, simulation, and decision readout.

``FlyBrain`` is the local engine. It owns a :class:`~childbot.connectome.Connectome`
and a :class:`~childbot.lif.LIFNetwork`, encodes a situation as Poisson stimulus
rates on known sensory neurons, runs the network for a short window, and reads
the response of descending (output) neurons.

``FlyBrainRemote`` presents the same ``decide`` interface but delegates to a
running fly-brain service over HTTP (see :mod:`childbot.service`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from childbot.celltypes import CellTypeIndex
from childbot.config import BrainConfig
from childbot.connectome import Connectome
from childbot.lif import LIFNetwork
from childbot.neurons import (
    DEFAULT_STIM_RATE_HZ,
    READOUT_CHANNELS,
    STIMULUS_CHANNELS,
    resolve_indices,
)


@dataclass
class ChannelReading:
    """Spike-rate response of one readout channel."""

    name: str
    rate_hz: float
    spikes: int


@dataclass
class BrainReading:
    """Result of one decision cycle."""

    decision: str
    confidence: float
    channels: dict[str, ChannelReading] = field(default_factory=dict)
    simulated_ms: float = 0.0
    note: str = ""

    def channel_rate(self, name: str) -> float:
        reading = self.channels.get(name)
        return reading.rate_hz if reading else 0.0


class FlyBrain:
    """Local fly-brain LIF engine driven by the FlyWire FAFB connectome.

    Decisions are read from the whole population of descending neurons (cell
    types beginning with ``DN``), which is how the brain actually commands the
    body. The rate on the *escape* giant-fibre neurons (``DNp01``) versus the
    remaining descending neurons decides between avoiding and approaching.
    """

    def __init__(
        self,
        config: BrainConfig | None = None,
        *,
        connectome: Connectome | None = None,
        cell_types: CellTypeIndex | None = None,
        download: bool = True,
    ):
        self.config = config or BrainConfig()
        self.connectome = connectome or Connectome.load(
            self.config,
            download=download,
            subset_size=self.config.subset_size,
        )
        self.network = LIFNetwork(self.connectome.weights, self.config)

        self._stimulus: dict[str, list[int]] = {}
        self._unavailable: list[int] = []
        for name, channel in STIMULUS_CHANNELS.items():
            indices, unknown = resolve_indices([channel], self.connectome.index_of)
            self._stimulus[name] = indices
            self._unavailable.extend(unknown)

        # Readout: the population of descending neurons, split into escape
        # (DNp01 giant fibre) and the rest.
        self._cell_types = cell_types
        self._escape_indices: list[int] = []
        self._descending_indices: list[int] = []
        self._build_readout(cell_types, download=download)

    def _build_readout(self, cell_types: CellTypeIndex | None, *, download: bool) -> None:
        try:
            if cell_types is None:
                cell_types = CellTypeIndex.load(self.config.data_dir, download=download)
            self._cell_types = cell_types
        except Exception:
            cell_types = None

        if cell_types is not None:
            index_of = self.connectome.index_of
            escape_ids = cell_types.ids_with_prefix("DNp01")
            for fid in escape_ids:
                try:
                    self._escape_indices.append(index_of(fid))
                except KeyError:
                    pass
            dn_ids = cell_types.ids_with_prefix("DN")
            escape_set = set(self._escape_indices)
            for fid in dn_ids:
                try:
                    idx = index_of(fid)
                except KeyError:
                    continue
                if idx not in escape_set:
                    self._descending_indices.append(idx)

        # Fall back to the hand-picked channel ids if annotations are unavailable.
        if not self._descending_indices and not self._escape_indices:
            for name, channel in READOUT_CHANNELS.items():
                indices, unknown = resolve_indices([channel], self.connectome.index_of)
                if name == "escape":
                    self._escape_indices = indices
                else:
                    self._descending_indices = indices
                self._unavailable.extend(unknown)

    @property
    def n_neurons(self) -> int:
        return self.connectome.n_neurons

    @property
    def unavailable_ids(self) -> list[int]:
        """Root ids referenced by a channel but missing from the connectome."""
        return list(self._unavailable)

    def encode(self, situation: str, *, intensity: float = 1.0) -> dict[int, float]:
        """Map a situation label to Poisson rates on sensory neurons.

        Encoding is intentionally simple and inspectable: the label selects which
        sensory channel is driven, and ``intensity`` (0..1) scales the rate. This
        is the seam where a learned encoder could be plugged in later.
        """
        label = situation.strip().lower()
        channel = None
        for key in ("sugar", "sweet", "food", "walk", "escape", "threat", "danger"):
            if key in label:
                channel = key
                break

        if channel in ("sugar", "sweet", "food"):
            channel = "sugar"
        elif channel == "walk":
            channel = "walk"
        elif channel is not None:
            channel = "escape"

        intensity = float(np.clip(intensity, 0.0, 1.0))
        rates: dict[int, float] = {}
        if channel is not None:
            rate = DEFAULT_STIM_RATE_HZ * intensity
            for index in self._stimulus.get(channel, []):
                rates[index] = rate
        return rates

    def decide(
        self,
        situation: str,
        *,
        intensity: float = 1.0,
        duration_ms: float = 100.0,
    ) -> BrainReading:
        """Run the network for ``duration_ms`` and read out a decision."""
        # Each decision starts from a clean, seeded network so results do not
        # depend on earlier decisions and are reproducible run to run.
        self.network.reset()
        rates = self.encode(situation, intensity=intensity)
        self.network.set_stimulus_rates(rates)

        steps = max(1, int(round(duration_ms / self.config.dt_ms)))
        escape_spikes = 0
        descending_spikes = 0
        for t in range(steps):
            spike = self.network.step(t)
            if not spike.spiked_indices.size:
                continue
            spiked = spike.spiked_indices
            if self._escape_indices:
                escape_spikes += int(np.isin(spiked, self._escape_indices).sum())
            if self._descending_indices:
                descending_spikes += int(np.isin(spiked, self._descending_indices).sum())

        window_s = steps * self.config.dt_ms / 1000.0
        escape_cells = max(1, len(self._escape_indices))
        descending_cells = max(1, len(self._descending_indices))
        channels = {
            "escape": ChannelReading(
                name="escape",
                rate_hz=escape_spikes / window_s / escape_cells if window_s else 0.0,
                spikes=escape_spikes,
            ),
            "descending": ChannelReading(
                name="descending",
                rate_hz=descending_spikes / window_s / descending_cells if window_s else 0.0,
                spikes=descending_spikes,
            ),
        }
        # "walk" is the fly-brain-compatible alias for the non-escape descending pool.
        channels["walk"] = channels["descending"]

        decision, confidence = _pick_decision(
            channels["walk"].rate_hz, channels["escape"].rate_hz
        )

        note = ""
        if self._unavailable:
            note = f"{len(self._unavailable)} channel neurons absent from connectome"
        return BrainReading(
            decision=decision,
            confidence=confidence,
            channels=channels,
            simulated_ms=steps * self.config.dt_ms,
            note=note,
        )


def _pick_decision(walk_rate: float, escape_rate: float) -> tuple[str, float]:
    """Turn two descending-neuron rates into a decision label and confidence."""
    total = walk_rate + escape_rate
    if total <= 0:
        return "idle", 0.0
    if walk_rate >= escape_rate:
        return "approach", walk_rate / total
    return "avoid", escape_rate / total


class FlyBrainRemote:
    """Decision engine backed by a remote fly-brain HTTP service.

    The service is started with ``python -m childbot.service``. See
    :mod:`childbot.service` for the wire format.
    """

    def __init__(self, url: str, *, timeout: float = 60.0):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def decide(
        self,
        situation: str,
        *,
        intensity: float = 1.0,
        duration_ms: float = 100.0,
    ) -> BrainReading:
        import json
        import urllib.request

        payload = json.dumps(
            {"situation": situation, "intensity": intensity, "duration_ms": duration_ms}
        ).encode()
        request = urllib.request.Request(
            f"{self.url}/decide",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read())

        channels = {
            name: ChannelReading(name=name, rate_hz=info["rate_hz"], spikes=info["spikes"])
            for name, info in data.get("channels", {}).items()
        }
        return BrainReading(
            decision=data["decision"],
            confidence=float(data["confidence"]),
            channels=channels,
            simulated_ms=float(data.get("simulated_ms", 0.0)),
            note=data.get("note", ""),
        )
