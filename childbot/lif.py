"""Leaky integrate-and-fire engine over a connectome weight matrix.

This is a NumPy port of fly-brain's ``code/run_pytorch.py`` model: Poisson
stimulus -> alpha-function synapse with delay -> LIF neuron with refractory
period, with recurrent input ``w_scale * W @ spikes``. Keeping the equations
identical means Childbot's local brain reproduces the reference dynamics without
needing a GPU or the conda environment.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp

from childbot.config import BrainConfig


@dataclass
class SpikeStep:
    """Spike activity for one simulated timestep."""

    timestep: int
    time_s: float
    spiked_indices: np.ndarray


class LIFNetwork:
    """Stateful LIF network simulation.

    Parameters
    ----------
    weights:
        Sparse ``(n_neurons, n_neurons)`` matrix; ``weights[i, j]`` is the signed
        synapse weight from ``j`` onto ``i``.
    config:
        Numerical parameters. Defaults reproduce fly-brain.
    """

    def __init__(self, weights: sp.csr_matrix, config: BrainConfig, *, n_trials: int = 1):
        self.weights = weights.tocsr().astype(np.float32)
        # Recurrent input is only nonzero for the handful of neurons that spiked
        # in the previous step. Gathering those columns from a CSC matrix is ~100x
        # faster than a full sparse matvec over all 15M synapses, and gives the
        # same result because the skipped columns are multiplied by zero.
        self._weights_csc = weights.tocsc().astype(np.float32)
        self.config = config
        self.n_neurons = int(weights.shape[0])
        self.n_trials = n_trials
        self.rng = np.random.default_rng(config.seed)

        self._steps_delay = int(config.delay_ms / config.dt_ms)
        self._syn_factor = config.dt_ms / config.tau_syn_ms
        self._mem_factor = config.dt_ms / config.tau_mem_ms
        self._base_refrac = int(round(config.t_refrac_ms / config.dt_ms))
        self._poisson_prob = config.dt_ms / 1000.0

        self._refrac_steps = np.full(self.n_neurons, self._base_refrac, dtype=np.float32)
        self._reset()

    def _reset(self) -> None:
        self.rng = np.random.default_rng(self.config.seed)
        self._reset_state()

    def _reset_state(self) -> None:
        b, n = self.n_trials, self.n_neurons
        self.conductance = np.zeros((b, n), dtype=np.float32)
        self.delay_buffer = np.zeros((b, self._steps_delay + 1, n), dtype=np.float32)
        self.spikes = np.zeros((b, n), dtype=np.float32)
        self.voltage = np.full((b, n), self.config.v_rest_mv, dtype=np.float32)
        self.refrac = np.tile(self._refrac_steps, (b, 1))
        self._rates = None
        self._stim_indices = None

    def reset(self) -> None:
        """Return the network to its initial state with the seeded RNG."""
        self._reset()

    def set_stimulus_rates(self, rates_hz: dict[int, float]) -> None:
        """Set per-neuron Poisson stimulus rates (Hz) for the next steps."""
        self._rates = np.zeros((self.n_trials, self.n_neurons), dtype=np.float32)
        self._stim_indices = np.fromiter(
            (int(i) for i in rates_hz), dtype=np.int64, count=len(rates_hz)
        )
        for index, rate in rates_hz.items():
            self._rates[:, index] = rate

    def silence(self, indices) -> None:
        """Zero all synapses onto and from ``indices`` (optogenetic silencing)."""
        idx = np.atleast_1d(np.asarray(indices, dtype=np.int64))
        self.weights = self.weights.tolil()
        for i in idx:
            self.weights[:, i] = 0
            self.weights[i, :] = 0
        self.weights = self.weights.tocsr()
        self._weights_csc = self.weights.tocsc()

    def _recurrent_input(self) -> np.ndarray:
        """Weighted input from neurons that spiked on the previous step."""
        active = np.nonzero(self.spikes[0])[0]
        if active.size == 0:
            return np.zeros((self.n_trials, self.n_neurons), dtype=np.float32)
        weighted = self._weights_csc[:, active] @ self.spikes[:, active].T
        return np.asarray(weighted.T, dtype=np.float32)

    def step(self, timestep: int) -> SpikeStep:
        """Advance the network by one ``dt`` and return who spiked."""
        cfg = self.config
        rates = getattr(self, "_rates", None)
        stim = getattr(self, "_stim_indices", None)
        # Only stimulated neurons can fire from external drive, so draw random
        # numbers just for them instead of the whole 138k-neuron array.
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
