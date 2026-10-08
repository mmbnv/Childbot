"""
MockAdapter — искусственное «тело» для проверки мозга без Minecraft.

Повторяет интерфейс MinecraftAdapter, но живёт в памяти: еда убывает,
наступает ночь, иногда появляется зомби, действия двигают бота и меняют мир.
Нужен, чтобы убедиться, что весь цикл мозга работает end-to-end.
"""
import math
import random
import time


class MockAdapter:
    def __init__(self, url="mock://local"):
        self.url = url
        self.t = 0
        self.x = 0.0
        self.y = 64.0
        self.z = 0.0
        self.health = 20
        self.food = 20
        self._last_damage = 0
        self._msgs = []
        self._actions_seen = []
        self._player_actions = []
        self.said = []
        self.hostile = None
        self.hostile_timer = 0

    # ---- сенсоры ----
    def get_state(self):
        self.t += 1
        # еда убывает, ночью быстрее
        tod = (self.t * 40) % 24000
        is_night = 13000 < tod < 23000
        if self.t % 5 == 0:
            self.food = max(0, self.food - 1)
        if self.t % 97 == 0:
            self.health = max(1, self.health - 2)
            self._last_damage = int(time.time() * 1000)

        # случайный зомби
        self.hostile_timer -= 1
        if self.hostile is None and random.random() < 0.05:
            self.hostile = {'name': 'zombie', 'distance': random.uniform(3, 14)}
            self.hostile_timer = 10
        elif self.hostile is not None:
            if self.hostile_timer <= 0:
                self.hostile = None
            else:
                self.hostile['distance'] = max(1.0, self.hostile['distance'] - 0.5)

        p = {'name': 'Papa', 'x': self.x + 3, 'y': self.y, 'z': self.z + 2,
             'distance': math.hypot(3, 2)}
        return {
            'x': self.x, 'y': self.y, 'z': self.z,
            'health': self.health, 'food': self.food,
            'player': p,
            'in_pit': False,
            'has_sky_above': True,
            'is_night': is_night,
            'time_of_day': tod,
            'nearest_hostile': self.hostile,
            'recent_damage': (time.time() * 1000 - self._last_damage) < 2500,
            'damage_time': self._last_damage,
        }

    def get_self(self):
        return {
            'inventory': [{'name': 'dirt', 'count': 5, 'slot': 0},
                          {'name': 'bread', 'count': 2, 'slot': 1}],
            'armor': {'head': None, 'torso': None, 'legs': None, 'feet': None},
            'health': self.health, 'food': self.food,
            'pos': {'x': self.x, 'y': self.y, 'z': self.z},
        }

    def get_vision(self):
        return {'visible_blocks': [
            {'name': 'oak_log', 'x': self.x + 4, 'y': self.y, 'z': self.z + 1},
            {'name': 'water', 'x': self.x - 6, 'y': self.y - 1, 'z': self.z + 3},
            {'name': 'grass_block', 'x': self.x + 1, 'y': self.y - 1, 'z': self.z},
            {'name': 'cow', 'x': self.x + 8, 'y': self.y, 'z': self.z - 4},
        ], 'held_item': 'dirt'}

    def get_sounds(self):
        return {'sounds': []}

    def get_world(self):
        tod = (self.t * 40) % 24000
        return {'blocks': [{'name': 'grass_block'}, {'name': 'oak_log'}, {'name': 'water'}],
                'time': tod, 'isDay': tod < 13000}

    def get_messages(self):
        return self._msgs

    def get_player_actions(self):
        return self._player_actions

    def get_actions(self):
        names = [
            ('step_forward', 'шаг вперёд'), ('step_back', 'шаг назад'),
            ('step_left', 'шаг влево'), ('step_right', 'шаг вправо'),
            ('jump_once', 'прыжок'), ('jump_forward', 'прыжок вперёд'),
            ('sprint_short', 'пробежка'), ('sneak', 'присесть'),
            ('go_to_player', 'идти к папе'), ('walk_away_from_player', 'отойти'),
            ('come_close_to_player', 'подойти вплотную'), ('stay_here', 'стоять'),
            ('look_at_player', 'посмотреть на папу'), ('look_around', 'осмотреться'),
            ('dig_forward', 'копать впереди'), ('dig_down', 'копать вниз'),
            ('dig_up', 'копать вверх'), ('dig_nearby', 'копать рядом'),
            ('dig_tree', 'срубить дерево'), ('escape_pit', 'выбраться из ямы'),
            ('place_block', 'поставить блок'), ('build_shelter', 'построить укрытие'),
            ('drop_item', 'выбросить'), ('eat_food', 'съесть'),
            ('equip_best_armor', 'надеть броню'), ('hold_item', 'взять в руку'),
            ('attack_nearest', 'атаковать ближайшего'), ('find_and_attack', 'найти и атаковать'),
            ('flee_from_hostile', 'убежать'), ('attack_hostile', 'атаковать врага'),
            ('look_up', 'посмотреть вверх'), ('look_down', 'посмотреть вниз'),
            ('spin_around', 'повернуться'), ('stop', 'остановиться'),
            ('interact', 'взаимодействовать'), ('wait_1sec', 'ждать'),
            ('mimic_last', 'повторить за папой'), ('look_at_position', 'посмотреть в точку'),
            ('go_to_position', 'идти к точке'),
        ]
        return [{'name': n, 'desc': d} for n, d in names]

    def clear_messages(self):
        self._msgs = []

    def push_message(self, name, text):
        self._msgs.append({'name': name, 'text': text, 'time': time.time() * 1000})

    # ---- моторика ----
    def action(self, action, params=None):
        self._actions_seen.append(action)
        params = params or {}
        # движение
        if action in ('step_forward', 'go_to_player', 'come_close_to_player'):
            self.x += random.uniform(0.5, 1.5)
            self.z += random.uniform(-0.5, 0.5)
        elif action in ('step_back', 'walk_away_from_player'):
            self.x -= random.uniform(0.5, 1.5)
        elif action == 'step_left':
            self.z += 1.0
        elif action == 'step_right':
            self.z -= 1.0
        elif action == 'go_to_position':
            self.x += random.uniform(-1, 1)
            self.z += random.uniform(-1, 1)

        # еда восстанавливает
        if action == 'eat_food':
            self.food = min(20, self.food + 6)
        if action in ('flee_from_hostile', 'attack_hostile', 'attack_nearest', 'find_and_attack'):
            if self.hostile:
                self.hostile = None

        return {'ok': True, 'result': {'ok': True}}

    def say(self, text):
        self.said.append(text)
        return True
