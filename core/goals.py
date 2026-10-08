"""
GoalManager — удержание цели, поставленной извне (папой).
"""
import json
import os
import time

MAX_HISTORY = 100


class Goal:
    def __init__(self, description, action, params=None, max_attempts=5):
        self.description = description
        self.action = action
        self.params = params or {}
        self.created_at = time.time()
        self.attempts = 0
        self.max_attempts = max_attempts
        self.completed = False
        self.last_result = None

    def is_expired(self, max_age_sec=90):
        return (time.time() - self.created_at) > max_age_sec

    def to_dict(self):
        return {
            'description': self.description, 'action': self.action,
            'params': self.params, 'created_at': self.created_at,
            'attempts': self.attempts, 'max_attempts': self.max_attempts,
            'completed': self.completed, 'last_result': self.last_result,
        }


class GoalManager:
    def __init__(self, file="data/goals.json"):
        self.file = file
        self.current = None
        self.history = []
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                self.history = json.load(f).get('history', [])[-MAX_HISTORY:]
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'history': self.history[-MAX_HISTORY:]},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _remember(self, goal_dict):
        self.history.append(goal_dict)
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        self.save()

    def set_goal(self, description, action, params=None, max_attempts=5):
        if self.current:
            self._remember(self.current.to_dict())
        self.current = Goal(description, action, params, max_attempts)
        print(f"🎯 Цель: {description[:50]} → {action}")

    def progress(self):
        if not self.current:
            return None
        self.current.attempts += 1
        return self.current

    def complete(self, success, result=None):
        if not self.current:
            return
        self.current.completed = success
        self.current.last_result = result
        self._remember(self.current.to_dict())
        print(f"   {'✅' if success else '❌'} Цель {'выполнена' if success else 'провалена'}")
        self.current = None

    def give_up(self):
        if not self.current:
            return
        self.current.last_result = {'reason': 'gave_up'}
        self._remember(self.current.to_dict())
        print(f"   ❌ Сдаюсь (попыток: {self.current.attempts})")
        self.current = None
