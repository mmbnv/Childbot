"""Загрузка коннектома FlyWire FAFB и сборка разреженной матрицы весов.

Два файла описывают мозг:

* ``2025_Completeness_783.csv`` — список нейронов (по FlyWire root id).
* ``2025_Connectivity_783.parquet`` — по строке на пару (пре-, постсинапс)
  с числом синапсов.

``Excitatory x Connectivity`` — знаковое число синапсов, которое fly-brain
умножает на ``w_scale``. Матрица индексируется ПОЗИЦИЕЙ в файле полноты, то
есть ``weights[i, j]`` — синапсы от нейрона ``j`` на нейрон ``i`` (та же
ориентация, что у fly-brain ``get_weights``).
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from flybrain.config import (
    BrainConfig,
    COMPLETENESS_FILENAME,
    CONNECTIVITY_FILENAME,
    FLYBRAIN_RAW_BASE,
)


def download_file(url: str, dest: Path, *, timeout: int = 300) -> None:
    """Скачать файл в ``dest`` (через временный ``.part``)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "childbot-flybrain/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response, open(tmp, "wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)


@dataclass
class Connectome:
    """Id нейронов и разреженная матрица весов синапсов."""

    flywire_ids: np.ndarray
    weights: sp.csr_matrix

    @property
    def n_neurons(self) -> int:
        return int(self.weights.shape[0])

    def index_of(self, flywire_id: int) -> int:
        """Индекс в матрице для FlyWire root id (KeyError, если нет)."""
        matches = np.nonzero(self.flywire_ids == flywire_id)[0]
        if matches.size == 0:
            raise KeyError(f"FlyWire id {flywire_id} отсутствует в коннектоме")
        return int(matches[0])

    @classmethod
    def load(
        cls,
        config: BrainConfig,
        *,
        download: bool = False,
        subset_size: int | None = None,
    ) -> "Connectome":
        """Загрузить (при необходимости скачать) коннектом FAFB для ``config``."""
        comp_path = config.completeness_path
        conn_path = config.connectivity_path

        if download:
            if not comp_path.exists():
                download_file(f"{FLYBRAIN_RAW_BASE}/{COMPLETENESS_FILENAME}", comp_path)
            if not conn_path.exists():
                download_file(f"{FLYBRAIN_RAW_BASE}/{CONNECTIVITY_FILENAME}", conn_path)

        missing = [str(p) for p in (comp_path, conn_path) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "Нет данных коннектома: " + ", ".join(missing)
                + ". См. Fly-brain/README.md."
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

        ids = pd.read_csv(comp_path, index_col=0).index.to_numpy(dtype=np.int64)
        n_neurons = len(ids)

        if cache_path is not None and cache_path.exists() and subset_size is None:
            cached = np.load(cache_path, allow_pickle=False)
            if int(cached["n_neurons"]) == n_neurons:
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
    """Оставить ``subset_size`` самых связанных нейронов.

    Случайный срез оставил бы их почти без связей, поэтому берём узлы с
    наибольшей степенью и переиндексируем рёбра между ними.
    """
    degree = np.asarray(weights.getnnz(axis=0)).ravel() + np.asarray(
        weights.getnnz(axis=1)
    ).ravel()
    keep = np.argsort(degree)[::-1][:subset_size]
    keep.sort()
    sub = weights[keep][:, keep].tocoo()
    return ids[keep], sub.tocsr()
