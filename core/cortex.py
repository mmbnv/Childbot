"""
Cortex — моторное решение (что делать прямо сейчас).

Выбор действия соединяет три вещи, как в реальном мозге:
  1. предсказание облегчения (predictor — «мысленная примерка»);
  2. уверенность в себе (self_model — «получится ли у меня»);
  3. нейромодуляцию (exploration — «тяга к новому», patience — «терпение»).

После действия cortex.observe() сравнивает ожидание и реальность и учит
предсказательную модель (дофаминовая ошибка).
"""
import random
import time


ACTION_POOL = [
    'step_forward', 'step_back', 'step_left', 'step_right',
    'jump_once', 'jump_forward', 'sprint_short', 'sneak',
    'go_to_player', 'walk_away_from_player', 'come_close_to_player',
    'stay_here', 'look_at_player', 'look_around',
    'dig_forward', 'dig_down', 'dig_up', 'dig_nearby', 'dig_tree',
    'escape_pit', 'place_block', 'build_shelter',
    'drop_item', 'eat_food', 'equip_best_armor', 'hold_item',
    'attack_nearest', 'find_and_attack',
    'flee_from_hostile', 'attack_hostile',
    'look_up', 'look_down', 'spin_around', 'stop',
]


class Cortex:
    def __init__(self, adapter, drives, neuromod, predictor, self_model, world_model, catalog):
        self.adapter = adapter
        self.drives = drives
        self.neuromod = neuromod
        self.predictor = predictor
        self.self_model = self_model
        self.world_model = world_model
        self.catalog = catalog

        self.pending_action = None
        self.pending_drives_before = None
        self.pending_context = None
        self.pending_prediction = None
        self.pending_time = 0

    def snapshot_drives(self):
        return self.drives.to_dict()

    def _snapshot_context(self):
        try:
            return self.adapter.get_state() or {}
        except Exception:
            return {}

    def choose_action(self, state):
        drives_now = self.drives.to_dict()
        candidates = [a for a in ACTION_POOL if self.catalog.has(a)]
        if not candidates:
            return 'stay_here'

        # 1. Мысленная примерка: предсказанный прирост облегчения
        best, best_gain = self.predictor.best_action(drives_now, state, candidates)

        # 2. Добавляем уверенность в себе и любопытство (exploration)
        scored = []
        exploration = self.neuromod.exploration()
        for a in candidates:
            relief = self.predictor.predict_relief(a, drives_now, state)
            conf = self.self_model.confidence(a)
            novelty_bonus = exploration * 0.15 * (1.0 - conf)
            noise = exploration * 0.1 * (0.5 - random.random())
            scored.append((a, relief + conf * 0.1 + novelty_bonus + noise))

        scored.sort(key=lambda x: -x[1])
        top_n = min(3, len(scored))
        chosen = random.choice(scored[:top_n])
        return chosen[0]

    def act(self, action, params=None):
        self.pending_action = action
        self.pending_drives_before = self.snapshot_drives()
        self.pending_context = self._snapshot_context()
        self.pending_prediction = self.predictor.simulate(
            action, self.pending_drives_before, self.pending_context)
        self.pending_time = time.time()

        return self.adapter.action(action, params=params)

    def observe(self):
        """Сравнить ожидание и реальность, обучить предсказание (дофамин)."""
        if not self.pending_action:
            return None
        if time.time() - self.pending_time < 0.4:
            return None

        drives_after = self.drives.to_dict()
        drives_before = self.pending_drives_before
        context = self.pending_context
        action = self.pending_action
        prediction = self.pending_prediction

        # Ошибка предсказания по каждому драйву
        total_pred_error = 0.0
        for i, drive in enumerate(drives_before):
            before = drives_before[drive]
            after = drives_after[drive]
            if before < 0.15:
                continue
            drop = before - after
            relief_amount = min(1.0, drop / max(before, 0.01)) if drop > 0 else 0.0
            self.predictor.observe_relief(
                action, drive, context, relief_amount,
                learning_rate=self.neuromod.learning_rate())
            if prediction is not None and i < len(prediction):
                total_pred_error += abs(float(prediction[i]) - relief_amount)

        # Дофаминовая ошибка: сбылось ли предсказание?
        tension_before = sum(drives_before.values())
        tension_after = sum(drives_after.values())
        delta = tension_before - tension_after
        reward = max(0.0, min(1.0, 0.5 + delta * 2))
        self.neuromod.reward(0.5, reward)

        self.pending_action = None
        self.pending_prediction = None
        return delta
