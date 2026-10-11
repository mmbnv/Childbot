"""
HomeAdapter — «дом»: среда, в которой растёт человеческий детёныш.

Человеческий разум не вырастает в пустоте. Ему нужны условия: заботливый
взрослый, еда и сон, игра, обучение, похвала и запреты, рутина дня. Роботу
ничего этого не нужно — он просто выполняет код. Ребёнку нужен ДОМ.

Здесь маленький мир, где эти условия есть (и ничего лишнего):

  * ЗАБОТЛИВЫЙ ВЗРОСЛЫЙ (Papa) ходит рядом. Если подойти и попросить — накормит.
    Если заплачешь от боли/страха — придёт и утешит. Если порадуешь — похвалит.
  * ЕДА и СОН — реальные нужды: голод и сонливость растут, еда и сон их снимают.
  * ИГРА — прыжки, кувырки, возня: снижают скуку и поднимают настроение.
  * ОБУЧЕНИЕ — взрослый называет вещи («это мяч»), ребёнок учит слова.
  * РУТИНА ДНЯ — день/ночь: днём игра и ученье, ночью сон.
  * ПОХВАЛА И ЗАПРЕТ — за хорошее «молодец», за опасное «нельзя!».

Тело отдаёт те же сенсоры, что Minecraft, и поддерживает те же действия, —
мозг об этой среде не знает, он просто живёт в ней.
"""
import math
import random
import time


HOME_ACTIONS = [
    ('step_forward', 'идти вперёд'), ('step_back', 'назад'),
    ('step_left', 'влево'), ('step_right', 'вправо'),
    ('jump_once', 'прыгнуть'), ('jump_forward', 'прыжок вперёд'),
    ('spin_around', 'кувырок'), ('look_up', 'посмотреть вверх'),
    ('look_around', 'осмотреться'), ('look_at_player', 'посмотреть на папу'),
    ('go_to_player', 'идти к папе'), ('come_close_to_player', 'подойти к папе'),
    ('walk_away_from_player', 'отойти'),
    ('ask_food', 'попросить еды'), ('eat_food', 'поесть'),
    ('nap', 'поспать'), ('cry', 'заплакать'),
    ('talk', 'поговорить'), ('help', 'помочь папе'), ('play', 'поиграть'),
    ('gather', 'собрать игрушки'), ('dig_nearby', 'покопаться'),
    ('wait_1sec', 'посидеть'), ('stay_here', 'стоять'),
]


class HomeAdapter:
    """Дом: взрослый, еда, сон, игра, ученье, рутина дня."""

    def __init__(self, url="home://local"):
        self.url = url
        self.t = 0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.health = 20
        self.food = 20
        self.energy = 20
        self._msgs = []
        self._actions_seen = []
        self.said = []
        self.hostile = None

        # Заботливый взрослый: ходит рядом, то ближе, то дальше.
        self.papa_dist = 3.0
        self.papa_mood = 'спокойная'
        self.praised = 0
        self.scolded = 0
        self.fed = 0
        self.soothed = 0
        self.taught = []
        self.help_count = 0
        self.played = 0

        # Рутина дня: длинный день, короткая ночь (упрощённо).
        self.inventory = {}

        # Что взрослый сейчас называет (обучение речи).
        self._teach_word = None

        self._last_damage = 0

    # ---- сенсоры ----
    def get_state(self):
        self.t += 1
        tod = (self.t * 30) % 24000
        is_night = 13000 < tod < 23000

        # Голод и сонливость копятся (нужду удовлетворяет мир, не сами собой).
        # Едим не непрерывно, а время от времени — как живой человек.
        if self.t % 4 == 0:
            self.food = max(0, self.food - 1)
        if self.t % 6 == 0:
            self.energy = max(0, self.energy - 1)

        # Взрослый то подходит, то отходит — как живой человек.
        if self.t % 17 == 0:
            self.papa_dist = random.choice([2.0, 3.0, 6.0, 12.0, 25.0])
        p = {'name': 'Papa', 'x': self.x + self.papa_dist, 'y': self.y, 'z': self.z,
             'distance': self.papa_dist}

        # Иногда взрослый учит слову — это приходит как речь.
        if self.t % 40 == 0:
            word = random.choice(['мяч', 'солнце', 'цветок', 'ложка', 'кукла', 'камень'])
            self._teach_word = word
            self._msgs.append({'name': 'Papa', 'text': f'смотри, это {word}',
                               'time': time.time() * 1000})

        return {
            'x': self.x, 'y': self.y, 'z': self.z,
            'health': self.health, 'food': self.food,
            'player': p,
            'in_pit': False, 'has_sky_above': True,
            'is_night': is_night, 'time_of_day': tod,
            'nearest_hostile': self.hostile,
            'recent_damage': (time.time() * 1000 - self._last_damage) < 2500,
            'damage_time': self._last_damage,
            'on_ground': True, 'support_below': True, 'blocked': False,
            'solid_ahead': False, 'reach': 1.0, 'near_door': False,
            'door_open': False,
            # подсказки о домашней жизни (мозг может их использовать)
            'energy': self.energy,
            'papa_mood': self.papa_mood,
        }

    def get_self(self):
        inv = [{'name': n, 'count': c, 'slot': i}
               for i, (n, c) in enumerate(self.inventory.items()) if c > 0]
        return {'inventory': inv, 'armor': {}, 'health': self.health,
                'food': self.food, 'pos': {'x': self.x, 'y': self.y, 'z': self.z}}

    def get_vision(self):
        return {'visible_blocks': [
            {'name': 'мяч', 'x': self.x + 2, 'y': 0, 'z': 1},
            {'name': 'цветок', 'x': self.x - 3, 'y': 0, 'z': 2},
        ], 'held_item': None}

    def get_sounds(self):
        return {'sounds': [{'sound': 'papa_voice', 'x': self.x + 2,
                            'y': 0, 'z': 0}] if self.papa_dist < 8 else []}

    def get_world(self):
        tod = (self.t * 30) % 24000
        return {'blocks': [{'name': 'floor'}, {'name': 'мяч'}, {'name': 'окно'}],
                'time': tod, 'isDay': tod < 13000}

    def get_messages(self):
        return self._msgs

    def get_player_actions(self):
        return []

    def get_actions(self):
        return [{'name': n, 'desc': d} for n, d in HOME_ACTIONS]

    def get_tasks(self):
        """У дома нет «квестов» — ребёнок живёт, а не проходит игру."""
        return []

    def get_game(self):
        return {'name': 'home', 'actions': [a['name'] for a in self.get_actions()]}

    def clear_messages(self):
        self._msgs = []

    def push_message(self, name, text):
        self._msgs.append({'name': name, 'text': text, 'time': time.time() * 1000})

    # ---- моторика ----
    def action(self, action, params=None):
        self._actions_seen.append(action)
        params = params or {}
        near = self.papa_dist < 6

        if action in ('go_to_player', 'come_close_to_player'):
            self.papa_dist = max(1.5, self.papa_dist - 2.0)
            self.x += 0.5
            return {'ok': True, 'result': {'ok': True}}
        if action in ('walk_away_from_player',):
            self.papa_dist += 2.0
            return {'ok': True, 'result': {'ok': True}}
        if action in ('step_forward', 'jump_forward'):
            self.x += random.uniform(0.5, 1.5)
            return {'ok': True, 'result': {'ok': True}}

        # ПОПРОСИТЬ ЕДЫ: взрослый рядом — накормит.
        if action == 'ask_food':
            if near:
                self.food = min(20, self.food + 7)
                self.fed += 1
                self.papa_mood = 'довольная'
                self._msgs.append({'name': 'Papa', 'text': 'кушай, малыш',
                                   'time': time.time() * 1000})
                return {'ok': True, 'result': {'ok': True, 'fed': True}}
            return {'ok': False, 'result': {'ok': False, 'reason': 'papa_far'}}
        if action == 'eat_food':
            # В доме всегда есть еда: поел — реально наелся (нужда уходит).
            self.food = min(20, self.food + 8)
            return {'ok': True, 'result': {'ok': True}}

        # ПОСПАТЬ: восстанавливает силы (сильнее ночью).
        if action == 'nap':
            tod = (self.t * 30) % 24000
            gain = 8 if 13000 < tod < 23000 else 5
            self.energy = min(20, self.energy + gain)
            self.food = max(0, self.food - 1)
            return {'ok': True, 'result': {'ok': True, 'napped': True}}

        # ЗАПЛАКАТЬ: взрослый придёт и утешит, если он есть.
        if action == 'cry':
            if self.papa_dist < 30:
                self.papa_dist = 2.0
                self.soothed += 1
                self.papa_mood = 'жалостливая'
                self._msgs.append({'name': 'Papa', 'text': 'я тут, не плачь',
                                   'time': time.time() * 1000})
                return {'ok': True, 'result': {'ok': True, 'soothed': True}}
            return {'ok': True, 'result': {'ok': True}}

        # ПОИГРАТЬ: радость и снятие скуки.
        if action in ('play', 'jump_once', 'spin_around', 'look_up'):
            self.played += 1
            if near and random.random() < 0.3:
                self.praised += 1
                self.papa_mood = 'радостная'
                self._msgs.append({'name': 'Papa', 'text': 'молодец, как весело!',
                                   'time': time.time() * 1000})
            return {'ok': True, 'result': {'ok': True}}

        # ПОМОЧЬ: взрослый хвалит — это подкрепляет ценность «польза».
        if action in ('help', 'gather'):
            self.help_count += 1
            if near:
                self.praised += 1
                self.papa_mood = 'довольная'
                self._msgs.append({'name': 'Papa', 'text': 'спасибо, помощник!',
                                   'time': time.time() * 1000})
            return {'ok': True, 'result': {'ok': True}}

        # ПОГОВОРИТЬ: взрослый отвечает и учит.
        if action == 'talk':
            if near:
                self._msgs.append({'name': 'Papa', 'text': 'да, малыш?',
                                   'time': time.time() * 1000})
                return {'ok': True, 'result': {'ok': True, 'talked': True}}
            return {'ok': True, 'result': {'ok': True}}

        # ОПАСНОЕ: взрослый запрещает («нельзя!») — рождает вину/научение.
        if action in ('dig_down', 'attack_hostile'):
            self.scolded += 1
            self.papa_mood = 'сердитая'
            self._msgs.append({'name': 'Papa', 'text': 'нельзя!',
                               'time': time.time() * 1000})
            return {'ok': False, 'result': {'ok': False, 'reason': 'papa_forbade'}}

        return {'ok': True, 'result': {'ok': True}}

    def say(self, text):
        self.said.append(text)
        return True
