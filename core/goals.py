"""
GoalManager — удержание цели, поставленной извне (папой).
"""
import time


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

    def set_goal(self, description, action, params=None, max_attempts=5):
        if self.current:
            self.history.append(self.current.to_dict())
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
        self.history.append(self.current.to_dict())
        print(f"   {'✅' if success else '❌'} Цель {'выполнена' if success else 'провалена'}")
        self.current = None

    def give_up(self):
        if not self.current:
            return
        self.current.last_result = {'reason': 'gave_up'}
        self.history.append(self.current.to_dict())
        print(f"   ❌ Сдаюсь (попыток: {self.current.attempts})")
        self.current = None
