"""Bridge to an installed ``fly-brain`` checkout.

The upstream project (https://github.com/eonsystemspbc/fly-brain) runs a
benchmark CLI rather than exposing a library API. ``FlyBrainBridge`` drives that
checkout the supported way:

1. It imports ``code/paper-phil-drosophila/model.py`` (the paper's reusable
   model) directly when it is importable, giving in-process activation and
   silencing runs.
2. If that import is not available (for example the conda env is missing), it
   falls back to invoking ``main.py`` as a subprocess and reading the spike
   parquet it writes under ``data/results/``.

Both paths return a :class:`~childbot.brain.BrainReading`, so Childbot does not
care which backend answered.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from childbot.brain import BrainReading, ChannelReading, _pick_decision
from childbot.config import BrainConfig
from childbot.neurons import P9_DESCENDING, ESCAPE_DESCENDING, SUGAR_GRNS


@dataclass
class FlyBrainBridge:
    """Drive an installed fly-brain checkout.

    Parameters
    ----------
    home:
        Path to the fly-brain repo root (the directory containing ``main.py``).
    config:
        Childbot config; used for the default data paths.
    python:
        Interpreter to run fly-brain with. Defaults to the current one, which
        should be the ``brain-fly`` conda environment.
    """

    home: Path
    config: BrainConfig | None = None
    python: str = sys.executable

    def __post_init__(self) -> None:
        self.home = Path(self.home).expanduser().resolve()
        self.config = self.config or BrainConfig()
        if not (self.home / "main.py").exists():
            raise FileNotFoundError(
                f"{self.home} does not look like a fly-brain checkout (no main.py)"
            )

    @property
    def paper_model_path(self) -> Path:
        return self.home / "code" / "paper-phil-drosophila" / "model.py"

    @property
    def comp_path(self) -> Path:
        return self.home / "data" / "2025_Completeness_783.csv"

    @property
    def conn_path(self) -> Path:
        return self.home / "data" / "2025_Connectivity_783.parquet"

    def _load_paper_model(self):
        """Import the paper model module from the checkout, or return None."""
        path = self.paper_model_path
        if not path.exists():
            return None
        spec = importlib.util.spec_from_file_location("flybrain_paper_model", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            return None
        return module

    def decide(
        self,
        situation: str,
        *,
        intensity: float = 1.0,
        duration_ms: float = 100.0,
    ) -> BrainReading:
        """Run one decision cycle against fly-brain."""
        model = self._load_paper_model()
        if model is not None:
            return self._decide_in_process(model, situation, intensity, duration_ms)
        return self._decide_subprocess(situation, intensity, duration_ms)

    def _decide_in_process(
        self, model, situation: str, intensity: float, duration_ms: float
    ) -> BrainReading:
        """Use ``model.run_exp`` with activation/silencing from the situation."""
        params = dict(model.default_params)
        params["t_run"] = duration_ms * model.ms
        params["n_run"] = 1
        params["r_poi"] = 200 * model.Hz * float(np.clip(intensity, 0, 1))

        exc, slnc = _situation_to_neuron_ids(situation)
        result_dir = self.home / "data" / "childbot"
        result_dir.mkdir(parents=True, exist_ok=True)

        model.run_exp(
            exp_name="childbot_decide",
            neu_exc=list(exc),
            neu_slnc=list(slnc),
            path_res=result_dir,
            path_comp=self.comp_path,
            path_con=self.conn_path,
            params=params,
            n_proc=1,
            force_overwrite=True,
        )

        spike_file = result_dir / "childbot_decide.parquet"
        return _reading_from_spikes(
            spike_file, duration_ms, note="fly-brain paper model (in-process)"
        )

    def _decide_subprocess(
        self, situation: str, intensity: float, duration_ms: float
    ) -> BrainReading:
        """Fallback: run fly-brain's CLI and read the parquet it writes."""
        experiment = _situation_to_experiment(situation)
        t_run_s = duration_ms / 1000.0
        cmd = [
            self.python,
            "main.py",
            "--experiment",
            experiment,
            "--pytorch",
            "--t_run",
            str(t_run_s),
            "--n_run",
            "1",
            "--no_log_file",
        ]
        env = dict(os.environ)
        env.setdefault("PYTHONUNBUFFERED", "1")
        subprocess.run(cmd, cwd=self.home, env=env, check=True)

        results_dir = self.home / "data" / "results"
        candidates = sorted(
            results_dir.rglob(f"*pytorch_t{t_run_s}s_n1*.parquet"),
            key=lambda p: p.stat().st_mtime,
        )
        if not candidates:
            raise FileNotFoundError(
                f"fly-brain produced no spike parquet under {results_dir}"
            )
        return _reading_from_spikes(
            candidates[-1], duration_ms, note=f"fly-brain CLI (--experiment {experiment})"
        )


def _situation_to_experiment(situation: str) -> str:
    label = situation.strip().lower()
    if any(k in label for k in ("escape", "threat", "danger", "avoid")):
        return "p9"
    return "sugar"


def _situation_to_neuron_ids(situation: str) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return (excite, silence) FlyWire ids for a situation label."""
    label = situation.strip().lower()
    if any(k in label for k in ("escape", "threat", "danger", "avoid")):
        return ESCAPE_DESCENDING.root_ids, SUGAR_GRNS.root_ids
    if "walk" in label or "approach" in label:
        return P9_DESCENDING.root_ids, ()
    return SUGAR_GRNS.root_ids, ()


def _reading_from_spikes(path: Path, duration_ms: float, *, note: str) -> BrainReading:
    """Summarise a fly-brain spike parquet into a decision reading."""
    import pandas as pd

    df = pd.read_parquet(path)
    window_s = max(duration_ms / 1000.0, 1e-6)

    walk_ids = set(P9_DESCENDING.root_ids)
    escape_ids = set(ESCAPE_DESCENDING.root_ids)

    def count(ids: set[int]) -> int:
        if "flywire_id" not in df.columns or not ids:
            return 0
        return int(df["flywire_id"].isin(ids).sum())

    walk_spikes = count(walk_ids)
    escape_spikes = count(escape_ids)
    walk_rate = walk_spikes / window_s
    escape_rate = escape_spikes / window_s

    decision, confidence = _pick_decision(walk_rate, escape_rate)
    return BrainReading(
        decision=decision,
        confidence=confidence,
        channels={
            "walk": ChannelReading("walk", walk_rate, walk_spikes),
            "escape": ChannelReading("escape", escape_rate, escape_spikes),
        },
        simulated_ms=duration_ms,
        note=note,
    )
