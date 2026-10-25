"""Configuration for the Childbot brain.

Every value can be overridden with an environment variable so the same code runs
in this container, on a laptop, or on a GPU box without edits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

# Repository root = parent of this package directory.
REPO_ROOT = Path(__file__).resolve().parent.parent

# Public mirrors of the FlyWire FAFB v783 data that fly-brain ships with.
COMPLETENESS_FILENAME = "2025_Completeness_783.csv"
CONNECTIVITY_FILENAME = "2025_Connectivity_783.parquet"
WEIGHT_CACHE_FILENAME = "weight_csr_783.npz"

FLYBRAIN_RAW_BASE = (
    "https://raw.githubusercontent.com/eonsystemspbc/fly-brain/main/data"
)


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


@dataclass(frozen=True)
class BrainConfig:
    """Numerical parameters and paths for one brain instance.

    The default numbers match ``fly-brain/code/run_pytorch.py`` so a locally run
    Childbot brain reproduces the reference model. Changing them changes the
    dynamics, not the wiring.
    """

    # --- Where the connectome lives -------------------------------------
    data_dir: Path = field(
        default_factory=lambda: _env_path("CHILDBOT_DATA_DIR", REPO_ROOT / "data")
    )

    # --- LIF model constants (fly-brain MODEL_PARAMS) -------------------
    dt_ms: float = 0.1          # simulation timestep, ms
    tau_syn_ms: float = 5.0     # synapse time constant
    delay_ms: float = 1.8       # synaptic delay
    v_rest_mv: float = -52.0    # resting / reset potential
    v_threshold_mv: float = -45.0
    tau_mem_ms: float = 20.0    # membrane time constant
    t_refrac_ms: float = 2.2    # refractory period
    scale_poisson: float = 250.0
    w_scale: float = 0.275      # weight scale applied to input and recurrence

    # --- Runtime --------------------------------------------------------
    seed: int = 0
    subset_size: int | None = None  # cap neuron count for fast runs; None = full brain
    cache_weights: bool = True
    threads: int = field(
        default_factory=lambda: int(os.environ.get("CHILDBOT_THREADS", "0"))
    )

    # --- External fly-brain --------------------------------------------
    flybrain_home: Path | None = field(
        default_factory=lambda: _env_path("CHILDBOT_FLYBRAIN_HOME", Path())
        if os.environ.get("CHILDBOT_FLYBRAIN_HOME")
        else None
    )
    flybrain_url: str | None = field(
        default_factory=lambda: os.environ.get("CHILDBOT_FLYBRAIN_URL")
    )

    @property
    def completeness_path(self) -> Path:
        return self.data_dir / COMPLETENESS_FILENAME

    @property
    def connectivity_path(self) -> Path:
        return self.data_dir / CONNECTIVITY_FILENAME

    @property
    def weight_cache_path(self) -> Path:
        return self.data_dir / WEIGHT_CACHE_FILENAME

    @property
    def steps_per_second(self) -> int:
        return int(round(1000.0 / self.dt_ms))

    def with_(self, **kwargs) -> "BrainConfig":
        return replace(self, **kwargs)
