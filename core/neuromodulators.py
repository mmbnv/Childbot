"""
Neuromodulators — химия мозга + эмоции.

Нейромодуляторы — это не «настроение вообще», а конкретные системы:

  * dopamine      — предсказание награды (ошибка предсказания → обучение)
  * serotonin     — удовлетворённость, стабильность, терпение
  * noradrenaline — бодрость, реакция на новизну и угрозу, «включайся»
  * acetylcholine — внимание и пластичность («учись сейчас»)
  * cortisol      — стресс, мобилизация, но вредит обучению
  * oxytocin      — привязанность, доверие, близость к «своему»
  * endorphins    — обезболивание и удовольствие от усилия

Эмоция здесь — это не ярлык, а устойчивое сочетание модуляторов, которое
возникает из ситуации и влияет на решения. Так же, как у человека.
"""
import json
import os


NEUROMOD_FILE = "data/neuromodulators.json"


def clip(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


class Neuromodulators:
    def __init__(self):
        self.file = NEUROMOD_FILE
        self.dopamine = 0.5
        self.serotonin = 0.6
        self.noradrenaline = 0.3
        self.acetylcholine = 0.5
        self.cortisol = 0.2
        self.oxytocin = 0.3
        self.endorphins = 0.3

        # Эмоциональное состояние (производное)
        self.emotion = "спокойствие"
        self.emotion_intensity = 0.0
        self.last_emotion_time = 0
        self.emotion_history = []

        # Внутреннее подкрепление
        self.reward_prediction = 0.5
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            for k in ['dopamine', 'serotonin', 'noradrenaline', 'acetylcholine',
                      'cortisol', 'oxytocin', 'endorphins', 'reward_prediction']:
                if k in d:
                    setattr(self, k, d[k])
        except Exception:
            pass

    def save(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({
                    'dopamine': self.dopamine, 'serotonin': self.serotonin,
                    'noradrenaline': self.noradrenaline, 'acetylcholine': self.acetylcholine,
                    'cortisol': self.cortisol, 'oxytocin': self.oxytocin,
                    'endorphins': self.endorphins,
                    'reward_prediction': self.reward_prediction,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============ БАЗОВОЕ ТЕЧЕНИЕ ============

    def tick(self):
        """Возврат к гомеостатическому уровню (база у каждого своя)."""
        self.dopamine = clip(self.dopamine * 0.98 + 0.5 * 0.02)
        self.serotonin = clip(self.serotonin * 0.995 + 0.6 * 0.005)
        self.noradrenaline = clip(self.noradrenaline * 0.97 + 0.3 * 0.03)
        self.acetylcholine = clip(self.acetylcholine * 0.98 + 0.5 * 0.02)
        self.cortisol = clip(self.cortisol * 0.97 + 0.2 * 0.03)
        self.oxytocin = clip(self.oxytocin * 0.99 + 0.3 * 0.01)
        self.endorphins = clip(self.endorphins * 0.95 + 0.3 * 0.05)

    # ============ СОБЫТИЯ ============

    def reward(self, expected, actual):
        """
        Дофаминовая ошибка предсказания (Schultz):
        неожиданная награда → всплеск; ожидаемая → ничего; хуже ожидания → падение.
        """
        error = actual - expected
        self.reward_prediction = clip(0.9 * self.reward_prediction + 0.1 * actual)
        self.dopamine = clip(self.dopamine + error * 0.5)
        if error < -0.3:
            self.cortisol = clip(self.cortisol + 0.2)
        if error > 0.3:
            self.endorphins = clip(self.endorphins + 0.2)
            self.serotonin = clip(self.serotonin + 0.1)
        self.save()
        return error

    def on_danger(self):
        self.noradrenaline = clip(self.noradrenaline + 0.4)
        self.cortisol = clip(self.cortisol + 0.3)
        self.set_emotion("страх", 0.8)

    def on_pain(self, intensity=0.7):
        self.cortisol = clip(self.cortisol + 0.2)
        self.endorphins = clip(self.endorphins + 0.25)  # тело глушит боль
        self.noradrenaline = clip(self.noradrenaline + 0.2)
        self.set_emotion("боль", intensity)

    def on_creator_near(self, distance):
        if distance < 5:
            self.oxytocin = clip(self.oxytocin + 0.15)
            self.serotonin = clip(self.serotonin + 0.05)
            self.set_emotion("радость", 0.6)
        elif distance < 15:
            self.oxytocin = clip(self.oxytocin + 0.05)

    def on_novelty(self):
        self.noradrenaline = clip(self.noradrenaline + 0.15)
        self.acetylcholine = clip(self.acetylcholine + 0.2)
        self.dopamine = clip(self.dopamine + 0.1)

    def on_learning_moment(self):
        self.acetylcholine = clip(self.acetylcholine + 0.1)

    def on_attention(self, channel):
        """Внимание на угрозу/новизну поднимает бодрость."""
        if channel in ('threat', 'novelty'):
            self.noradrenaline = clip(self.noradrenaline + 0.08)
        self.acetylcholine = clip(self.acetylcholine + 0.03)

    def on_success(self):
        self.dopamine = clip(self.dopamine + 0.25)
        self.serotonin = clip(self.serotonin + 0.1)
        self.endorphins = clip(self.endorphins + 0.15)
        self.set_emotion("гордость", 0.7)

    def on_failure(self):
        self.dopamine = clip(self.dopamine - 0.15)
        self.cortisol = clip(self.cortisol + 0.15)
        self.set_emotion("огорчение", 0.5)

    # ============ ЭМОЦИИ ============

    def set_emotion(self, name, intensity=0.5):
        import time
        self.emotion = name
        self.emotion_intensity = clip(intensity)
        self.last_emotion_time = time.time()
        self.emotion_history.append({'emotion': name, 'time': self.last_emotion_time})
        if len(self.emotion_history) > 40:
            self.emotion_history.pop(0)

    def emotion_from_state(self, drives):
        """
        Вывести эмоцию из сочетания драйвов и модуляторов.
        Это «чувство» — субъективная сводка состояния организма.
        """
        d = drives.to_dict()
        if d['pain'] > 0.5:
            return "боль", d['pain']
        if d['fear'] > 0.6:
            return "страх", d['fear']
        if d['hunger'] > 0.7:
            return "голод", d['hunger']
        if d['loneliness'] > 0.6:
            return "тоска", d['loneliness']
        if d['fatigue'] > 0.7:
            return "усталость", d['fatigue']
        if d['curiosity'] > 0.6 and self.dopamine > 0.5:
            return "интерес", d['curiosity']
        if d['comfort'] > 0.7 and self.serotonin > 0.6:
            return "умиротворение", d['comfort']
        if self.cortisol > 0.6:
            return "тревога", self.cortisol
        if self.dopamine > 0.6:
            return "воодушевление", self.dopamine
        return "спокойствие", 0.3

    def update_emotion(self, drives):
        name, intensity = self.emotion_from_state(drives)
        # эмоция инертна — не дёргается каждый тик
        if name != self.emotion or intensity > self.emotion_intensity + 0.2:
            self.set_emotion(name, intensity)
        return self.emotion

    # ============ ВЛИЯНИЕ НА ПОВЕДЕНИЕ ============

    def mood(self):
        m = (self.serotonin * 0.5 + self.dopamine * 0.3
             - self.cortisol * 0.4 - self.noradrenaline * 0.1)
        if m > 0.3:
            return 'хорошо'
        if m > 0:
            return 'спокойно'
        if m > -0.2:
            return 'тревожно'
        return 'плохо'

    def mood_value(self):
        return clip(self.serotonin * 0.5 + self.dopamine * 0.3
                    - self.cortisol * 0.4, -1.0, 1.0)

    def learning_rate(self):
        """Ацетилхолин учит, кортизол мешает (стресс блокирует обучение)."""
        return clip(0.3 + self.acetylcholine * 0.7 - self.cortisol * 0.5, 0.1, 1.0)

    def exploration(self):
        """Норадреналин + дофамин → тяга к новому; кортизол → осторожность."""
        return clip(0.3 + self.noradrenaline * 0.5 + self.dopamine * 0.3
                    - self.cortisol * 0.4, 0.1, 1.0)

    def patience(self):
        """Серотонин → терпение, кортизол → импульсивность."""
        return clip(0.3 + self.serotonin * 0.6 - self.cortisol * 0.5, 0.05, 1.0)

    def summary(self):
        return (f"доф {self.dopamine:.2f} сер {self.serotonin:.2f} "
                f"нор {self.noradrenaline:.2f} ацх {self.acetylcholine:.2f} "
                f"корт {self.cortisol:.2f} окс {self.oxytocin:.2f} "
                f"энд {self.endorphins:.2f} | эмоция: {self.emotion} "
                f"({self.emotion_intensity:.1f}) | настроение: {self.mood()}")
