"""Integration tests for Childbot's fly-brain connection.

These exercise the real code paths over the real FlyWire FAFB connectome and
the real Codex cell-type annotations - no mocks. The connectome files must be
present in ``data/`` (see README); the tests skip rather than download.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pytest

from childbot.bot import Childbot, build_brain
from childbot.brain import FlyBrain, FlyBrainRemote
from childbot.celltypes import CellTypeIndex
from childbot.config import BrainConfig
from childbot.connectome import Connectome
from childbot.lif import LIFNetwork
from childbot.neurons import ESCAPE_DESCENDING, SUGAR_GRNS

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = BrainConfig()

pytestmark = pytest.mark.skipif(
    not CONFIG.completeness_path.exists() or not CONFIG.connectivity_path.exists(),
    reason="FlyWire FAFB data not present in data/",
)


@pytest.fixture(scope="module")
def connectome() -> Connectome:
    return Connectome.load(CONFIG, download=False)


@pytest.fixture(scope="module")
def brain() -> FlyBrain:
    return FlyBrain(CONFIG, download=False)


def test_connectome_shape_and_orientation(connectome: Connectome) -> None:
    # FAFB v783 has 139,255 neurons in the full release; the fly-brain mirror
    # ships the 138,639-neuron model subset.
    assert connectome.n_neurons == 138639
    assert connectome.weights.shape == (connectome.n_neurons, connectome.n_neurons)
    assert connectome.weights.nnz > 10_000_000


def test_weight_orientation_matches_synapse_table(connectome: Connectome) -> None:
    """weights[i, j] must be the weight from presynaptic j onto postsynaptic i."""
    import pandas as pd

    df = pd.read_parquet(
        CONFIG.connectivity_path,
        columns=["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"],
    )
    row = df.iloc[0]
    i = int(row["Postsynaptic_Index"])
    j = int(row["Presynaptic_Index"])
    expected = float(row["Excitatory x Connectivity"])
    assert connectome.weights[i, j] == pytest.approx(expected)


def test_stimulated_neurons_spike(connectome: Connectome) -> None:
    """Driving the sugar GRNs must make them fire and activate downstream cells."""
    net = LIFNetwork(connectome.weights, CONFIG)
    sugar = [connectome.index_of(i) for i in SUGAR_GRNS.root_ids]
    net.set_stimulus_rates({i: 200.0 for i in sugar})

    total = np.zeros(connectome.n_neurons)
    for t in range(500):  # 50 ms
        step = net.step(t)
        if step.spiked_indices.size:
            total[step.spiked_indices] += 1

    assert total[sugar].sum() > 0, "stimulated GRNs never fired"
    assert (total > 0).sum() > len(sugar), "activity never spread past the stimulus"


def test_escape_stimulus_triggers_avoidance(brain: FlyBrain) -> None:
    reading = brain.decide("escape", duration_ms=100)
    assert reading.decision == "avoid"
    assert reading.channels["escape"].spikes > 0


def test_sugar_stimulus_triggers_approach(brain: FlyBrain) -> None:
    reading = brain.decide("sweet sugar", duration_ms=200)
    assert reading.decision == "approach"
    assert reading.channel_rate("descending") > 0


def test_readout_uses_real_descending_population(brain: FlyBrain) -> None:
    # The population readout must be much larger than the two hand-picked ids.
    assert len(brain._descending_indices) > 100
    assert len(brain._escape_indices) >= 1


def test_cell_type_index_matches_known_neurons() -> None:
    types = CellTypeIndex.load(CONFIG.data_dir, download=False)
    assert types.type_of(ESCAPE_DESCENDING.root_ids[0]) == "DNp01"
    assert types.type_of(SUGAR_GRNS.root_ids[0]) == "LB3"


def test_decisions_are_reproducible_with_seed() -> None:
    a = FlyBrain(CONFIG.with_(seed=7), download=False)
    b = FlyBrain(CONFIG.with_(seed=7), download=False)
    ra = a.decide("escape", duration_ms=50)
    rb = b.decide("escape", duration_ms=50)
    assert ra.decision == rb.decision
    assert ra.channels["escape"].spikes == rb.channels["escape"].spikes


def test_bot_memory_round_trip(brain: FlyBrain, tmp_path: Path) -> None:
    memory = tmp_path / "memory.json"
    bot = Childbot(brain=brain, config=CONFIG, memory_path=memory)

    first = bot.respond("escape", duration_ms=100)
    assert first["source"] == "brain"
    assert first["decision"] == "avoid"

    second = bot.respond("escape", duration_ms=100)
    assert second["source"] == "memory"
    assert second["hits"] == 2

    reloaded = Childbot(brain=brain, config=CONFIG, memory_path=memory)
    assert "escape" in reloaded.memory
    assert json.loads(memory.read_text())["entries"]["escape"]["decision"] == "avoid"


def test_build_brain_prefers_flybrain_home(tmp_path: Path) -> None:
    # A directory that looks like a fly-brain checkout (has main.py).
    (tmp_path / "main.py").write_text("# stub\n")
    config = CONFIG.with_(flybrain_home=tmp_path)
    brain = build_brain(config, download=False)
    assert type(brain).__name__ == "FlyBrainBridge"


def test_service_round_trip() -> None:
    """Start the real service and drive it over HTTP."""
    port = 8079
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "childbot.service",
            "--port",
            str(port),
            "--subset-size",
            "4000",
            "--no-download",
        ],
        cwd=REPO_ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(120):
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=2) as resp:
                    health = json.loads(resp.read())
                break
            except Exception:
                time.sleep(0.5)
        else:
            pytest.fail("service did not become healthy")

        assert health["status"] == "ok"
        assert health["engine"] == "FlyBrain"

        payload = json.dumps({"situation": "escape", "duration_ms": 50}).encode()
        request = urllib.request.Request(
            f"{base}/decide",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as resp:
            result = json.loads(resp.read())
        assert result["decision"] in {"avoid", "approach", "idle"}
        assert "channels" in result

        remote = FlyBrainRemote(base)
        reading = remote.decide("escape", duration_ms=50)
        assert reading.decision in {"avoid", "approach", "idle"}
    finally:
        proc.terminate()
        proc.wait(timeout=30)
