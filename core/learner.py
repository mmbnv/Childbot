"""
Learner — обучение на ошибках (причина сбоя → правило подготовки).
"""
import json
import os
import time


LEARNED_RULES_FILE = "data/learned_rules.json"


class Learner:
    def __init__(self, self_model, world_model, adapter):
        self.self_model = self_model
        self.world_model = world_model
        self.adapter = adapter
        self.rules = {}
        self.failures = []
        self.load()

    def load(self):
        if not os.path.exists(LEARNED_RULES_FILE):
            return
        try:
            with open(LEARNED_RULES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.rules = data.get('rules', {})
            self.failures = data.get('failures', [])[-50:]
        except Exception:
            pass

    def save(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(LEARNED_RULES_FILE, 'w', encoding='utf-8') as f:
                json.dump({'rules': self.rules, 'failures': self.failures[-50:]},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def observe_result(self, action, result):
        if not result:
            return
        ok = result.get('ok')
        reason = result.get('reason', '')

        if not ok and reason:
            self.failures.append({'action': action, 'reason': reason, 'time': time.time()})
            rule = self._reason_to_rule(action, reason)
            if rule and action not in self.rules:
                self.rules[action] = rule
                print(f"📚 Правило: для '{action}' нужно: {rule['needs']}")
                self.save()

    def _reason_to_rule(self, action, reason):
        mapping = {
            'no_block_in_hand': {'needs': 'блок в руке', 'steps': ['hold_item']},
            'held_item_not_block': {'needs': 'блок в руке', 'steps': ['hold_item']},
            'no_block_in_inventory': {'needs': 'блок в инвентаре', 'steps': ['dig_nearby']},
            'item_not_found': {'needs': 'нужный предмет', 'steps': ['dig_nearby']},
            'no_food': {'needs': 'еда в инвентаре', 'steps': []},
            'no_food_to_sprint': {'needs': 'есть больше 6', 'steps': ['eat_food']},
            'nothing_to_dig': {'needs': 'блок перед ботом', 'steps': ['step_forward']},
            'no_surface_to_place_on': {'needs': 'опора', 'steps': ['dig_nearby']},
            'no_target': {'needs': 'моб рядом', 'steps': ['step_forward']},
            'no_player': {'needs': 'игрок в зоне', 'steps': ['spin_around']},
        }
        return mapping.get(reason)

    def suggest_fix(self, action):
        rule = self.rules.get(action)
        if rule and rule.get('steps'):
            return rule['steps']
        return None

    def summary(self):
        if not self.rules:
            return "пока ничего не знаю из опыта"
        lines = [f"- для '{a}': {r.get('needs', '?')}" for a, r in list(self.rules.items())[-10:]]
        return "\n".join(lines)
