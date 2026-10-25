"""Cell-type annotations for the FAFB connectome.

The public Codex release ships a per-neuron type table
(``codex/data/fafb/783/consolidated_cell_types.csv.gz``). Childbot uses it to
read the brain's *descending* output as a population instead of two hand-picked
neurons, so decisions reflect what the whole brain does rather than a single
guessed id.
"""

from __future__ import annotations

import csv
import gzip
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ANNOTATION_URL = (
    "https://storage.googleapis.com/flywire-data/codex/data/fafb/783/"
    "consolidated_cell_types.csv.gz"
)
ANNOTATION_FILENAME = "consolidated_cell_types_783.csv.gz"


@dataclass
class CellTypeIndex:
    """Maps FlyWire root id -> primary cell type."""

    types: dict[int, str]

    def type_of(self, flywire_id: int) -> str:
        return self.types.get(int(flywire_id), "")

    def ids_with_prefix(self, prefix: str) -> list[int]:
        return [fid for fid, t in self.types.items() if t.startswith(prefix)]

    @classmethod
    def load(
        cls,
        data_dir: Path,
        *,
        download: bool = True,
    ) -> "CellTypeIndex":
        path = Path(data_dir) / ANNOTATION_FILENAME
        if download and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            request = urllib.request.Request(
                ANNOTATION_URL, headers={"User-Agent": "childbot/0.1"}
            )
            with urllib.request.urlopen(request, timeout=300) as response, open(
                tmp, "wb"
            ) as out:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            tmp.replace(path)

        types: dict[int, str] = {}
        with gzip.open(path, "rt") as handle:
            reader = csv.reader(handle)
            next(reader, None)  # header
            for row in reader:
                if len(row) >= 2 and row[1]:
                    types[int(row[0])] = row[1]
        return cls(types=types)
