"""
Knowledge — знание «что работает» (условные связи цель→действие).
"""
import json
import os


KNOWLEDGE_FILE = "data/knowledge.json"


class Knowledge:
    def __init__(self):
        self.file = KNOWLEDGE_FILE
        self.patterns = {}
        self.total_learned = 0
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.patterns = data.get('patterns', {})
            self.total_learned = data.get('total_learned', 0)
        except Exception:
            pass

    def save(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'patterns': self.patterns, 'total_learned': self.total_learned},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _hash_goal(self, goal_text):
        words = goal_text.lower().split()
        important = [w for w in words if len(w) > 3][:3]
        return '|'.join(sorted(important))

    def record(self, goal_text, action, success, reason=""):
        if not success and ('is not a function' in reason or 'not a function' in reason or
                            'undefined' in reason or 'TypeError' in reason or 'bug' in reason):
            return

        h = self._hash_goal(goal_text)
        if h not in self.patterns:
            self.patterns[h] = {}
        if action not in self.patterns[h]:
            self.patterns[h][action] = {'success': 0, 'fail': 0, 'last_reason': ''}
            self.total_learned += 1

        rec = self.patterns[h][action]
        if success:
            rec['success'] += 1
            print(f"📚 Запомнил: для '{goal_text[:30]}' '{action}' РАБОТАЕТ")
        else:
            rec['fail'] += 1
            rec['last_reason'] = reason
            print(f"📚 Запомнил: для '{goal_text[:30]}' '{action}' НЕ работает")
        self.save()

    def suggest_actions(self, goal_text, exclude=None):
        h = self._hash_goal(goal_text)
        exclude = set(exclude or [])
        if h in self.patterns:
            candidates = []
            for action, rec in self.patterns[h].items():
                if action in exclude:
                    continue
                total = rec['success'] + rec['fail']
                if total == 0:
                    continue
                if rec['success'] == 0 and rec['fail'] >= 1:
                    continue
                candidates.append((action, rec['success'] / total))
            candidates.sort(key=lambda x: -x[1])
            return [a for a, r in candidates]
        return []

    def get_known_failures(self, goal_text):
        h = self._hash_goal(goal_text)
        if h not in self.patterns:
            return []
        return [a for a, rec in self.patterns[h].items()
                if rec['fail'] > 0 and rec['success'] == 0]

    def summary(self):
        if not self.patterns:
            return "пока не знаю что работает"
        return f"знаю {self.total_learned} связей"
