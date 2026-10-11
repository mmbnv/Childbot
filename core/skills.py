"""
SkillsLibrary — библиотека навыков (заученные последовательности действий).
"""
import json
import os


class Skill:
    def __init__(self, name, steps, description="", preconditions=None):
        self.name = name
        self.steps = steps
        self.description = description
        self.preconditions = preconditions or []
        self.success_count = 0
        self.failure_count = 0

    def to_dict(self):
        return {
            'name': self.name, 'steps': self.steps,
            'description': self.description, 'preconditions': self.preconditions,
            'success_count': self.success_count, 'failure_count': self.failure_count,
        }

    @classmethod
    def from_dict(cls, d):
        s = cls(d['name'], d['steps'], d.get('description', ''), d.get('preconditions', []))
        s.success_count = d.get('success_count', 0)
        s.failure_count = d.get('failure_count', 0)
        return s


class SkillsLibrary:
    def __init__(self, file="data/skills.json"):
        self.file = file
        self.skills = {}
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for d in data:
                s = Skill.from_dict(d)
                self.skills[s.name] = s
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump([s.to_dict() for s in self.skills.values()], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, name):
        return self.skills.get(name)

    def learn(self, name, steps, description=""):
        if name not in self.skills:
            self.skills[name] = Skill(name, steps, description)
            self.save()

    def record_result(self, name, success):
        s = self.skills.get(name)
        if not s:
            return
        if success:
            s.success_count += 1
        else:
            s.failure_count += 1
        self.save()
