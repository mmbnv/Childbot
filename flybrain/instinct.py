"""Инстинкт: врождённый отклик fly-brain на текущую ситуацию ребёнка.

Это шов между двумя мозгами. Выученный мозг ребёнка (``core/``) знает про
драйвы, эмоции и предсказание, но не про коннектом. ``FlyBrainInstinct``
переводит состояние ребёнка в стимул для FAFB-модели и обратно — в
эмоциональный знак («тянет» или «отвращает») и небольшой сдвиг выбора.

Почему так, а не «fly-brain решает за ребёнка». Врождённое и выученное в
мозге работают вместе: инстинкт даёт быстрый, необучаемый ответ «нутром чую»,
а выученная кора — медленный, обдуманный. Инстинкт поэтому лишь СМЕЩАЕТ
решение (маленький бонус к оценке действия), а не приказывает.

Инстинкт необязателен: если данных коннектома нет или нет scipy, он тихо
выключается (``available == False``) и существо работает как раньше.
"""

from __future__ import annotations

from dataclasses import dataclass

from flybrain.config import BrainConfig

# Насколько сильно инстинкт смещает выбор действия (небольшой вклад).
BIAS_STRENGTH = 0.25

# Действия, согласные «избеганию» и «движению вперёд».
AVOID_ACTIONS = frozenset({
    "flee_from_hostile", "attack_hostile", "walk_away_from_player",
    "escape_pit", "force_break_out", "step_back", "build_shelter",
})
APPROACH_ACTIONS = frozenset({
    "step_forward", "come_close_to_player", "go_to_player", "dig_tree",
    "gather", "eat_food", "find_and_attack", "jump_forward", "sprint_short",
    "look_around", "dig_nearby", "dig_forward",
})


@dataclass
class InstinctReading:
    """Знак инстинкта: куда тянет и насколько уверенно."""

    valence: float          # -1 (отвращает) .. +1 (тянет)
    decision: str           # 'avoid' | 'approach' | 'idle'
    confidence: float
    forward_hz: float
    escape_hz: float
    note: str = ""

    def bias_for(self, action: str) -> float:
        """Сдвиг оценки действия по знаку инстинкта (маленький).

        Знак задаёт решение, величину — уверенность: инстинкт «подталкивает»
        согласные действия и притормаживает противоположные. Для ``avoid``
        согласны действия бегства, для ``approach`` — движения/добычи.
        """
        if self.decision == "idle":
            return 0.0
        magnitude = BIAS_STRENGTH * self.confidence
        if self.decision == "avoid":
            if action in AVOID_ACTIONS:
                return magnitude
            if action in APPROACH_ACTIONS:
                return -magnitude
        elif self.decision == "approach":
            if action in APPROACH_ACTIONS:
                return magnitude
            if action in AVOID_ACTIONS:
                return -magnitude
        return 0.0


class FlyBrainInstinct:
    """Врождённый инстинкт поверх коннектома FAFB (необязательный слой)."""

    def __init__(
        self,
        config: BrainConfig | None = None,
        *,
        duration_ms: float = 40.0,
        refresh_every: int = 10,
        download: bool = False,
    ):
        self.config = config or BrainConfig()
        self.duration_ms = duration_ms
        self.refresh_every = max(1, refresh_every)
        self.download = download
        self._engine = None
        self._error: str | None = None
        self._last: InstinctReading | None = None
        self._last_step = -10**9
        self.runs = 0

    # ---------- ДОСТУПНОСТЬ ----------

    @property
    def available(self) -> bool:
        """Готов ли инстинкт (движок загружен и данные на месте)."""
        if self._engine is not None:
            return True
        if self._error is not None:
            return False
        return self.config.data_available()

    @property
    def error(self) -> str | None:
        return self._error

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            from flybrain.engine import FlyBrainEngine

            self._engine = FlyBrainEngine(self.config, download=self.download)
        except Exception as exc:  # нет данных/scipy — тихо выключаемся
            self._error = str(exc)
            return None
        return self._engine

    # ---------- СОСТОЯНИЕ → СТИМУЛ ----------

    @staticmethod
    def stimuli_from_state(state: dict, drives) -> dict[str, float]:
        """Перевести состояние ребёнка в стимул для FAFB-модели.

        Сладкое → «еда рядом / хочу есть». Бегство → «угроза» (боль, страх,
        враг, мало здоровья). Ходьба → «любопытство/скука» (тяга идти и
        исследовать).
        """
        d = drives.to_dict() if hasattr(drives, "to_dict") else dict(drives)
        hunger = float(d.get("hunger", 0.0))
        fear = float(d.get("fear", 0.0))
        pain = float(d.get("pain", 0.0))
        curiosity = float(d.get("curiosity", 0.0))
        boredom = float(d.get("boredom", 0.0))

        health = state.get("health", 20) or 20
        food = state.get("food", 20) or 20
        hostile = state.get("nearest_hostile")
        player = state.get("player")

        # Угроза — врождённый безусловный стимул.
        threat = max(fear, pain)
        if hostile:
            dist = hostile.get("distance", 99)
            threat = max(threat, 0.9 if dist < 8 else 0.5)
        if health < 8:
            threat = max(threat, 0.8)
        if player and player.get("distance", 999) < 8 and fear > 0.4:
            threat = max(threat, 0.6)

        # Еда: хочу есть и она доступна (в руке/рядом).
        food_available = food > 12
        sugar = 0.0
        if hunger > 0.3 and food_available:
            sugar = min(1.0, hunger + 0.2)
        elif hunger > 0.5:
            sugar = min(1.0, hunger)

        walk = max(curiosity, boredom)

        stimuli: dict[str, float] = {}
        if threat > 0.05:
            stimuli["escape"] = threat
        if sugar > 0.05:
            stimuli["sugar"] = sugar
        if walk > 0.05:
            stimuli["walk"] = walk
        return stimuli

    # ---------- СТИМУЛ → ЗНАК ----------

    def feel(self, state: dict, drives, step: int) -> InstinctReading | None:
        """Прожить инстинкт на текущей ситуации (с кэшем на ``refresh_every``).

        Возвращает ``InstinctReading`` или ``None``, если инстинкт недоступен.
        """
        engine = self._ensure_engine()
        if engine is None:
            return None

        if self._last is not None and step - self._last_step < self.refresh_every:
            return self._last

        stimuli = self.stimuli_from_state(state, drives)
        if not stimuli:
            reading = InstinctReading(0.0, "idle", 0.0, 0.0, 0.0)
        else:
            result = engine.run(stimuli, duration_ms=self.duration_ms)
            forward = result.channel_rate("descending")
            escape = result.channel_rate("escape")
            valence = 0.0
            total = forward + escape
            if total > 0:
                valence = (forward - escape) / total
            reading = InstinctReading(
                valence=valence,
                decision=result.decision,
                confidence=result.confidence,
                forward_hz=forward,
                escape_hz=escape,
                note=result.note,
            )

        self._last = reading
        self._last_step = step
        self.runs += 1
        return reading

    @property
    def last(self) -> InstinctReading | None:
        return self._last

    def summary(self) -> str:
        if not self.config.data_available():
            return "инстинкт fly-brain: выключен (нет данных коннектома)"
        if self._engine is None and self._error is None:
            self._ensure_engine()
        if self._error is not None:
            return f"инстинкт fly-brain: выключен ({self._error})"
        last = self._last
        if last is None:
            return f"инстинкт fly-brain: готов, {self.runs} прогонов"
        sign = "тянет" if last.valence > 0.05 else ("отвращает" if last.valence < -0.05 else "нейтрально")
        return (
            f"инстинкт fly-brain: {sign} ({last.valence:+.2f}), "
            f"вперёд {last.forward_hz:.1f}Гц бегство {last.escape_hz:.1f}Гц, "
            f"прогонов {self.runs}"
        )
