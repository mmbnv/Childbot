# Fly-brain — данные коннектома

Здесь лежат данные коннектома **FlyWire FAFB v783** (мозг взрослой дрозофилы).
Из них `flybrain/` строит врождённый инстинкт существа (см. ниже). Данные
большие (сотни МБ), поэтому в git они **не хранятся** — папка создаётся
локально.

## Что должно лежать в этой папке

| Файл | Размер | Откуда |
|------|--------|--------|
| `2025_Completeness_783.csv` | ~3.4 МБ | [fly-brain](https://github.com/eonsystemspbc/fly-brain) `data/` |
| `2025_Connectivity_783.parquet` | ~97 МБ | [fly-brain](https://github.com/eonsystemspbc/fly-brain) `data/` |
| `weight_csr_783.npz` | ~116 МБ | кэш весов, создаётся сам при первом запуске |
| `consolidated_cell_types_783.csv.gz` | ~0.9 МБ | [FlyWire Codex](https://codex.flywire.ai/api/download?dataset=fafb), аннотации типов клеток (необязательно) |

Достаточно первых двух — движок соберёт веса и закэширует `weight_csr_783.npz`.
Аннотации нужны, чтобы находить конкретные типы нейронов (сладкие GRN,
нисходящие DNp09/DNp01) для каналов инстинкта.

## Как получить данные

**Вариант 1 — из репозитория fly-brain (быстрее, рекомендую):**

```bash
mkdir -p Fly-brain
cd Fly-brain
BASE=https://raw.githubusercontent.com/eonsystemspbc/fly-brain/main/data
curl -LO $BASE/2025_Completeness_783.csv
curl -LO $BASE/2025_Connectivity_783.parquet
```

**Вариант 2 — из FlyWire Codex (первоисточник):**

1. Откройте <https://codex.flywire.ai/api/download?dataset=fafb>.
2. Скачайте материалы датасета (completeness + connectivity) и положите в эту
   папку под именами из таблицы.
3. Дополнительно можно скачать `consolidated_cell_types_783.csv.gz`.

**Вариант 3 — автоматически из кода** (движок умеет докачивать базовые файлы):

```python
from flybrain import FlyBrainInstinct
FlyBrainInstinct(download=True)   # докачает недостающее в Fly-brain/
```

## Нет данных — не беда

Инстинкт необязателен. Если этой папки нет (или нет `scipy`), существо
работает как раньше: `FlyBrainInstinct.available == False`, а вызовы тихо
возвращают `None`. Тесты и `make test` проходят и без данных.

## Что строится из данных

`flybrain/` (см. `flybrain/README` в корне проекта и `AGENTS.md`):

- `connectome.py` — читает completeness/connectivity, строит разреженную
  матрицу весов (кэш `weight_csr_783.npz`);
- `celltypes.py` — сопоставляет типы клеток из аннотаций с индексами нейронов;
- `lif.py` / `engine.py` — leaky integrate-and-fire сеть; прогон стимула даёт
  частоты нисходящих нейронов (вперёд / бегство);
- `instinct.py` — переводит состояние ребёнка в стимул и обратно в знак
  «тянет / отвращает» для выбора действия.
