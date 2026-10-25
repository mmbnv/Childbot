"""Аннотации типов клеток FAFB (Codex).

Публичный релиз Codex даёт таблицу тип-на-нейрон
(``codex/data/fafb/783/consolidated_cell_types.csv.gz``). По ней мы читаем
НЕЙРОНЫ, а не угаданные id: сенсорные входы и нисходящий (моторный) выход.
"""

from __future__ import annotations

import csv
import gzip
from dataclasses import dataclass
from pathlib import Path

from flybrain.config import ANNOTATION_FILENAME, ANNOTATION_URL
from flybrain.connectome import download_file


@dataclass
class CellTypeIndex:
    """FlyWire root id -> основной тип клетки."""

    types: dict[int, str]

    def type_of(self, flywire_id: int) -> str:
        return self.types.get(int(flywire_id), "")

    def ids_with_prefix(self, prefix: str) -> list[int]:
        return [fid for fid, t in self.types.items() if t.startswith(prefix)]

    @classmethod
    def load(cls, data_dir: Path, *, download: bool = False) -> "CellTypeIndex":
        path = Path(data_dir) / ANNOTATION_FILENAME
        if download and not path.exists():
            download_file(ANNOTATION_URL, path)

        types: dict[int, str] = {}
        with gzip.open(path, "rt") as handle:
            reader = csv.reader(handle)
            next(reader, None)  # заголовок
            for row in reader:
                if len(row) >= 2 and row[1]:
                    types[int(row[0])] = row[1]
        return cls(types=types)
