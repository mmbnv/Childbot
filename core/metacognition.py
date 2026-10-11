"""
Metacognition — думать о своём думании.

Человек не только думает, но и знает, что он думает: замечает, что чего-то
не понимает, что устал думать, что в чём-то уверен, а в чём-то нет. Это
метапознание — «мышление о мышлении».

Здесь:
  * САМОНАБЛЮДЕНИЕ. Существо следит за своей работой: как давно думает,
    насколько часто ошибается, повторяется ли, залипает ли.
  * ЧУВСТВО ЗНАНИЯ (feeling of knowing). «Я знаю это» / «я не понимаю» —
    без этого существо не может попросить помощи или объяснения.
  * ПЕРЕКЛЮЧЕНИЕ СТРАТЕГИИ. Заметив залипание, оно не упорствует, а меняет
    способ: переосмыслить, отвлечься, попросить папу, отдохнуть.
  * ВОПРОСЫ. Непонимание рождает вопрос — это и есть «спросить у папы».
"""
import json
import os
import time


METACOG_FILE = "data/metacognition.json"


class Metacognition:
    def __init__(self, file=METACOG_FILE):
        self.file = file
        self.confusion = 0.0        # насколько я сейчас не понимаю
        self.confidence = 0.5       # насколько я уверен в своих действиях
        self.loop_score = 0.0       # насколько я зациклился
        self._recent = []           # (action, ok) для наблюдения
        self._last_actions = []
        self.last_question = 0.0
        self.questions_asked = 0
        self.strategy_switches = 0
        self.insights = []          # «я понял, что...»
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.questions_asked = d.get('questions_asked', 0)
            self.strategy_switches = d.get('strategy_switches', 0)
            self.insights = d.get('insights', [])[-20:]
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'questions_asked': self.questions_asked,
                           'strategy_switches': self.strategy_switches,
                           'insights': self.insights[-20:]},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============ САМОНАБЛЮДЕНИЕ ============

    def observe(self, action, ok):
        """Наблюдать за своим действием и его исходом."""
        if not action:
            return
        self._recent.append({'action': action, 'ok': bool(ok), 'time': time.time()})
        if len(self._recent) > 40:
            self._recent.pop(0)

        # Залипание: одно и то же действие повторяется много раз подряд.
        self._last_actions.append(action)
        if len(self._last_actions) > 10:
            self._last_actions.pop(0)
        if len(self._last_actions) >= 5:
            last5 = self._last_actions[-5:]
            repeats = max(last5.count(a) for a in set(last5))
            self.loop_score = max(0.0, (repeats - 2) / 3.0)

        # Уверенность: доля успехов в последних действиях.
        recent = self._recent[-12:]
        if recent:
            self.confidence = sum(1 for r in recent if r['ok']) / len(recent)

        # Непонимание: частые неудачи + залипание + нет понимания причины.
        fails = [r for r in recent if not r['ok']]
        self.confusion = min(1.0, len(fails) / max(4, len(recent)) * 1.2
                             + self.loop_score * 0.4)

    def stuck(self):
        """Я зациклился и/или сильно не понимаю — пора менять подход."""
        return self.loop_score > 0.5 or self.confusion > 0.7

    # ============ ЧУВСТВО ЗНАНИЯ ============

    def feels_confident(self, threshold=0.55):
        return self.confidence >= threshold

    def feeling_of_knowing(self, topic_known):
        """«Я знаю это» или «я не понимаю»."""
        if topic_known and self.confidence > 0.4:
            return 'знаю'
        if self.confusion > 0.6:
            return 'не понимаю'
        return 'догадываюсь'

    # ============ ПЕРЕКЛЮЧЕНИЕ СТРАТЕГИИ ============

    def pick_strategy(self):
        """Заметив трудность, выбрать способ справиться (а не упорствовать)."""
        if not self.stuck():
            return None
        self.strategy_switches += 1
        self.save()
        if self.confusion > 0.8:
            return 'ask_papa'         # совсем не понимаю — спросить
        if self.loop_score > 0.6:
            return 'switch_task'      # залип — переключиться
        return 'reappraise'           # переосмыслить

    # ============ ВОПРОСЫ И ОЗАРЕНИЯ ============

    def ask(self, question):
        self.last_question = time.time()
        self.questions_asked += 1
        self.save()
        return question

    def insight(self, text):
        """Озарение: «я понял, что...». Запоминаем, чтобы поделиться с папой."""
        self.insights.append({'text': text, 'time': time.time()})
        if len(self.insights) > 20:
            self.insights.pop(0)
        self.save()
        return text

    def last_insight(self):
        return self.insights[-1]['text'] if self.insights else None

    def summary(self):
        return (f"мета: уверен {self.confidence:.2f}, не понимаю {self.confusion:.2f}, "
                f"залип {self.loop_score:.2f}, вопросов {self.questions_asked}")
