"""
BrainRegions — распределённый мозг вместо одной «коробки решений».

Почему так, а не как раньше. Три работы 2025–2026 годов показали одно и то же:
решение — это не конвейер «сенсор → фронтальная кора → мотор», а работа МНОГИХ
областей сразу, связанных в обе стороны.

  * International Brain Laboratory (Nature 645, 177–191 и 192–200, 2025):
    записали 621 733 нейрона в 279 областях. Сигналы ВЫБОРА возникают
    одновременно в коре и подкорке (стриатум, верхний холм, средний мозг);
    моторное действие и награда представлены ГЛОБАЛЬНО; зрительная информация
    сначала кратко живёт в сенсорных зонах, а затем в среднем/заднем мозге
    нарастает (ramping) — это и есть накопление свидетельств. Субъективный
    ПРИОР кодируется в 20–30% областей и зависит от ПРОШЛЫХ 5–6 выборов,
    а не только от последнего (байесовские петли между областями).

  * Dalla Porta et al. (PNAS 123(28):e2532072123, 2026): мозг ГЕТЕРОГЕНЕН —
    разные области имеют разную возбудимость и адаптацию (по холинергическим
    картам). Эта гетерогенность (а не однородный шум) даёт синхронизацию и
    усиливает поток информации. И она же порождает ЛОКАЛЬНЫЙ сон: отдельные
    области «засыпают» медленными волнами прямо внутри бодрствования.

  * Armstrong & Vlasov (PNAS 2026): активность решения видна уже в первичной
    соматосенсорной коре, и туда идёт НИСХОДЯЩАЯ обратная связь. Значит,
    обработка двунаправленна.

Что здесь реализовано:
  * несколько функциональных областей, у каждой своя возбудимость и адаптация
    (гетерогенность из характера — у каждого существа своя «нейрохимия»);
  * связи между областями с весами (структурная связность), включая НИСХОДЯЩИЕ
    (top-down) — поэтому сенсорные зоны «видят» ожидания, а не только стимул;
  * накопление свидетельств с «ramp» — моторный сигнал растёт, пока не созреет;
  * глобальный broadcast: победивший сигнал транслируется всем (это GWT);
  * распределённое ГОЛОСОВАНИЕ за действие: каждая область добавляет свой
    вклад, а не одна инстанция решает за всех;
  * локальный сон: перегруженная (адаптированная) область временно уходит в
    «офлайн» и её голос слабеет — это разгружает и консолидирует.
"""
import random


def clip01(v):
    return max(0.0, min(1.0, v))


# Структурная связность: кто на кого влияет и с каким весом.
# Двунаправленность — принципиальна (PNAS про обратную связь в S1).
CONNECTIVITY = {
    'sensory':      {'association': 1.0, 'value': 0.4, 'arousal': 0.6},
    'arousal':      {'sensory': 0.8, 'association': 0.7, 'motor': 0.6, 'value': 0.3},
    'value':        {'association': 0.9, 'motor': 0.7, 'sensory': 0.3},   # ↓ top-down
    'association':  {'sensory': 0.5, 'motor': 1.0, 'value': 0.6},          # ↓ top-down
    'motor':        {'association': 0.4, 'value': 0.3},
}


class Region:
    """Одна область: своя возбудимость, адаптация, входы и голос."""

    def __init__(self, name, kind, baseline, adaptation_rate=0.12, recovery=0.06):
        self.name = name
        self.kind = kind
        self.baseline = clip01(baseline)   # гетерогенность: у всех разная
        self.activation = 0.0              # текущая активность
        self.adaptation = 0.0              # усталость (накапливается от работы)
        self.adaptation_rate = adaptation_rate
        self.recovery = recovery
        self.asleep = False                # локальный сон (PNAS 2026)
        self.last_input = 0.0
        self.evidence = 0.0                # накопление свидетельств (ramp)

    def excitability(self):
        """Возбудимость = базис, ослабленный адаптацией; во сне почти ноль."""
        if self.asleep:
            return self.baseline * 0.15
        return clip01(self.baseline - self.adaptation)

    def receive(self, signal):
        """Принять вход от мира или другой области."""
        self.last_input = signal
        # Возбудимость поднимает слабый сигнал: гетерогенность важна (PNAS 2026).
        drive = min(1.0, signal * self.excitability() * 1.6)
        # Накопление с утечкой: сигнал растёт, пока приходит (ramp), иначе гаснет.
        self.evidence = clip01(self.evidence * 0.85 + drive * 0.45)
        self.activation = clip01(0.6 * self.activation + 0.5 * drive)
        self.adaptation = clip01(self.adaptation + self.adaptation_rate * self.activation)

    def rest(self):
        """Отдых: адаптация спадает, свидетельство тает."""
        self.adaptation = clip01(self.adaptation - self.recovery)
        self.evidence *= 0.9
        self.activation *= 0.85

    def maybe_local_sleep(self, threshold=0.6):
        """Перегруженная область «засыпает» медленными волнами (локальный сон)."""
        if self.asleep:
            return
        if self.adaptation > threshold and self.activation < 0.2:
            self.asleep = True

    def wake(self):
        if self.asleep and self.adaptation < 0.35:
            self.asleep = False


class BrainRegions:
    """Распределённая сеть областей, принимающая решение вместе."""

    def __init__(self, temperament=None, seed=None):
        self.temperament = temperament
        if seed is not None:
            random.seed(seed)
        # Гетерогенность берём из характера: у существа своя «нейрохимия»
        # областей, а не одинаковая у всех (PNAS 2026).
        t = temperament.t if temperament else (lambda k: 0.5)
        self.regions = {
            'sensory': Region('sensory', 'sensory', 0.5 + 0.4 * t('openness')),
            'arousal': Region('arousal', 'arousal', 0.5 + 0.4 * t('neuroticism')),
            'value': Region('value', 'value', 0.5 + 0.4 * t('conscientiousness')),
            'association': Region('association', 'association',
                                  0.5 + 0.4 * t('openness')),
            'motor': Region('motor', 'motor', 0.5 + 0.4 * t('extraversion')),
        }
        self.broadcast = None          # победивший сигнал (глобальное пространство)
        self.ramp = 0.0                # «ramping» моторного свидетельства
        self.ticks = 0
        self.local_sleeps = 0

    # ---------- ВНЕШНИЙ ВХОД ----------

    def sense(self, features):
        """Внешний мир → сенсорные области (bottom-up)."""
        self.regions['sensory'].receive(features.get('stimulus', 0.0))
        self.regions['arousal'].receive(features.get('urgency', 0.0))

    # ---------- ОДИН ТАКТ СЕТИ ----------

    def tick(self, features, reward=0.0):
        """
        Прожить такт: сенсорный вход → распространение по связям (в обе
        стороны) → broadcast → накопление моторного свидетельства.
        """
        self.ticks += 1
        self.sense(features)
        # Награда/исход — глобальный сигнал (IBL: reward представлен повсюду).
        self.regions['value'].receive(reward)
        # Ассоциативная кора сводит сенсорику и ценность.
        self.regions['association'].receive(
            0.5 * self.regions['sensory'].activation
            + 0.5 * self.regions['value'].activation)

        # Распространение по структурной связности — с НИСХОДЯЩИМИ связями.
        incoming = {}
        for src, dsts in CONNECTIVITY.items():
            act = self.regions[src].activation
            if act <= 0.0:
                continue
            for dst, w in dsts.items():
                incoming[dst] = incoming.get(dst, 0.0) + w * act
        for name, sig in incoming.items():
            self.regions[name].receive(sig / 2.0)

        # Моторная область накапливает свидетельство к решению (ramp).
        drive = (0.5 * self.regions['association'].evidence
                 + 0.5 * self.regions['value'].evidence
                 + 0.3 * self.regions['arousal'].evidence)
        self.ramp = clip01(self.ramp * 0.7 + drive * 0.3)
        self.regions['motor'].receive(self.ramp)

        # Глобальный broadcast: самый активный сигнал становится общим.
        winner = max(self.regions.values(), key=lambda r: r.activation)
        self.broadcast = (winner.name, winner.activation)

        # Локальный сон и отдых областей.
        for r in self.regions.values():
            r.maybe_local_sleep()
            if r.asleep:
                self.local_sleeps += 1
                r.rest()
                r.wake()
            elif self.ticks % 3 == 0:
                r.rest()
        return self.broadcast

    # ---------- РАСПРЕДЕЛЁННОЕ ГОЛОСОВАНИЕ ----------

    def vote(self, action, drives, state):
        """
        Вклад областей в выбор действия. Решение распределено: каждая область
        добавляет своё, и итог — сумма, а не приказ одной инстанции.
        """
        bias = 0.0
        s = self.regions['sensory'].evidence
        a = self.regions['association'].evidence
        v = self.regions['value'].evidence
        m = self.regions['motor'].evidence
        r = self.regions['arousal'].evidence

        # Ассоциативная кора и ценность: общий вклад в «разумное» действие.
        if action in ('gather', 'dig_tree', 'craft', 'eat_food', 'use', 'interact',
                      'place_block', 'build_shelter', 'hold_item', 'equip_best_armor'):
            bias += 0.5 * a + 0.4 * v
        # Моторная готовность: двигательные действия (ramp копит намерение).
        if action.startswith(('step', 'jump', 'sprint', 'go_to', 'come_close',
                              'walk_away', 'spin', 'look')):
            bias += 0.6 * m
        # Возбуждение: реакции на угрозу/боль.
        if action in ('flee_from_hostile', 'attack_hostile', 'attack_nearest',
                      'find_and_attack', 'escape_pit', 'force_break_out'):
            bias += 0.7 * r
        # Сенсорное свидетельство: исследование и внимание к новому.
        if action in ('look_around', 'look_up', 'look_down', 'look_at_player'):
            bias += 0.4 * s
        return bias

    # ---------- ОТЧЁТ ----------

    def state(self):
        return {n: {'act': round(r.activation, 2), 'ex': round(r.excitability(), 2),
                    'adapt': round(r.adaptation, 2), 'asleep': r.asleep}
                for n, r in self.regions.items()}

    def summary(self):
        awake = sum(1 for r in self.regions.values() if not r.asleep)
        b = self.broadcast or ('—', 0.0)
        return (f"мозг: {awake}/{len(self.regions)} областей бодрствуют, "
                f"фокус {b[0]} ({b[1]:.2f}), ramp {self.ramp:.2f}, "
                f"локальных снов {self.local_sleeps}")
