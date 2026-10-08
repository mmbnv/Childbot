"""
Game2Adapter — совсем другая игра, для того же мозга.

Это не Minecraft. Маленькое «подземелье»: комнаты, дверь, ключ, яма.
Задача — найти ключ, соединить его с замком (combine = химия/соединение),
открыть дверь (use = проход) и дойти до выхода.

Тело отдаёт те же сенсоры, что и Minecraft, и поддерживает те же действия.
Мозг об этом не знает: он видит признаки мира и учит законы. Если понятия
универсальны, существо разберётся и здесь — без единой строчки про эту игру.
"""
import math
import time


class Game2Adapter:
    def __init__(self):
        self.url = "game2://local"
        self.t = 0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.health = 20
        self.food = 20

        self.on_ground = True
        self.support_below = True
        self.blocked = False
        self.near_door = True
        self.door_open = False
        self.has_key = False
        self.key_used = False
        self.rooms_cleared = 0
        self._msgs = []
        self._actions_seen = []
        self.said = []
        self.hostile = None
        self.inventory = {}
        self.tasks = [
            {'id': 'g_key', 'name': 'найти ключ', 'target': 'key', 'count': 1,
             'need': 'осмотреть комнату', 'action': 'gather', 'done': False},
            {'id': 'g_lock', 'name': 'соединить ключ с замком', 'target': 'unlocked',
             'count': 1, 'need': 'соединить', 'action': 'combine', 'done': False},
            {'id': 'g_door', 'name': 'открыть дверь', 'target': 'door_open',
             'count': 1, 'need': 'дверь', 'action': 'use', 'done': False},
            {'id': 'g_exit', 'name': 'дойти до выхода', 'target': 'exit', 'count': 1,
             'need': 'иди вперёд', 'action': 'step_forward', 'done': False},
        ]

    # ---- сенсоры (тот же контракт, что у Minecraft) ----
    def get_state(self):
        self.t += 1
        if self.t % 120 == 0:
            self.health = max(1, self.health - 1)   # ловушка в комнате
        p = {'name': 'Friend', 'x': self.x + 2, 'y': self.y, 'z': self.z,
             'distance': 2.0}
        return {
            'x': self.x, 'y': self.y, 'z': self.z,
            'health': self.health, 'food': self.food,
            'player': p, 'in_pit': False, 'has_sky_above': False,
            'is_night': False, 'time_of_day': 6000,
            'nearest_hostile': self.hostile,
            'recent_damage': False, 'damage_time': 0,
            'on_ground': self.on_ground, 'support_below': self.support_below,
            'blocked': self.blocked, 'near_door': self.near_door,
            'door_open': self.door_open,
        }

    def get_self(self):
        inv = [{'name': n, 'count': c, 'slot': i}
               for i, (n, c) in enumerate(self.inventory.items()) if c > 0]
        return {'inventory': inv, 'armor': {}, 'health': self.health,
                'food': self.food, 'pos': {'x': self.x, 'y': self.y, 'z': self.z}}

    def get_vision(self):
        return {'visible_blocks': [{'name': 'door', 'x': self.x + 2, 'y': 0, 'z': 0}],
                'held_item': None}

    def get_sounds(self):
        return {'sounds': []}

    def get_world(self):
        return {'blocks': [{'name': 'stone'}, {'name': 'door'}],
                'time': 6000, 'isDay': True}

    def get_messages(self):
        return self._msgs

    def get_player_actions(self):
        return []

    def get_actions(self):
        names = [
            ('step_forward', 'шаг вперёд'), ('step_back', 'шаг назад'),
            ('step_left', 'шаг влево'), ('step_right', 'шаг вправо'),
            ('jump_once', 'прыжок'), ('jump_forward', 'прыжок вперёд'),
            ('sprint_short', 'пробежка'), ('sneak', 'присесть'),
            ('go_to_player', 'идти к другу'), ('walk_away_from_player', 'отойти'),
            ('come_close_to_player', 'подойти вплотную'), ('stay_here', 'стоять'),
            ('look_at_player', 'посмотреть на друга'), ('look_around', 'осмотреться'),
            ('gather', 'искать предмет'), ('combine', 'соединить'),
            ('use', 'открыть/использовать'), ('interact', 'взаимодействовать'),
            ('eat_food', 'съесть'), ('wait_1sec', 'ждать'),
            ('go_to_position', 'идти к точке'), ('escape_pit', 'выбраться'),
            ('place_block', 'поставить блок'), ('dig_nearby', 'копать рядом'),
            ('dig_down', 'копать вниз'), ('attack_hostile', 'атаковать'),
            ('flee_from_hostile', 'убежать'), ('look_up', 'вверх'),
            ('look_down', 'вниз'), ('spin_around', 'повернуться'),
        ]
        return [{'name': n, 'desc': d} for n, d in names]

    def get_tasks(self):
        # игра сама отмечает, что уже сделано
        self.tasks[0]['done'] = self.has_key
        self.tasks[1]['done'] = self.key_used
        self.tasks[2]['done'] = self.door_open
        self.tasks[3]['done'] = self.rooms_cleared >= 1
        return self.tasks

    def get_game(self):
        return {'name': 'dungeon', 'actions': [a['name'] for a in self.get_actions()]}

    def clear_messages(self):
        self._msgs = []

    def push_message(self, name, text):
        self._msgs.append({'name': name, 'text': text, 'time': time.time() * 1000})

    # ---- моторика ----
    def action(self, action, params=None):
        self._actions_seen.append(action)
        params = params or {}

        if action in ('jump_once', 'jump_forward'):
            self.y += 1.0
            self.on_ground = False
            self.y -= 1.0
            self.on_ground = True
            return {'ok': True, 'result': {'ok': True}}

        if action in ('dig_down', 'dig_nearby') and not self.support_below:
            self.y -= 1.0
            self.on_ground = False
            return {'ok': True, 'result': {'ok': True, 'fell': True}}

        if action in ('gather', 'look_around'):
            if not self.has_key:
                self.has_key = True
                self.inventory['key'] = 1
                return {'ok': True, 'result': {'ok': True, 'gathered': 'key'}}
            return {'ok': False, 'result': {'ok': False, 'reason': 'nothing_new'}}

        if action == 'combine':
            if self.has_key and not self.key_used:
                self.key_used = True
                self.inventory.pop('key', None)
                self.inventory['unlocked'] = 1
                return {'ok': True, 'result': {'ok': True, 'combined': 'unlocked'}}
            return {'ok': False, 'result': {'ok': False, 'reason': 'no_materials'}}

        if action in ('use', 'interact') and self.near_door:
            if self.key_used and not self.door_open:
                self.door_open = True
                self.x += 1.0
                return {'ok': True, 'result': {'ok': True, 'opened': 'door'}}
            return {'ok': False, 'result': {'ok': False, 'reason': 'locked'}}

        if action in ('step_forward', 'go_to_player', 'come_close_to_player',
                      'step_back', 'walk_away_from_player', 'step_left',
                      'step_right', 'go_to_position'):
            if self.blocked:
                return {'ok': True, 'result': {'ok': True, 'blocked': True}}
            if action in ('step_forward', 'go_to_player', 'come_close_to_player'):
                self.x += 0.8
            elif action in ('step_back', 'walk_away_from_player'):
                self.x -= 0.8
            elif action == 'step_left':
                self.z += 0.8
            elif action == 'step_right':
                self.z -= 0.8
            elif action == 'go_to_position':
                self.x += 0.8
            if self.door_open:
                self.rooms_cleared = 1
            return {'ok': True, 'result': {'ok': True}}

        if action == 'eat_food':
            self.food = min(20, self.food + 5)
        return {'ok': True, 'result': {'ok': True}}

    def say(self, text):
        self.said.append(text)
        return True
