"""flybrain — модель мозга дрозофилы (FlyWire FAFB) как ИНСТИНКТ существа.

Отдельный слой: ``core/`` — это выученный, «человеческий» мозг ребёнка
(драйвы, эмоции, предсказание, память). ``flybrain`` — врождённая, «насекомая»
подложка: реальный коннектом FAFB, по которому сигнал растекается сам, без
обучения. Существо получает быстрый «нутром чую» отклик на ситуацию, который
дополняет выученное решение, а не заменяет его.

Модуль необязателен: если данных коннектома нет или нет scipy, инстинкт тихо
выключается, и существо работает как раньше.

Импорты здесь ЛЕНИВЫЕ: тяжёлые зависимости (numpy/scipy/pandas) и движок
подгружаются только при создании движка, чтобы отсутствие scipy не ломало
импорт всего проекта.
"""

from flybrain.config import BrainConfig
from flybrain.instinct import FlyBrainInstinct, InstinctReading

__all__ = [
    "BrainConfig",
    "FlyBrainInstinct",
    "InstinctReading",
    "BrainReading",
    "ChannelReading",
    "FlyBrainEngine",
]

__version__ = "0.1.0"


def __getattr__(name):
    """Ленивый доступ к тяжёлым символам движка (numpy/scipy)."""
    if name in ("BrainReading", "ChannelReading", "FlyBrainEngine"):
        from flybrain import engine

        return getattr(engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
