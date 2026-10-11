"""
Imagination — воображение: «путешествие в уме» вперёд и назад во времени.

Человек не живёт только «сейчас». Он вспоминает прошлое и ПРЕДСТАВЛЯЕТ
будущее: «если я сейчас не поем, через десять шагов будет совсем плохо»,
«если пойду туда, найду еду», «чем это может кончиться?». Это проспективное
мышление (prospection) — основа предусмотрительности и настоящего
целеустремлённого поведения. Та же нейронная машина, что «прокручивает» план,
строит и воображаемую игру.

Здесь три способности:

  * ПРЕДВИДЕНИЕ НУЖДЫ. Симуляция: как вырастут драйвы, если ничего не делать.
    Так существо заботится о будущем, а не только о текущем «болит/не болит».

  * ПЛАНИРОВАНИЕ ЦЕПОЧКИ. Мысленный перебор последовательностей действий и
    выбор той, что ведёт к цели с наименьшей ценой (целенаправленное поведение,
    а не реакция).

  * ВООБРАЖЕНИЕ ЦЕЛИ. Построить воображаемый сценарий достижения желаемого
    (как ребёнок строит замок в голове) и развернуть его в шаги.

Всё это опирается на predictor.simulate/rollout и знание причин (causality):
воображение не выдумывает магию, а комбинирует то, чему существо научилось.
"""
import random
import time

from core.drives import Drives


# Действия, которые могут утолить нужду (для перебора цепочек).
NEED_ACTIONS = {
    'hunger': ['eat_food', 'find_and_attack', 'gather'],
    'loneliness': ['go_to_player', 'come_close_to_player'],
    'fear': ['flee_from_hostile', 'go_to_player', 'build_shelter'],
    'fatigue': ['wait_1sec', 'build_shelter'],
    'boredom': ['step_forward', 'dig_nearby', 'look_around'],
    'curiosity': ['step_forward', 'look_around'],
    'pain': ['eat_food', 'flee_from_hostile'],
}

DRIVES = list(Drives().to_dict().keys())
# Скорость роста нужды за шаг (для предвидения). Совпадает по духу с Drives.
GROWTH = {'hunger': 0.012, 'loneliness': 0.014, 'boredom': 0.015,
          'fatigue': 0.012, 'fear': 0.0, 'pain': 0.0, 'curiosity': 0.006,
          'comfort': 0.0}
WEIGHTS = {'fear': 1.5, 'pain': 1.4, 'hunger': 1.2, 'loneliness': 1.0,
           'fatigue': 0.9, 'boredom': 0.7, 'curiosity': 0.5, 'comfort': -1.0}


class Imagination:
    """Мысленное «путешествие во времени»: вспомнить, представить, спланировать."""

    def __init__(self, predictor=None, causality=None, catalog=None):
        self.predictor = predictor
        self.causality = causality
        self.catalog = catalog
        self.last_forecast = None
        self.last_forecast_step = -99
        self.anticipated = None      # о чём я «позаботился заранее»
        self.imagined_scenarios = 0
        self._last_anticipate_step = -99
        self.anticipate_cooldown = 12   # шагов между «заглядываниями вперёд»

    # ============ ПРЕДВИДЕНИЕ НУЖДЫ ============

    def forecast(self, drives, state, horizon=20):
        """Как будет через `horizon` шагов, если ничего не делать.

        Возвращает словарь драйвов «в будущем» — то, что существо представляет.
        """
        d = drives.to_dict()
        future = dict(d)
        for _ in range(horizon):
            for k, rate in GROWTH.items():
                future[k] = min(1.0, future.get(k, 0.0) + rate)
            # страх/боль сами не растут без угрозы — их «предвидим» как есть
        self.last_forecast = future
        return future

    def future_tension(self, drives, state, horizon=20):
        fut = self.forecast(drives, state, horizon)
        return sum(fut[k] * WEIGHTS.get(k, 0.0) for k in WEIGHTS)

    def current_tension(self, drives):
        d = drives.to_dict()
        return sum(d[k] * WEIGHTS.get(k, 0.0) for k in WEIGHTS)

    def anticipate(self, drives, state, step, horizon=45):
        """
        Заметить, что нужда В БУДУЩЕМ станет большой, и озаботиться заранее.

        Это человеческая предусмотрительность: «пока не хочется есть, но скоро
        захочется — позабочусь». Возвращает имя нужды или None.
        """
        # Заглядываем вперёд не каждый шаг, а время от времени — как человек,
        # который не думает о будущем непрерывно, но и не забывает о нём.
        if step - self._last_anticipate_step < self.anticipate_cooldown:
            return None
        self._last_anticipate_step = step

        d = drives.to_dict()
        # Не тревожимся о том, что уже и так сильно — этим займётся реакция.
        fut = self.forecast(drives, state, horizon)
        urgent_now = max((d[k] for k in ('hunger', 'loneliness', 'fatigue')), default=0)
        if urgent_now > 0.55:
            return None
        worst, worst_val = None, 0.0
        for k in ('hunger', 'loneliness', 'fatigue', 'boredom'):
            gain = fut[k] - d[k]
            # Заботимся заранее, когда нужда ещё умеренна, но в обозримом
            # будущем станет большой.
            if 0.2 < d[k] < 0.8 and fut[k] > 0.72 and gain > 0.05 \
                    and fut[k] * WEIGHTS[k] > worst_val:
                worst, worst_val = k, fut[k] * WEIGHTS[k]
        if worst:
            self.anticipated = (worst, step)
            self.last_forecast_step = step
        return worst

    # ============ ПЛАНИРОВАНИЕ ЦЕПОЧКИ ============

    def plan_chain(self, drives, state, goal_drive, depth=3, candidates=None):
        """
        Перебрать в уме цепочки действий и выбрать ведущую к цели.

        goal_drive — какую нужду хотим снизить. Возвращает список действий
        (план) или None. Это целенаправленный поиск, а не реакция на стимул.
        """
        if not self.predictor:
            return None
        pool = candidates or NEED_ACTIONS.get(goal_drive, [])
        pool = [a for a in pool if not self.catalog or self.catalog.has(a)]
        if not pool:
            return None

        best_plan, best_score = None, 1e9
        # Жадный поиск в глубину по «мысленной симуляции».
        frontier = [([], drives.to_dict())]
        for _ in range(depth):
            new_frontier = []
            for path, cur in frontier:
                for a in pool:
                    relief = self.predictor.simulate(a, cur, state)
                    nxt = dict(cur)
                    for i, k in enumerate(DRIVES):
                        try:
                            nxt[k] = max(0.0, nxt[k] - float(relief[i]))
                        except Exception:
                            pass
                    new_path = path + [a]
                    score = sum(nxt[k] * WEIGHTS.get(k, 0.0) for k in WEIGHTS)
                    if score < best_score:
                        best_score, best_plan = score, new_path
                    new_frontier.append((new_path, nxt))
            # Держим поиск узким — как реальное внимание (не перебираем всё).
            new_frontier.sort(key=lambda p: sum(p[1][k] * WEIGHTS.get(k, 0.0) for k in WEIGHTS))
            frontier = new_frontier[:6]
        return best_plan

    # ============ ВООБРАЖЕНИЕ ЦЕЛИ ============

    def imagine_goal(self, drives, state, goal_drive):
        """
        Построить воображаемый сценарий: как я добьюсь желаемого.

        Возвращает (описание, [шаги]) — «в голове я уже это сделал». Если
        воображение не находит пути, возвращает (None, None) — не выдумываем.
        """
        plan = self.plan_chain(drives, state, goal_drive)
        if not plan:
            return None, None
        self.imagined_scenarios += 1
        names = {
            'hunger': 'как я поем', 'loneliness': 'как я буду рядом с папой',
            'fear': 'как я спасусь', 'fatigue': 'как я отдохну',
            'boredom': 'чем я займусь', 'curiosity': 'что я найду',
            'pain': 'как мне станет легче',
        }
        return names.get(goal_drive, 'что я сделаю'), plan

    def summary(self):
        if not self.last_forecast:
            return "воображение: пока не заглядывал вперёд"
        d = self.last_forecast
        worst = max(d, key=lambda k: d[k] * WEIGHTS.get(k, 0.0))
        return (f"воображение: представляю будущее (сильнее всего — {worst} "
                f"{d[worst]:.2f}), сценариев {self.imagined_scenarios}")
