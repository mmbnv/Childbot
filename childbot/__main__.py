"""Command-line interface for Childbot.

Examples
--------
Decide once, with a fast subset of the brain:

    python -m childbot "sweet sugar" --subset-size 5000

Run interactively and remember situations:

    python -m childbot --interactive --memory .childbot_memory.json

Use an installed fly-brain checkout:

    CHILDBOT_FLYBRAIN_HOME=/path/to/fly-brain python -m childbot "escape"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from childbot.bot import Childbot, build_brain
from childbot.config import BrainConfig


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="childbot", description="Fly-brain-driven agent")
    parser.add_argument("situation", nargs="*", help="One or more situations to react to")
    parser.add_argument("--subset-size", type=int, default=None,
                        help="Use only the N most-connected neurons (fast runs)")
    parser.add_argument("--duration-ms", type=float, default=100.0,
                        help="Simulation window per decision, ms")
    parser.add_argument("--intensity", type=float, default=1.0,
                        help="Stimulus intensity, 0..1")
    parser.add_argument("--memory", type=Path, default=None,
                        help="JSON file to persist the associative memory")
    parser.add_argument("--interactive", action="store_true",
                        help="Read situations from stdin until EOF")
    parser.add_argument("--no-download", action="store_true",
                        help="Require connectome data to already be present")
    args = parser.parse_args(argv)

    config = BrainConfig()
    if args.subset_size:
        config = config.with_(subset_size=args.subset_size)

    brain = build_brain(config, download=not args.no_download)
    bot = Childbot(brain=brain, config=config, memory_path=args.memory)

    situations = list(args.situation)
    if args.interactive:
        situations.extend(line.strip() for line in sys.stdin if line.strip())
    if not situations:
        situations = ["sweet sugar"]

    for situation in situations:
        result = bot.respond(
            situation, intensity=args.intensity, duration_ms=args.duration_ms
        )
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
