"""Движок LIF по матрице весов коннектома.

Это порт модели из ``fly-brain/code/run_pytorch.py`` на numpy: пуассоновский
стимул → альфа-синапс с задержкой → LIF-нейрон с рефрактерностью, рекуррентный
вход ``w_scale * W @ spikes``. Уравнения те же, поэтому динамика совпадает с
эталонной, но не нужны GPU и conda-окружение fly-brain.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp

from flybrain.config import BrainConfig


@dataclass
class SpikeStep:
    """Активность за один шаг симуляции."""

    timestep: int
    time_s: float
    spiked_indices: np.ndarray


class LIFNetwork:
    """Пошаговая симуляция сети LIF.

    Параметры
    ----------
    weights:
        Разреженная ``(n, n)``; ``weights[i, j]`` — знаковый вес синапса с ``j``
        на ``i``.
    config:
        Численные параметры (по умолчанию как в fly-brain).
    """

    def __init__(self, weights: sp.csr_matrix, config: BrainConfig, *, n_trials: int = 1):
        self.weights = weights.tocsr().astype(np.float32)
        # Рекуррентный вход ненулевой только для нейронов, вспыхнувших на прошлом
        # шаге. Сбор этих столбцов из CSC примерно в 100 раз быстрее полного
        # matvec по 15M синапсов и даёт тот же результат (пропущенные столбцы
        # умножаются на ноль).
        self._weights_csc = weights.tocsc().astype(np.float32)
        self.config = config
        self.n_neurons = int(weights.shape[0])
        self.n_trials = n_trials

        self._steps_delay = int(config.delay_ms / config.dt_ms)
        self._syn_factor = config.dt_ms / config.tau_syn_ms
        self._mem_factor = config.dt_ms / config.tau_mem_ms
        self._base_refrac = int(round(config.t_refrac_ms / config.dt_ms))
        self._poisson_prob = config.dt_ms / 1000.0
        self._refrac_steps = np.full(self.n_neurons, self._base_refrac, dtype=np.float32)

        self.reset()

    def reset(self) -> None:
        """Вернуть сеть в начальное состояние с засеянным ГПСЧ."""
        self.rng = np.random.default_rng(self.config.seed)
        b, n = self.n_trials, self.n_neurons
        self.conductance = np.zeros((b, n), dtype=np.float32)
        self.delay_buffer = np.zeros((b, self._steps_delay + 1, n), dtype=np.float32)
        self.spikes = np.zeros((b, n), dtype=np.float32)
        self.voltage = np.full((b, n), self.config.v_rest_mv, dtype=np.float32)
        self.refrac = np.tile(self._refrac_steps, (b, 1))
        self._rates = None
        self._stim_indices = None

    def set_stimulus_rates(self, rates_hz: dict[int, float]) -> None:
        """Задать частоты пуассоновского стимула (Гц) для следующих шагов."""
        self._rates = np.zeros((self.n_trials, self.n_neurons), dtype=np.float32)
        self._stim_indices = np.fromiter(
            (int(i) for i in rates_hz), dtype=np.int64, count=len(rates_hz)
        )
        for index, rate in rates_hz.items():
            self._rates[:, index] = rate

    def _recurrent_input(self) -> np.ndarray:
        """Взвешенный вход от нейронов, вспыхнувших на прошлом шаге."""
        active = np.nonzero(self.spikes[0])[0]
        if active.size == 0:
            return np.zeros((self.n_trials, self.n_neurons), dtype=np.float32)
        weighted = self._weights_csc[:, active] @ self.spikes[:, active].T
        return np.asarray(weighted.T, dtype=np.float32)

    def step(self, timestep: int) -> SpikeStep:
        """Прожить один ``dt`` и вернуть, кто вспыхнул."""
        cfg = self.config
        rates = self._rates
        stim = self._stim_indices
        # Из внешнего стимула могут вспыхнуть только стимулируемые нейроны,
        # поэтому случайные числа тянем только для них, а не для всех 138k.
        voltage_stim = np.zeros((self.n_trials, self.n_neurons), dtype=np.float32)
        if rates is not None and stim is not None and stim.size:
            draws = self.rng.random((self.n_trials, stim.size))
            fired = (draws < rates[:, stim] * self._poisson_prob).astype(np.float32)
            voltage_stim[:, stim] = cfg.w_scale * fired * cfg.scale_poisson

        recurrent = cfg.w_scale * self._recurrent_input()

        self.refrac = np.where(self.spikes > 0, 0.0, self.refrac + 1.0)
        open_mask = (self.refrac >= self._refrac_steps[None, :]).astype(np.float32)

        conductance_new = (
            self.conductance * (1 - self._syn_factor)
            + self.delay_buffer[:, 0, :] * open_mask
        )
        self.delay_buffer[:, :-1] = self.delay_buffer[:, 1:]
        self.delay_buffer[:, -1] = recurrent

        v = self.voltage + voltage_stim
        v = v + self._mem_factor * (self.conductance - (v - cfg.v_rest_mv))
        spiked = (v > cfg.v_threshold_mv).astype(np.float32)
        v = v - (v - cfg.v_rest_mv) * spiked
        conductance_new = conductance_new - conductance_new * spiked

        self.conductance = conductance_new
        self.voltage = v
        self.spikes = spiked

        return SpikeStep(
            timestep=timestep,
            time_s=(timestep + 1) * cfg.dt_ms / 1000.0,
            spiked_indices=np.nonzero(spiked[0])[0],
        )
