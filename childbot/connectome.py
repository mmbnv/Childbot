"""Load the FlyWire FAFB connectome and turn it into a sparse weight matrix.

Two files describe the brain:

* ``2025_Completeness_783.csv``  - the neuron list (one row per neuron, indexed
  by FlyWire root id).
* ``2025_Connectivity_783.parquet`` - one row per (presynaptic, postsynaptic)
  pair with a synapse count.

``Excitatory x Connectivity`` is the signed, weighted connection count that
fly-brain multiplies by ``w_scale``. The weight matrix is indexed by *position*
in the completeness file, so ``weight[i, j]`` means "synapses from neuron j onto
neuron i" - the same orientation fly-brain's ``get_weights`` builds.
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from childbot.config import (
    BrainConfig,
    COMPLETENESS_FILENAME,
    CONNECTIVITY_FILENAME,
    FLYBRAIN_RAW_BASE,
)


def _download(url: str, dest: Path, *, timeout: int = 300) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "childbot/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response, open(tmp, "wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)


@dataclass
class Connectome:
    """Neuron ids plus a sparse synapse-weight matrix.

    Attributes
    ----------
    flywire_ids:
        Root ids in matrix order. ``flywire_ids[i]`` is row/column ``i``.
    weights:
        ``csr_matrix`` of shape ``(n_neurons, n_neurons)`` where
        ``weights[i, j]`` is the signed synapse weight from ``j`` onto ``i``.
    """

    flywire_ids: np.ndarray
    weights: sp.csr_matrix

    @property
    def n_neurons(self) -> int:
        return int(self.weights.shape[0])

    def index_of(self, flywire_id: int) -> int:
        """Return the matrix index for a FlyWire root id."""
        matches = np.nonzero(self.flywire_ids == flywire_id)[0]
        if matches.size == 0:
            raise KeyError(f"FlyWire id {flywire_id} is not in this connectome")
        return int(matches[0])

    def downstream_of(self, indices, *, top: int = 10) -> list[tuple[int, float]]:
        """Return the strongest postsynaptic targets of ``indices``.

        Each entry is ``(matrix_index, total_weight)`` sorted by weight.
        """
        idx = np.atleast_1d(np.asarray(indices, dtype=np.int64))
        column = np.asarray(self.weights[:, idx].sum(axis=1)).ravel()
        order = np.argsort(column)[::-1]
        order = [int(i) for i in order if column[i] > 0][:top]
        return [(i, float(column[i])) for i in order]

    @classmethod
    def load(
        cls,
        config: BrainConfig,
        *,
        download: bool = True,
        subset_size: int | None = None,
    ) -> "Connectome":
        """Load (and, if needed, fetch) the FAFB connectome for ``config``."""
        comp_path = config.completeness_path
        conn_path = config.connectivity_path

        if download:
            if not comp_path.exists():
                _download(f"{FLYBRAIN_RAW_BASE}/{COMPLETENESS_FILENAME}", comp_path)
            if not conn_path.exists():
                _download(f"{FLYBRAIN_RAW_BASE}/{CONNECTIVITY_FILENAME}", conn_path)

        missing = [str(p) for p in (comp_path, conn_path) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "Connectome data missing: "
                + ", ".join(missing)
                + ". Run with download enabled or set CHILDBOT_DATA_DIR."
            )

        ids, weights = cls._build(
            comp_path,
            conn_path,
            config.weight_cache_path if config.cache_weights else None,
            subset_size=subset_size,
        )
        return cls(flywire_ids=ids, weights=weights)

    @staticmethod
    def _build(
        comp_path: Path,
        conn_path: Path,
        cache_path: Path | None,
        *,
        subset_size: int | None,
    ) -> tuple[np.ndarray, sp.csr_matrix]:
        import pandas as pd

        df_comp = pd.read_csv(comp_path, index_col=0)
        ids = df_comp.index.to_numpy(dtype=np.int64)
        n_neurons = len(ids)

        if cache_path is not None and cache_path.exists():
            cached = np.load(cache_path, allow_pickle=False)
            if int(cached["n_neurons"]) == n_neurons and subset_size is None:
                return ids, sp.csr_matrix(
                    (cached["data"], cached["indices"], cached["indptr"]),
                    shape=(n_neurons, n_neurons),
                )

        df_con = pd.read_parquet(
            conn_path,
            columns=["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"],
        )
        rows = df_con["Postsynaptic_Index"].to_numpy(dtype=np.int64)
        cols = df_con["Presynaptic_Index"].to_numpy(dtype=np.int64)
        vals = df_con["Excitatory x Connectivity"].to_numpy(dtype=np.float32)

        weights = sp.coo_matrix((vals, (rows, cols)), shape=(n_neurons, n_neurons)).tocsr()

        if subset_size is not None and subset_size < n_neurons:
            ids, weights = _restrict(ids, weights, subset_size)

        if cache_path is not None and subset_size is None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(
                cache_path,
                data=weights.data,
                indices=weights.indices,
                indptr=weights.indptr,
                n_neurons=n_neurons,
            )

        return ids, weights


def _restrict(
    ids: np.ndarray, weights: sp.csr_matrix, subset_size: int
) -> tuple[np.ndarray, sp.csr_matrix]:
    """Keep only the ``subset_size`` most strongly wired neurons.

    Subsetting is a convenience for fast runs: a random slice would leave the
    kept neurons almost disconnected, so we keep the highest-degree nodes and
    re-index the edges among them.
    """
    degree = np.asarray(weights.getnnz(axis=0)).ravel() + np.asarray(
        weights.getnnz(axis=1)
    ).ravel()
    keep = np.argsort(degree)[::-1][:subset_size]
    keep.sort()
    remap = np.full(weights.shape[0], -1, dtype=np.int64)
    remap[keep] = np.arange(keep.size)
    sub = weights[keep][:, keep].tocoo()
    return ids[keep], sub.tocsr()
