"""
Interoception — «чувство тела»: как организм ощущает сам себя изнутри.

У человека есть интероцепция: мы чувствуем сердцебиение, дыхание, тяжесть,
тепло, тошноту. Это не «датчик здоровья», а субъективное ощущение — основа
эмоций (теория Джеймса-Ланге: эмоция = телесное возбуждение + его осмысление).

Здесь тело даёт сырые сигналы (голод, боль, тепло, усталость), а мозг
превращает их в ФЕНОМЕНАЛЬНОЕ чувство — «мне тяжело», «внутри тревожно»,
«легко и тепло». Это то, что делает состояние переживанием, а не числом.
"""
import time


def clip(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


# Сырой сигнал тела -> как он ощущается.
SENSATION_WORDS = {
    'hunger':    ('пусто в животе', 'урчит в животе'),
    'pain':      ('острая боль', 'ноет и болит'),
    'fear':      ('сердце колотится', 'сжимается внутри'),
    'fatigue':   ('тяжело в теле', 'слипаются глаза'),
    'loneliness': ('щемит в груди', 'пусто без папы'),
    'cold':      ('зябко', 'холодно'),
    'heat':      ('жарко', 'душно'),
    'effort':    ('напрягаюсь', 'устали мышцы'),
    'calm':      ('дышу ровно', 'легко и спокойно'),
    'warmth':    ('тепло на душе', 'хорошо внутри'),
}


class Interoception:
    """Телесное чувство себя. Собирает сырьё тела в цельный «тон» организма."""

    def __init__(self):
        self.tone = 0.0            # -1 (тяжело) .. +1 (легко)
        self.arousal = 0.0         # 0 (спокойно) .. 1 (возбуждён)
        self.feeling = "спокойно"  # словесное ощущение
        self.signals = {}          # что именно сейчас ощущается
        self.last_update = 0.0
        self.history = []

    def sense(self, state, drives, body=None):
        """Считать ощущения из тела и драйвов. Возвращает словесное чувство."""
        d = drives.to_dict()
        body = body or {}
        state = state or {}

        # Возбуждение: угроза и боль «заводят» организм, усталость гасит.
        self.arousal = clip(0.2 + d['fear'] * 0.7 + d['pain'] * 0.5
                            + d['hunger'] * 0.2 - d['fatigue'] * 0.3)

        # Тон (валентность): насколько внутри хорошо или плохо.
        good = d['comfort'] * 0.6 + (1.0 - d['fatigue']) * 0.2
        bad = (d['pain'] * 0.9 + d['fear'] * 0.7 + d['hunger'] * 0.6
               + d['loneliness'] * 0.5 + d['fatigue'] * 0.3)
        self.tone = clip(good - bad, -1.0, 1.0)

        # Какие именно ощущения сейчас есть — от сильных к слабым.
        self.signals = {}
        for key, val in (('pain', d['pain']), ('fear', d['fear']),
                         ('hunger', d['hunger']), ('fatigue', d['fatigue']),
                         ('loneliness', d['loneliness'])):
            if val > 0.35:
                self.signals[key] = val
        # Внешняя среда: холод/жара/высота.
        if state.get('y', 64) > 120:
            self.signals['cold'] = 0.5
        if body.get('in_water'):
            self.signals['cold'] = max(self.signals.get('cold', 0), 0.6)
        if body.get('in_lava') or body.get('on_fire'):
            self.signals['heat'] = 0.9

        self.feeling = self._word()

        now = time.time()
        self.last_update = now
        self.history.append({'tone': round(self.tone, 2),
                             'arousal': round(self.arousal, 2),
                             'feeling': self.feeling, 'time': now})
        if len(self.history) > 60:
            self.history.pop(0)
        return self.feeling

    def _word(self):
        """Слово для цельного телесного чувства (как человек говорит «мне плохо»)."""
        if self.signals.get('pain', 0) > 0.5:
            return 'мне больно'
        if self.signals.get('heat', 0) > 0.5:
            return 'мне горячо, страшно'
        if self.signals.get('fear', 0) > 0.6:
            return 'страшно, сердце колотится'
        if self.signals.get('hunger', 0) > 0.6:
            return 'голодно, пусто в животе'
        if self.signals.get('cold', 0) > 0.4:
            return 'зябко и неуютно'
        if self.signals.get('fatigue', 0) > 0.6:
            return 'тяжело, хочу спать'
        if self.signals.get('loneliness', 0) > 0.55:
            return 'одиноко, щемит в груди'
        if self.tone > 0.45:
            return 'легко и тепло'
        if self.tone > 0.15:
            return 'спокойно и хорошо'
        if self.tone > -0.15:
            return 'спокойно'
        return 'неуютно'

    def describe(self):
        """Человеческое описание телесного состояния — для мысли и речи."""
        if not self.signals:
            return self.feeling
        parts = []
        for key, val in sorted(self.signals.items(), key=lambda kv: -kv[1]):
            words = SENSATION_WORDS.get(key)
            if not words:
                continue
            parts.append(words[0] if val > 0.6 else words[1])
        if not parts:
            return self.feeling
        return self.feeling + ': ' + ', '.join(parts[:3])

    def summary(self):
        return (f"тело: {self.feeling} "
                f"(тон {self.tone:+.2f}, возбуждение {self.arousal:.2f})")
