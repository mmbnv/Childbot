"""
SelfModel — «Я» существа.

Самосознание человека состоит из нескольких слоёв:
  * телесная схема — где я, сколько у меня здоровья, что в руках;
  * знание о себе — что я умею, что у меня получается;
  * нарративное «Я» — связная история «кто я и что со мной было»;
  * метакогниция — оценка собственной уверенности и компетентности.

Всё это влияет на поведение: существо избегает того, в чём не уверено,
и тянется к тому, что у него получается.
"""
import json
import os
import time
import requests


class SelfModel:
    def __init__(self, adapter, file="data/self.json"):
        self.adapter = adapter
        self.file = file
        self.last_update = 0
        self.inventory = []
        self.armor = {}
        self.health = 20
        self.food = 20
        self.pos = {'x': 0, 'y': 0, 'z': 0}
        self.knowledge = {}

        # нарративное «Я»
        self.name = "ChildBot"
        self.identity = "ребёнок, который учится жить в этом мире"
        self.creator = None
        self.narrative = []          # ключевые события «обо мне»
        self.self_esteem = 0.5       # уверенность в себе

        # метакогниция: компетентность по действиям
        self.competence = {}         # action -> {'ok', 'fail'}

        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.knowledge = data.get('knowledge', {})
            self.narrative = data.get('narrative', [])[-50:]
            self.self_esteem = data.get('self_esteem', 0.5)
            self.identity = data.get('identity', self.identity)
            self.creator = data.get('creator')
            self.competence = data.get('competence', {})
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({
                    'knowledge': self.knowledge,
                    'narrative': self.narrative[-50:],
                    'self_esteem': self.self_esteem,
                    'identity': self.identity,
                    'creator': self.creator,
                    'competence': self.competence,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def refresh(self, force=False):
        now = time.time()
        if not force and (now - self.last_update) < 10:
            return
        self.last_update = now
        data = None
        getter = getattr(self.adapter, "get_self", None)
        if callable(getter):
            try:
                data = getter()
            except Exception:
                data = None
        if data is None:
            try:
                data = requests.get(f"{self.adapter.url}/self", timeout=3).json()
            except Exception:
                return
        self.inventory = data.get('inventory', [])
        self.armor = data.get('armor', {})
        self.health = data.get('health', 20)
        self.food = data.get('food', 20)
        self.pos = data.get('pos') or self.pos

    # ---------- ЗНАНИЕ О СЕБЕ ----------

    def learn_about_self(self, key, value):
        self.knowledge[key] = value
        self.save()

    def set_creator(self, name):
        if self.creator is None and name:
            self.creator = name
            self.add_narrative(f"у меня появился папа — {name}")

    def add_narrative(self, event):
        self.narrative.append({'event': event, 'time': time.time()})
        if len(self.narrative) > 50:
            self.narrative.pop(0)

    def record_competence(self, action, success):
        """Метакогниция: насколько у меня получается это действие."""
        rec = self.competence.setdefault(action, {'ok': 0, 'fail': 0})
        if success:
            rec['ok'] += 1
            self.self_esteem = min(1.0, self.self_esteem + 0.02)
        else:
            rec['fail'] += 1
            self.self_esteem = max(0.0, self.self_esteem - 0.01)

    def confidence(self, action):
        """Насколько я уверен, что справлюсь с действием (0..1)."""
        rec = self.competence.get(action)
        if not rec or (rec['ok'] + rec['fail']) == 0:
            return 0.5
        return rec['ok'] / (rec['ok'] + rec['fail'])

    # ---------- ИНВЕНТАРЬ ----------

    def has_item(self, name_contains):
        return any(name_contains in i['name'] for i in self.inventory)

    def get_items(self, name_contains):
        return [i for i in self.inventory if name_contains in i['name']]

    # ---------- ОПИСАНИЯ ----------

    def summary(self):
        inv_str = ', '.join([f"{i['name']}×{i['count']}" for i in self.inventory[:8]]) or 'пусто'
        armor_str = ', '.join([f"{k}:{v}" for k, v in self.armor.items() if v]) or 'нет'
        return (f"Я {self.name}: HP {self.health}/20, еда {self.food}/20, "
                f"уверенность в себе {self.self_esteem:.2f}. "
                f"Инвентарь: {inv_str}. Броня: {armor_str}.")

    def narrative_summary(self, n=3):
        if not self.narrative:
            return "моя история только начинается"
        return " → ".join(e['event'] for e in self.narrative[-n:])

    def get_known_facts(self):
        if not self.knowledge:
            return "пока ничего не знаю о себе"
        return "\n".join([f"- {k}: {v}" for k, v in list(self.knowledge.items())[-10:]])

    def metacognition_summary(self):
        """Что я думаю о своих способностях."""
        if not self.competence:
            return "ещё не знаю, что умею"
        lines = []
        for a, r in list(self.competence.items())[-6:]:
            total = r['ok'] + r['fail']
            if total:
                lines.append(f"{a}: {100*r['ok']//total}%")
        return ', '.join(lines) if lines else "ещё не знаю, что умею"
