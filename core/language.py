"""
Language — язык: как ребёнок учится говорить и понимать слова.

Речь не выдаётся готовой. Ребёнок проходит путь: лепет → одно слово → «телеграф»
(«папа, смотри!») → фразы → вопросы. Он не просто повторяет — он ОСМЫСЛЯЕТ:
связывает слово с предметом, спрашивает «что это?», придумывает свои названия.

Здесь:
  * ЛЕКСИКОН. Слова, которым существо научилось: «что значит слово» и «как
    называется вещь». Растёт из общения с папой и из наблюдения мира.
  * ВОПРОСЫ. Непонимание рождает вопрос: «папа, что такое ...?». Это главный
    двигатель развития речи — ребёнок спрашивает без конца.
  * ГРАММАТИКА. Сначала телеграфный стиль, потом связные фразы — по мере
    развития (см. development.py). Одна мысль — одна фраза.
  * НАЗЫВАНИЕ. Существо само даёт имена новым вещам (номинация) — это
    творчество языка, а не копирование.
"""
import json
import os
import random
import time

from core.temperament import clip


LANGUAGE_FILE = "data/language.json"

# Вопросы, которые задаёт маленький ребёнок, чтобы понять мир.
CURIOSITY_QUESTIONS = [
    'папа, а что это?',
    'папа, а почему так?',
    'папа, а зачем это?',
    'папа, а можно?',
    'папа, а как это называется?',
    'папа, а ты видел?',
]


class Language:
    def __init__(self, temperament, file=LANGUAGE_FILE):
        self.temperament = temperament
        self.file = file
        self.lexicon = {}          # слово -> {'meaning', 'time', 'source'}
        self.named = {}            # предмет -> имя, которое дал я
        self.questions_asked = 0
        self.last_question_time = 0.0
        self.last_word = None
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.lexicon = d.get('lexicon', {})
            self.named = d.get('named', {})
            self.questions_asked = d.get('questions_asked', 0)
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'lexicon': self.lexicon, 'named': self.named,
                           'questions_asked': self.questions_asked},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============ ЛЕКСИКОН ============

    def learn_word(self, word, meaning='', source='папа'):
        """Узнать слово и его смысл. Повторение укрепляет."""
        if not word:
            return
        word = word.strip().lower()
        rec = self.lexicon.get(word)
        if rec:
            rec['seen'] = rec.get('seen', 1) + 1
            if meaning:
                rec['meaning'] = meaning
        else:
            self.lexicon[word] = {'meaning': meaning, 'source': source,
                                  'seen': 1, 'time': time.time()}
            print(f"🗣️  Новое слово: «{word}»" + (f" — {meaning}" if meaning else ""))
        self.save()

    def know(self, word):
        return (word or '').strip().lower() in self.lexicon

    def means(self, word):
        return self.lexicon.get((word or '').strip().lower(), {}).get('meaning', '')

    def vocabulary_size(self):
        return len(self.lexicon)

    # ============ ВОПРОСЫ ============

    def should_ask(self, curiosity, confusion=0.0):
        """Задать вопрос: от любопытства и непонимания, не слишком часто."""
        if (time.time() - self.last_question_time) < 45:
            return False
        urge = 0.3 * curiosity + 0.5 * confusion
        return random.random() < urge

    def ask(self, about=None, confused=False):
        """Задать вопрос вслух. О незнакомом слове — «что это?»."""
        self.last_question_time = time.time()
        self.questions_asked += 1
        if confused:
            q = f"папа, я не понимаю. Что такое {about}?" if about else 'папа, я не понимаю, помоги'
        elif about:
            q = random.choice([f'папа, а что такое {about}?',
                               f'папа, а {about} — это что?'])
        else:
            q = random.choice(CURIOSITY_QUESTIONS)
        self.save()
        return q

    # ============ НАЗЫВАНИЕ (творчество) ============

    def name_thing(self, thing):
        """Дать своё имя новой вещи (как ребёнок придумывает названия)."""
        if thing in self.named:
            return self.named[thing]
        roots = ['штучка', 'штуковина', 'непонятка', 'зверушка', 'блестяшка',
                 'палка-махалка', 'камушек', 'облачко']
        name = f"{random.choice(roots)}-{thing[:6]}"
        self.named[thing] = name
        self.save()
        return name

    # ============ ПОСТРОЕНИЕ ФРАЗЫ ============

    def phrase(self, stage, content, name='папа'):
        """
        Собрать фразу по уровню развития речи:
          0 — лепет/одно слово; 1 — телеграф (2 слова); 2 — простая фраза;
          3 — связная фраза с «потому что».
        content — короткая суть (что сказать).
        """
        c = (content or '').strip().rstrip('.').rstrip('!')
        if stage <= 0:
            return c.split()[0] if c.split() else 'а-а'
        if stage == 1:
            words = c.split()
            return ' '.join(words[:2]) if words else c
        if stage == 2:
            return f"{name}, {c}" if name and name not in c else c
        # stage 3 — с объяснением
        if 'потому' in c.lower():
            return c
        return f"{c} — потому что мне так чувствуется"

    def summary(self):
        return (f"слов знаю {self.vocabulary_size()}, вопросов задал {self.questions_asked}, "
                f"сам назвал {len(self.named)} вещей")
