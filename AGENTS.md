# AGENTS.md

Persistent notes for agents working in this repository.

## What this repo is

`Childbot` is an agent whose decisions come from a *Drosophila* brain model
built on the public **FlyWire FAFB v783** connectome. It connects to the
`eonsystemspbc/fly-brain` project in three ways: a local NumPy engine, a bridge
to an installed fly-brain checkout, and an HTTP service.

## Layout

- `childbot/connectome.py` - loads `2025_Completeness_783.csv` +
  `2025_Connectivity_783.parquet` into a sparse matrix. `weights[i, j]` is the
  weight from presynaptic `j` onto postsynaptic `i` (rows = postsynaptic).
- `childbot/lif.py` - LIF engine, numerically matched to fly-brain's
  `code/run_pytorch.py`. `FlyBrain.decide()` calls `network.reset()` first, so
  decisions are independent and reproducible per `seed`.
- `childbot/celltypes.py` - Codex `consolidated_cell_types` annotations.
- `childbot/brain.py` - `FlyBrain` (local) and `FlyBrainRemote` (HTTP).
- `childbot/bridge.py` - `FlyBrainBridge` for an installed fly-brain checkout.
- `childbot/service.py` - stdlib HTTP service (`python -m childbot.service`).
- `childbot/bot.py` - `Childbot`: memory + replies.

## Environment

- Run with `PYTHONPATH=.` from the repo root (not installed as a package).
- Deps: `numpy scipy pandas pyarrow` (see `requirements.txt`); `pytest` for tests.
- Connectome data lives in `data/` and is **gitignored** (large, downloadable).
  Tests skip when it is absent. A `data/weight_csr_783.npz` cache is built on
  first load; delete it to rebuild.
- `--subset-size N` keeps the N most-connected neurons for fast runs, but may
  drop the specific sensory neurons a label needs.

## Commands

```bash
pip install -r requirements.txt
PYTHONPATH=. python -m childbot "escape" --no-download
PYTHONPATH=. python -m pytest tests/ -q
```

## Gotchas

- The readout uses the whole descending-neuron (`DN*`) population, split into
  `DNp01` (escape) vs. the rest. Do not hardcode two ids for the readout.
- The recurrent input gathers CSC columns for only the neurons that spiked last
  step (~100x faster than a full 15M-synapse matvec, mathematically identical).
  `silence()` must refresh `_weights_csc` as well as `weights`.
- `data/` files are large; never commit them.
