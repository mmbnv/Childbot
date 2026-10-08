"""
Cognition — мышление, внутренняя речь и память о мире.

Три части:
  * SymbolicMemory — семантическая память о мире: где что лежит, что с чем
    связано (это «знание», а не «события»).
  * InternalVoice — внутренний монолог. Не команда, не ответ, а мысль.
  * Cognition — связывает мир, внимание, рабочую память и планировщик.

Внутренняя речь питается тем, на что направлено ВНИМАНИЕ (глобальное рабочее
пространство), и тем, что удерживает рабочая память — как у человека.
"""
import json
import os
import re
import time
import requests

from core.planner import Planner


COGNITION_FILE = "data/cognition.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"

CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]')


def has_cjk(t):
    return bool(CJK_PATTERN.search(t))


class SymbolicMemory:
    def __init__(self):
        self.file = COGNITION_FILE
        self.objects = {}
        self.effects = {}
        self.places = {}
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.objects = data.get('objects', {})
            self.effects = data.get('effects', {})
            self.places = data.get('places', {})
            total = sum(len(v) for v in self.objects.values())
            if total:
                print(f"🌍 Мир: знаю {len(self.objects)} типов объектов, {total} мест")
        except Exception:
            pass

    def save(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'objects': self.objects, 'effects': self.effects,
                           'places': self.places}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def note_object(self, name, x, y, z):
        if name not in self.objects:
            self.objects[name] = []
        for o in self.objects[name]:
            if abs(o['x'] - x) < 2 and abs(o['z'] - z) < 2 and time.time() - o['seen'] < 30:
                o['seen'] = time.time()
                return
        self.objects[name].append({'x': x, 'y': y, 'z': z, 'seen': time.time()})
        if len(self.objects[name]) > 20:
            self.objects[name].sort(key=lambda o: -o['seen'])
            self.objects[name] = self.objects[name][:20]

    def note_effect(self, action, target, result):
        self.effects[f"{action}+{target}"] = {'result': result, 'time': time.time()}

    def where_is(self, name):
        if name not in self.objects:
            return None
        recent = [o for o in self.objects[name] if time.time() - o['seen'] < 600]
        if not recent:
            return None
        recent.sort(key=lambda o: -o['seen'])
        return recent[0]

    def summary_for_prompt(self, limit=8):
        lines = []
        for name, points in list(self.objects.items())[:limit]:
            if not points:
                continue
            recent = max(points, key=lambda o: o['seen'])
            age = time.time() - recent['seen']
            lines.append(f"{name} был в ({recent['x']:.0f}, {recent['z']:.0f}), {age:.0f} сек назад")
        return '\n'.join(lines) if lines else "мир пуст, я ещё ничего не знаю"


class InternalVoice:
    def __init__(self, interval_sec=30, enabled=True):
        self.interval = interval_sec
        self.last_thought_time = 0
        self.thoughts = []
        self.MAX_THOUGHTS = 20
        self.enabled = enabled
        self._llm_down = False

    def should_think(self):
        if not self.enabled:
            return False
        return (time.time() - self.last_thought_time) > self.interval

    def _offline_thought(self, drives_summary, emotion, attention):
        """Мысль без LLM — из внутреннего состояния (работает всегда)."""
        import random
        templates = [
            f"мне {emotion}... надо что-то делать",
            f"я замечаю: {attention}",
            f"чувствую себя так: {drives_summary}",
            "что это там такое?",
            "папа, ты где?",
            "я хочу узнать, что дальше",
        ]
        return random.choice(templates)

    def _clean(self, text):
        text = text.strip().strip('"\'').strip().split('\n')[0].strip()
        text = re.sub(r'<[^>]*>', '', text).strip()
        if not text or len(text) > 200 or has_cjk(text):
            return None
        return text

    def think(self, drives_summary, symbolic_summary, recent_events, mood,
              current_action, attention="", working_memory="", emotion="", self_narrative=""):
        prompt = f"""Ты — цифровой ребёнок 3-5 лет в Minecraft. Ты ДУМАЕШЬ про себя.
Это внутренний монолог. Не обращайся к папе. Просто размышляй вслух.

Я чувствую: {drives_summary}
Моя эмоция сейчас: {emotion}
Настроение: {mood}
Сейчас я осознаю (внимание): {attention}
Держу в уме: {working_memory}
Что знаю о мире: {symbolic_summary}
Что со мной было: {self_narrative}
Последние события: {recent_events}
Чем занят: {current_action}

Подумай вслух. Одно-два коротких предложения. Максимум 15 слов.
Только мысль. Без кавычек и без угловых скобок."""

        if self._llm_down:
            text = self._offline_thought(drives_summary, emotion, attention)
            self._record(text)
            return text

        try:
            r = requests.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.9, "num_predict": 40, "top_p": 0.9}
            }, timeout=60)
            if r.status_code != 200:
                return None
            text = self._clean(r.json().get('response', ''))
            if not text:
                return None
            self._record(text)
            return text
        except Exception as e:
            if not self._llm_down:
                print(f"⚠️  LLM недоступна, думаю сама: {e}")
                self._llm_down = True
            text = self._offline_thought(drives_summary, emotion, attention)
            self._record(text)
            return text

    def _record(self, text):
        self.last_thought_time = time.time()
        self.thoughts.append({'text': text, 'time': time.time()})
        if len(self.thoughts) > self.MAX_THOUGHTS:
            self.thoughts.pop(0)

    def last(self):
        return self.thoughts[-1]['text'] if self.thoughts else ''


class Cognition:
    def __init__(self, knowledge=None):
        self.symbolic = SymbolicMemory()
        self.voice = InternalVoice(interval_sec=30)
        self.planner = Planner(self.symbolic, knowledge)
        self.last_plan = None

    def observe_world(self, vision_data, sounds_data):
        SKIP = {'dirt', 'grass_block', 'stone', 'bedrock', 'cobblestone',
                'sand', 'gravel', 'andesite', 'diorite', 'granite'}
        INTERESTING = ['bed', 'door', 'chest', 'crafting', 'furnace',
                       'log', 'wood', 'water', 'lava',
                       'cow', 'pig', 'sheep', 'chicken',
                       'zombie', 'skeleton', 'creeper', 'spider',
                       'torch', 'glass', 'plank', 'wool',
                       'leaves', 'flower', 'sapling']

        if vision_data:
            for b in vision_data.get('visible_blocks', []):
                name = b['name']
                if name in SKIP:
                    continue
                if any(k in name for k in INTERESTING):
                    self.symbolic.note_object(name, b['x'], b['y'], b['z'])

        if sounds_data:
            for s in sounds_data.get('sounds', []):
                if 'door' in s.get('sound', ''):
                    self.symbolic.note_object('door_sound', s['x'], s['y'], s['z'])

    def think_if_time(self, drives, recent_events, mood, current_action,
                      attention="", working_memory="", emotion="", self_narrative=""):
        if not self.voice.should_think():
            return None
        drives_str = ", ".join([f"{k}: {v:.1f}" for k, v in drives.items()
                                if v > 0.2 and k != 'comfort']) or "всё спокойно"
        world_str = self.symbolic.summary_for_prompt()
        return self.voice.think(drives_str, world_str, recent_events or "ничего особенного",
                                mood, current_action or "просто существую",
                                attention=attention, working_memory=working_memory,
                                emotion=emotion, self_narrative=self_narrative)

    def plan_if_needed(self, drives, state, predictor=None):
        if not self.planner.should_plan():
            return None
        plan = self.planner.make_plan(drives, state, predictor)
        if plan:
            self.last_plan = [dict(s) for s in plan.steps]
            return self.last_plan
        return None

    def record_effect(self, action, target, result):
        self.symbolic.note_effect(action, target, result)
        self.symbolic.save()

    def save(self):
        self.symbolic.save()

    def summary(self):
        obj_count = sum(len(v) for v in self.symbolic.objects.values())
        lines = [f"🌍 Мир: {obj_count} объектов в памяти"]
        last_thought = self.voice.last()
        if last_thought:
            lines.append(f"💭 Мысль: {last_thought}")
        return '\n'.join(lines)
