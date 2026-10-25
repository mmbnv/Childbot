"""Параметры модели fly-brain и пути к данным.

Числа по умолчанию совпадают с fly-brain (``code/run_pytorch.py``), чтобы
динамика нашего движка повторяла эталонную. Всё можно переопределить
переменной окружения.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Данные коннектома лежат в Fly-brain/ (в git не хранятся, см. Fly-brain/README.md).
DEFAULT_DATA_DIR = REPO_ROOT / "Fly-brain"

COMPLETENESS_FILENAME = "2025_Completeness_783.csv"
CONNECTIVITY_FILENAME = "2025_Connectivity_783.parquet"
ANNOTATION_FILENAME = "consolidated_cell_types_783.csv.gz"
WEIGHT_CACHE_FILENAME = "weight_csr_783.npz"

FLYBRAIN_RAW_BASE = (
    "https://raw.githubusercontent.com/eonsystemspbc/fly-brain/main/data"
)
ANNOTATION_URL = (
    "https://storage.googleapis.com/flywire-data/codex/data/fafb/783/"
    "consolidated_cell_types.csv.gz"
)


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class BrainConfig:
    """Численные параметры и пути одного экземпляра мозга."""

    data_dir: Path = field(
        default_factory=lambda: _env_path("FLYBRAIN_DATA_DIR", DEFAULT_DATA_DIR)
    )

    # --- LIF (значения fly-brain) ---------------------------------------
    dt_ms: float = 0.1
    tau_syn_ms: float = 5.0
    delay_ms: float = 1.8
    v_rest_mv: float = -52.0
    v_threshold_mv: float = -45.0
    tau_mem_ms: float = 20.0
    t_refrac_ms: float = 2.2
    scale_poisson: float = 250.0
    w_scale: float = 0.275

    # --- Запуск ---------------------------------------------------------
    seed: int = field(default_factory=lambda: _env_int("FLYBRAIN_SEED", 0))
    subset_size: int | None = field(
        default_factory=lambda: _env_int("FLYBRAIN_SUBSET", 0) or None
    )
    cache_weights: bool = True

    @property
    def completeness_path(self) -> Path:
        return self.data_dir / COMPLETENESS_FILENAME

    @property
    def connectivity_path(self) -> Path:
        return self.data_dir / CONNECTIVITY_FILENAME

    @property
    def annotation_path(self) -> Path:
        return self.data_dir / ANNOTATION_FILENAME

    @property
    def weight_cache_path(self) -> Path:
        return self.data_dir / WEIGHT_CACHE_FILENAME

    def data_available(self) -> bool:
        """Есть ли на диске хотя бы файлы коннектома (аннотации необязательны)."""
        return self.completeness_path.exists() and self.connectivity_path.exists()

    def with_(self, **kwargs) -> "BrainConfig":
        return replace(self, **kwargs)
