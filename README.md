# Childbot

A small agent whose decisions are made by a *Drosophila* (fruit fly) brain
simulation built on the public **FlyWire FAFB** connectome - the same wiring the
[`eonsystemspbc/fly-brain`](https://github.com/eonsystemspbc/fly-brain) project
uses.

The fly-brain emulation is large (the connectome is ~100 MB and the model has
138,639 neurons and ~15 million synapses), so it usually lives on its own
machine or GPU box. Childbot connects to it in whichever way fits:

| Mode | When to use | How |
|---|---|---|
| **Local engine** | Just want it to work | `python -m childbot "sweet sugar"` |
| **fly-brain checkout** | You already have fly-brain installed | set `CHILDBOT_FLYBRAIN_HOME` |
| **fly-brain service** | The model runs on another machine/GPU | set `CHILDBOT_FLYBRAIN_URL` |

All three return the same `BrainReading`, so the bot code does not change.

## What "connecting" means here

The brain decides, the bot talks. Concretely:

1. A situation string (e.g. `"sweet sugar"`, `"escape"`) is encoded as Poisson
   spike rates on real sensory neurons - sugar-gustatory receptor neurons
   (cell type `LB3`) or the `DNp01` giant-fibre escape neurons.
2. The LIF network runs for a short window over the FAFB connectome, using the
   exact equations from fly-brain's PyTorch runner
   (`PoissonSpikeGenerator -> alpha synapse + delay -> LIF with refractory`).
3. Childbot reads the response of the **descending-neuron population** (every
   neuron whose annotated cell type starts with `DN`) and turns the escape vs.
   non-escape rates into a decision: `avoid`, `approach`, or `idle`.
4. A tiny associative memory remembers situations so repeats are instant.

Neuron ids and cell types are checked against the public Codex annotation
(`codex/data/fafb/783/consolidated_cell_types.csv.gz`), not guessed.

## Install

```bash
pip install -r requirements.txt
```

Python 3.10+. No GPU required - the engine is NumPy/SciPy.

## Get the brain data

Two files from the fly-brain repository are needed (about 100 MB total):

```bash
mkdir -p data
curl -L -o data/2025_Completeness_783.csv \
  https://raw.githubusercontent.com/eonsystemspbc/fly-brain/main/data/2025_Completeness_783.csv
curl -L -o data/2025_Connectivity_783.parquet \
  https://raw.githubusercontent.com/eonsystemspbc/fly-brain/main/data/2025_Connectivity_783.parquet
```

The Codex cell-type annotation downloads itself on first run (about 1 MB). A
cached weight matrix (`data/weight_csr_783.npz`) is written on first load, which
makes later startups near-instant.

Childbot will also download the two files automatically if they are missing and
you leave downloads enabled.

## Run

```bash
# one decision
python -m childbot "sweet sugar" --duration-ms 200

# several, with a small fast slice of the brain
python -m childbot "escape" "sweet sugar" --subset-size 20000

# interactive, remembering what it learns
python -m childbot --interactive --memory .childbot_memory.json
```

Example output:

```json
{
  "situation": "escape",
  "decision": "avoid",
  "confidence": 0.99,
  "source": "brain",
  "channels": {
    "escape": {"rate_hz": 200.0, "spikes": 20},
    "descending": {"rate_hz": 1.1, "spikes": 16}
  },
  "simulated_ms": 100.0,
  "reply": "'escape' reads as a threat - backing away."
}
```

## Use an installed fly-brain checkout

If you already have fly-brain cloned and its conda env (`brain-fly`) set up:

```bash
export CHILDBOT_FLYBRAIN_HOME=/path/to/fly-brain
python -m childbot "sweet sugar"
```

Childbot imports the reusable paper model
(`code/paper-phil-drosophila/model.py`) and calls `run_exp` with the right
activation/silencing for the situation. If that import is not available it falls
back to running fly-brain's `main.py` and reading the spike parquet it writes.
Run Childbot with the same Python that has fly-brain's dependencies.

## Run the model on another machine (service)

On the machine with the model / GPU:

```bash
python -m childbot.service --host 0.0.0.0 --port 8077
# or serve an installed checkout:
python -m childbot.service --flybrain-home /path/to/fly-brain
```

On the machine running the bot:

```bash
export CHILDBOT_FLYBRAIN_URL=http://<model-host>:8077
python -m childbot "escape"
```

Endpoints: `GET /health`, `POST /decide` with
`{"situation": "...", "intensity": 1.0, "duration_ms": 100}`.

## Configuration

Every setting is an environment variable:

| Variable | Default | Meaning |
|---|---|---|
| `CHILDBOT_DATA_DIR` | `./data` | Where connectome and cache files live |
| `CHILDBOT_FLYBRAIN_HOME` | unset | Path to a fly-brain checkout |
| `CHILDBOT_FLYBRAIN_URL` | unset | URL of a running fly-brain service |
| `CHILDBOT_THREADS` | 0 (auto) | Worker threads |

Model constants (timestep, membrane time constant, weights) live in
`childbot/config.py` and default to fly-brain's values.

## Performance

The engine reproduces fly-brain's dynamics in NumPy. The recurrent input only
gathers the columns of neurons that spiked last step (from a CSC matrix) instead
of a full 15-million-synapse matvec, which is about 100x faster and
mathematically identical because the skipped columns are multiplied by zero.

A 100 ms decision over the full 138,639-neuron brain takes a few seconds on CPU.
Use `--subset-size N` to keep only the N most-connected neurons for a quick
smoke test. Note that a subset may not contain the specific sensory neurons a
label needs; the reading then reports them as `absent from connectome`.

## Tests

```bash
pip install pytest
PYTHONPATH=. python -m pytest tests/ -q
```

The tests run the real engine over the real connectome and annotations - no
mocks. They skip if the data files are missing.

## Layout

```
childbot/
  config.py       # parameters + env overrides
  connectome.py   # load FAFB data -> sparse weight matrix
  celltypes.py    # Codex cell-type annotations (DN population readout)
  neurons.py      # sensory/readout neuron ids
  lif.py          # LIF engine (fly-brain equations)
  brain.py        # FlyBrain (local) + FlyBrainRemote (HTTP)
  bridge.py       # FlyBrainBridge (installed fly-brain checkout)
  service.py      # HTTP service
  bot.py          # Childbot: memory + replies
  __main__.py     # CLI
tests/
  test_brain.py
```

## Notes and limits

- Childbot does not copy or vendor fly-brain's code; it talks to it (or to a
  checkout you already have) and reuses its published connectome data.
- The situation-to-stimulus encoder is deliberately simple and inspectable. It
  is the seam where a learned encoder could replace the keyword mapping.
- A short simulation window captures fast reflex-like paths well (escape is
  immediate); slower, polysynaptic feeding pathways may need a longer
  `--duration-ms`.
