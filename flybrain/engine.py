"""Движок fly-brain: ситуация → стимул → симуляция → отклик нисходящих нейронов.

``FlyBrainEngine`` владеет коннектомом и сетью LIF. Он кодирует ситуацию как
частоты пуассоновского стимула на реальных сенсорных нейронах, прогоняет сеть
на короткое окно и читает отклик ПОПУЛЯЦИИ нисходящих нейронов (типы клеток
``DN*``), которые и командуют телом. Отношение активности нейронов бегства
(``DNp01``) к остальным нисходящим даёт врождённый знак: избегать или идти.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from flybrain.celltypes import CellTypeIndex
from flybrain.config import BrainConfig
from flybrain.connectome import Connectome
from flybrain.lif import LIFNetwork
from flybrain.neurons import (
    DEFAULT_STIM_RATE_HZ,
    STIMULUS_CHANNELS,
    resolve_indices,
)


@dataclass
class ChannelReading:
    """Отклик одного канала (частота спайков)."""

    name: str
    rate_hz: float
    spikes: int


@dataclass
class BrainReading:
    """Результат одного такта решения."""

    decision: str
    confidence: float
    channels: dict[str, ChannelReading] = field(default_factory=dict)
    simulated_ms: float = 0.0
    note: str = ""

    def channel_rate(self, name: str) -> float:
        reading = self.channels.get(name)
        return reading.rate_hz if reading else 0.0


class FlyBrainEngine:
    """Локальный LIF-движок fly-brain поверх коннектома FlyWire FAFB."""

    def __init__(
        self,
        config: BrainConfig | None = None,
        *,
        connectome: Connectome | None = None,
        cell_types: CellTypeIndex | None = None,
        download: bool = False,
    ):
        self.config = config or BrainConfig()
        self.connectome = connectome or Connectome.load(
            self.config, download=download, subset_size=self.config.subset_size
        )
        self.network = LIFNetwork(self.connectome.weights, self.config)

        self._stimulus: dict[str, list[int]] = {}
        self._unavailable: list[int] = []
        for name, channel in STIMULUS_CHANNELS.items():
            indices, unknown = resolve_indices([channel], self.connectome.index_of)
            self._stimulus[name] = indices
            self._unavailable.extend(unknown)

        # Чтение: популяция нисходящих нейронов (DN*), отдельно — бегство (DNp01).
        self._escape_indices: list[int] = []
        self._descending_indices: list[int] = []
        self._build_readout(cell_types, download=download)

    def _build_readout(self, cell_types: CellTypeIndex | None, *, download: bool) -> None:
        if cell_types is None:
            try:
                cell_types = CellTypeIndex.load(self.config.data_dir, download=download)
            except Exception:
                cell_types = None

        if cell_types is None:
            # Без аннотаций читаем хотя бы явные id бегства/ходьбы.
            indices, unknown = resolve_indices(
                [STIMULUS_CHANNELS["escape"]], self.connectome.index_of
            )
            self._escape_indices = indices
            self._unavailable.extend(unknown)
            return

        index_of = self.connectome.index_of
        for fid in cell_types.ids_with_prefix("DNp01"):
            try:
                self._escape_indices.append(index_of(fid))
            except KeyError:
                pass
        escape_set = set(self._escape_indices)
        for fid in cell_types.ids_with_prefix("DN"):
            try:
                idx = index_of(fid)
            except KeyError:
                continue
            if idx not in escape_set:
                self._descending_indices.append(idx)

    @property
    def n_neurons(self) -> int:
        return self.connectome.n_neurons

    @property
    def unavailable_ids(self) -> list[int]:
        """Root id, упомянутые каналом, но отсутствующие в коннектоме."""
        return list(self._unavailable)

    def encode(self, stimuli: dict[str, float]) -> dict[int, float]:
        """Каналы+интенсивности → частоты пуассоновского стимула на нейронах.

        ``stimuli`` — например ``{'sugar': 0.8, 'escape': 0.3}``; значения
        0..1 масштабируют частоту по умолчанию.
        """
        rates: dict[int, float] = {}
        for channel, intensity in stimuli.items():
            amount = float(np.clip(intensity, 0.0, 1.0))
            if amount <= 0:
                continue
            rate = DEFAULT_STIM_RATE_HZ * amount
            for index in self._stimulus.get(channel, []):
                rates[index] = max(rates.get(index, 0.0), rate)
        return rates

    def run(
        self,
        stimuli: dict[str, float],
        *,
        duration_ms: float = 60.0,
    ) -> BrainReading:
        """Прогнать сеть ``duration_ms`` и прочитать решение."""
        self.network.reset()
        self.network.set_stimulus_rates(self.encode(stimuli))

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
                "escape",
                escape_spikes / window_s / escape_cells if window_s else 0.0,
                escape_spikes,
            ),
            "descending": ChannelReading(
                "descending",
                descending_spikes / window_s / descending_cells if window_s else 0.0,
                descending_spikes,
            ),
        }

        decision, confidence = _pick_decision(
            channels["descending"].rate_hz, channels["escape"].rate_hz
        )
        note = ""
        if self._unavailable:
            note = f"{len(self._unavailable)} нейронов каналов нет в коннектоме"
        return BrainReading(
            decision=decision,
            confidence=confidence,
            channels=channels,
            simulated_ms=steps * self.config.dt_ms,
            note=note,
        )


def _pick_decision(forward_rate: float, escape_rate: float) -> tuple[str, float]:
    """Две частоты нисходящих нейронов → метка решения и уверенность."""
    total = forward_rate + escape_rate
    if total <= 0:
        return "idle", 0.0
    if escape_rate > forward_rate:
        return "avoid", escape_rate / total
    return "approach", forward_rate / total
