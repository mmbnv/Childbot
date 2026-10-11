"""
Emotions — чувства: не реакции, а оценки того, что для меня значит событие.

Человеческая эмоция рождается не из «стимул → ответ», а из ОЦЕНКИ (appraisal):
«что это значит для моих нужд? хорошо или плохо? кто виноват — я, папа или
случай? справлюсь ли я? правильно ли я поступил?». Из этой оценки возникают
разные чувства:

  * радость   — случилось то, чего хотел;
  * печаль    — потерял важное, ничего не поделать;
  * страх     — угроза, и я не уверен, что справлюсь;
  * злость    — мне мешают, и я мог бы воспротивиться;
  * удивление — случилось неожиданное;
  * отвращение— что-то вредное, от него хочется прочь;
  * интерес   — новое и понятное настолько, чтобы тянуло узнать;
  * спокойствие — всё в порядке, я в безопасности;
  * любовь    — привязанность к папе, тепло и желание быть рядом;
  * гордость  — я сам сделал то, чем доволен;
  * стыд/вина — я поступил против того, что считаю правильным;
  * обида     — папа (свой) не откликнулся, стало больно.

Кроме отдельных чувств есть НАСТРОЕНИЕ — медленный фон (хорошо/плохо,
спокойно/возбуждённо, владею ли я собой). Настроение красит всё: то же
событие в дурном настроении ранит сильнее.

И есть РЕГУЛЯЦИЯ — человек не просто чувствует, он управляет чувством:
переосмысливает, отвлекается, ищет утешения у близкого, избегает.
Это то, что отличает зрелое существо от автомата страстей.
"""
import json
import os
import time

from core.temperament import clip


EMOTIONS_FILE = "data/emotions.json"

# Каждое чувство: как оно красит восприятие и что тянет делать.
#   valence — приятно/неприятно (-1..1)
#   arousal — возбуждение (0..1)
#   action  — к чему толкает (approach/avoid/attend/freeze/seektouch)
EMOTION_PROFILE = {
    'радость':     (+0.9, 0.6, 'approach'),
    'интерес':     (+0.6, 0.5, 'attend'),
    'спокойствие': (+0.5, 0.15, 'rest'),
    'любовь':      (+0.9, 0.4, 'seektouch'),
    'гордость':    (+0.7, 0.5, 'approach'),
    'удивление':   (+0.1, 0.8, 'attend'),
    'печаль':      (-0.6, 0.2, 'avoid'),
    'страх':       (-0.8, 0.9, 'avoid'),
    'злость':      (-0.5, 0.85, 'approach'),
    'отвращение':  (-0.7, 0.5, 'avoid'),
    'обида':       (-0.6, 0.5, 'avoid'),
    'стыд':        (-0.7, 0.5, 'freeze'),
    'вина':        (-0.6, 0.4, 'approach'),   # хочется загладить
    'одиночество': (-0.5, 0.3, 'seektouch'),
}

# Какие чувства гасят друг друга (регуляция через противоположное).
OPPOSITES = {
    'страх': 'спокойствие', 'печаль': 'радость', 'злость': 'спокойствие',
    'обида': 'любовь', 'стыд': 'гордость', 'отвращение': 'спокойствие',
    'одиночество': 'любовь',
}


class Emotion:
    __slots__ = ('name', 'intensity', 'cause', 'time', 'appraisal')

    def __init__(self, name, intensity, cause='', appraisal=None):
        self.name = name
        self.intensity = clip(intensity)
        self.cause = cause
        self.time = time.time()
        self.appraisal = appraisal or {}

    def to_dict(self):
        return {'name': self.name, 'intensity': round(self.intensity, 2),
                'cause': self.cause, 'time': self.time}

    def text(self):
        return f"{self.name} ({self.intensity:.1f})" + (f" — {self.cause}" if self.cause else "")


class Emotions:
    def __init__(self, temperament, file=EMOTIONS_FILE):
        self.temperament = temperament
        self.file = file

        self.current = Emotion('спокойствие', 0.3)
        self.recent = []                 # недавние чувства (для смешанности)
        self.memory = []                 # эмоциональная память (яркие события)
        self.MAX_MEMORY = 120

        # Настроение — медленный фон: удовольствие, возбуждение, владение собой.
        self.pleasure = 0.1
        self.arousal = 0.3
        self.dominance = 0.5
        self.mood_word = 'спокойно'
        self.last_regulation = 0.0
        self.load()

    # ============ СОХРАНЕНИЕ ============

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.pleasure = d.get('pleasure', 0.1)
            self.arousal = d.get('arousal', 0.3)
            self.dominance = d.get('dominance', 0.5)
            self.memory = d.get('memory', [])[-self.MAX_MEMORY:]
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'pleasure': self.pleasure, 'arousal': self.arousal,
                           'dominance': self.dominance,
                           'memory': self.memory[-self.MAX_MEMORY:]},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============ ОЦЕНКА (APPRAISAL) ============

    def appraise(self, event):
        """
        Оценить событие и вернуть чувство. Это сердце «человечности»:
        одна и та же ситуация рождает разное чувство в зависимости от смысла.

        event — словарь:
          goal_ok    — помогло ли моим нуждам (+1 да, -1 нет, 0 никак)
          novelty    — 0..1, насколько неожиданно
          control    — 0..1, могу ли я на это повлиять
          self_agency— сделал ли это Я
          other      — кто это сделал ('папа', имя, None=случай)
          harm       — насколько это мне вредит (0..1)
          benefit    — насколько помогает (0..1)
          norm       — 0..1, поступил ли я против своих правил
          attachment — связано ли со «своим» (папой)
          loss       — потерял ли важное
          blocked    — помешали ли мне
        """
        e = event or {}
        goal_ok = e.get('goal_ok', 0)
        novelty = e.get('novelty', 0.0)
        control = e.get('control', 0.5)
        self_agency = bool(e.get('self_agency'))
        other = e.get('other')
        harm = e.get('harm', 0.0)
        benefit = e.get('benefit', 0.0)
        norm = e.get('norm', 0.0)
        attachment = bool(e.get('attachment'))
        loss = e.get('loss', 0.0)
        blocked = bool(e.get('blocked'))

        # Гордость/вина/стыд — оценка себя относительно своих правил.
        if norm > 0.4 and self_agency:
            return self._make('стыд' if other is None else 'вина', norm * 1.2,
                              'поступил не так, как считаю правильным', e)

        # Обида: свой (папа) не откликнулся, когда я тянулся.
        if attachment and other and goal_ok < 0 and e.get('unanswered'):
            return self._make('обида', 0.5 + harm * 0.5, 'папа не откликнулся', e)

        # Угроза/вред — сильнейшее чувство, оно перекрывает радость и любовь.
        if harm > 0.4:
            return self._make('страх', 0.4 + harm * 0.6, 'мне угрожают', e)

        # Потеря важного, ничего не поделать → печаль.
        if loss > 0.4 and control < 0.4:
            return self._make('печаль', 0.4 + loss * 0.6, 'потерял важное', e)

        # Мне мешают, и я мог бы воспротивиться → злость.
        if blocked and control > 0.4:
            return self._make('злость', 0.4 + harm * 0.5, 'мне мешают', e)

        # Вредное, от чего хочется прочь → отвращение.
        if e.get('disgust'):
            return self._make('отвращение', 0.6, 'это противное', e)

        # В безопасности, рядом свой человек → любовь и тепло.
        if attachment and benefit > 0 and harm < 0.2:
            return self._make('любовь', 0.5 + benefit * 0.5, 'папа рядом', e)

        # Неожиданное → удивление (короткое), потом интерес.
        if novelty > 0.6:
            return self._make('удивление', 0.5 + novelty * 0.4, 'неожиданно', e)

        # Помогло → радость; новое и понятное → интерес.
        if benefit > 0.3 or goal_ok > 0:
            name = 'радость' if benefit > 0.4 else 'интерес'
            return self._make(name, 0.4 + max(benefit, goal_ok * 0.6), 'получилось', e)

        if novelty > 0.3:
            return self._make('интерес', 0.4 + novelty * 0.4, 'что-то новое', e)

        return None

    def _make(self, name, intensity, cause, appraisal):
        # Впечатлительность усиливает, настроение красит (mood-congruence):
        # то же событие в дурном настроении ранит сильнее, а в хорошем —
        # неприятное чувство глушится. Это человеческая черта, не «шкала».
        intense = intensity * self.temperament.reactivity()
        bad = name in ('страх', 'печаль', 'злость', 'обида', 'стыд', 'вина', 'отвращение')
        if bad:
            intense *= (1.0 + max(0.0, -self.pleasure) * 0.5)
            intense *= (1.0 - max(0.0, self.pleasure) * 0.35)
        else:
            intense *= (1.0 + max(0.0, self.pleasure) * 0.3)
        return Emotion(name, clip(intense), cause, appraisal)

    # ============ ПЕРЕЖИВАНИЕ ============

    def feel(self, name, intensity=0.6, cause=''):
        """Возникло чувство. Записываем его и запоминаем яркое."""
        if name not in EMOTION_PROFILE:
            return self.current
        self.current = Emotion(name, intensity, cause)
        self.recent.append(self.current)
        if len(self.recent) > 30:
            self.recent.pop(0)

        # Эмоциональная память: яркое помнится долго (как вспышки памяти).
        if intensity > 0.6:
            self.memory.append({'name': name, 'intensity': round(intensity, 2),
                                'cause': cause, 'time': time.time()})
            if len(self.memory) > self.MAX_MEMORY:
                self.memory.pop(0)
        self.mood_word = self._mood_name()
        self.save()
        return self.current

    def contagion(self, other_emotion, intensity):
        """Эмоциональное заражение: чувства близкого передаются (эмпатия)."""
        if other_emotion not in EMOTION_PROFILE:
            return
        # Эмпатия сильнее у доброжелательных (низкий порог заражения).
        strength = 0.25 + self.temperament.t('agreeableness') * 0.5
        self.feel(other_emotion, clip(intensity * strength), 'от папы')

    def mixed(self):
        """Смешанные чувства: последние сильные эмоции вместе (как бывает у людей)."""
        strong = [e for e in self.recent[-5:] if e.intensity > 0.45]
        if len(strong) < 2:
            return None
        names = []
        for e in strong:
            if e.name not in names:
                names.append(e.name)
        if len(names) < 2:
            return None
        return ' и '.join(names[:2])

    # ============ ТЕЧЕНИЕ И РЕГУЛЯЦИЯ ============

    def tick(self, drives, intero, neuromod, dt=1.0):
        """Чувство живёт во времени: настроение дрейфует, эмоция утихает."""
        d = drives.to_dict()

        # Настроение тянется к тому, что подсказывают драйвы и тело.
        target_pleasure = clip(0.7 * d['comfort'] + 0.5 * intero.tone
                               - 0.4 * d['pain'] - 0.3 * d['fear'] - 0.2 * d['hunger'])
        target_arousal = clip(intero.arousal)
        target_dominance = clip(0.6 - d['fear'] * 0.4 - d['pain'] * 0.3
                                + self.temperament.t('extraversion') * 0.2)
        # Инерция настроения: оно меняется медленно (это фон, а не вспышка).
        self.pleasure += (target_pleasure - self.pleasure) * 0.05 * dt
        self.arousal += (target_arousal - self.arousal) * 0.08 * dt
        self.dominance += (target_dominance - self.dominance) * 0.05 * dt

        # Эмоция утихает со временем (скорость — от характера).
        self.current.intensity *= (1.0 - 0.06 * self.temperament.recovery() * dt)
        if self.current.intensity < 0.12:
            self.current = Emotion(self._mood_name(), 0.3)

        self.mood_word = self._mood_name()
        return self.current

    def _mood_name(self):
        # Сильное чувство прямо сейчас окрашивает настроение, даже если фон
        # ещё не успел сдвинуться (эмоция вспыхивает раньше настроения).
        if self.current.intensity > 0.55:
            return {
                'радость': 'радостно', 'любовь': 'тепло на душе',
                'интерес': 'любопытно', 'гордость': 'гордо',
                'страх': 'тревожно', 'боль': 'плохо',
                'печаль': 'грустно', 'одиночество': 'одиноко',
                'злость': 'сердито', 'обида': 'обидно', 'стыд': 'стыдно',
            }.get(self.current.name, 'взволнованно')
        p, a, dom = self.pleasure, self.arousal, self.dominance
        if p > 0.35 and a < 0.5:
            return 'хорошо и спокойно'
        if p > 0.3 and a >= 0.5:
            return 'радостно и бодро'
        if p < -0.35 and a >= 0.5:
            return 'тревожно и плохо'
        if p < -0.25:
            return 'грустно'
        if dom < 0.35:
            return 'неуверенно'
        return 'ровно'

    def regulate(self, strategy, drives, neuromod, attachment_near=False):
        """
        Регуляция чувства — то, что делает существо человеком, а не автоматом.
        Возвращает True, если стратегия применилась.

        стратегии:
          * reappraisal — переосмыслить: «это не так страшно, я справлюсь»;
          * distraction — отвлечься на другое дело;
          * comfort     — поиск утешения у близкого (самая человеческая);
          * avoidance   — уйти от источника;
          * suppression — подавить (дорого: поднимает кортизол).
        """
        neg = self.current.name in ('страх', 'печаль', 'злость', 'обида', 'стыд', 'одиночество')
        if not neg or self.current.intensity < 0.4:
            return False
        self.last_regulation = time.time()
        before = self.current.intensity

        if strategy == 'reappraisal':
            # Переосмысление снижает возбуждение и чуть поднимает владение собой.
            self.current.intensity *= 0.6
            self.dominance = clip(self.dominance + 0.15)
            self.pleasure = clip(self.pleasure + 0.08)
        elif strategy == 'distraction':
            self.current.intensity *= 0.75
            self.arousal = clip(self.arousal - 0.15)
        elif strategy == 'comfort':
            if not attachment_near:
                return False
            opposite = OPPOSITES.get(self.current.name, 'спокойствие')
            self.current.intensity *= 0.35
            self.feel(opposite, 0.5, 'папа утешил')
            self.pleasure = clip(self.pleasure + 0.2)
        elif strategy == 'avoidance':
            self.current.intensity *= 0.7
        elif strategy == 'suppression':
            self.current.intensity *= 0.8
            neuromod.cortisol = clip(neuromod.cortisol + 0.12)  # подавление стоит дорого
        else:
            return False
        return self.current.intensity < before

    # ============ ВЛИЯНИЕ НА ПОВЕДЕНИЕ ============

    def action_bias(self):
        """К чему толкает текущее чувство: approach / avoid / attend / freeze / seektouch."""
        return EMOTION_PROFILE.get(self.current.name, (0, 0, 'attend'))[2]

    def bias_score(self, action):
        """Оценка действия сквозь призму чувства (для выбора поведения)."""
        bias = self.action_bias()
        want = {
            'approach': {'step_forward', 'sprint_short', 'jump_forward', 'dig_tree',
                         'find_and_attack', 'go_to_position', 'attack_hostile'},
            'avoid': {'step_back', 'flee_from_hostile', 'walk_away_from_player',
                      'escape_pit', 'force_break_out'},
            'attend': {'look_around', 'look_at_player', 'look_up', 'look_down',
                       'go_to_player', 'come_close_to_player'},
            'seektouch': {'go_to_player', 'come_close_to_player', 'look_at_player'},
            'rest': {'wait_1sec', 'look_around'},
            'freeze': {'stay_here', 'wait_1sec'},
        }
        score = 0.0
        if action in want.get(bias, set()):
            score += 0.25 * self.current.intensity
        # В страхе и печали осторожность важнее риска.
        if self.current.name in ('страх', 'печаль') and action in want['avoid']:
            score += 0.2
        return score

    def text(self):
        mixed = self.mixed()
        base = f"{self.current.name} ({self.current.intensity:.1f})"
        if mixed:
            return f"{base}, смешанно: {mixed}"
        return base

    def summary(self):
        return (f"чувство: {self.text()} | настроение: {self.mood_word} "
                f"(удов {self.pleasure:+.2f}, возб {self.arousal:.2f}, "
                f"владею {self.dominance:.2f}) | ярких воспоминаний {len(self.memory)}")
