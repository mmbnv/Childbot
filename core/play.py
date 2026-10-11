"""
Play — игра и воображение.

Игра — не «безделье» и не «случайные действия». Для ребёнка это главный способ
учиться и главный источник радости. Здесь живёт игровое начало:

  * ВООБРАЖЕНИЕ. Воображаемая игра: палка — это меч, блок — это пирог.
    Внутри себя существо придумывает игру и играет в неё (make-believe).
  * ИГРА-ИССЛЕДОВАНИЕ. Ребёнок пробует действия «просто так», чтобы узнать,
    что будет, — но в отличие от экспериментатора это не про закон, а про
    удовольствие от процесса.
  * ПРОБУЖДЕНИЕ ФАНТАЗИИ. Из воображения рождаются собственные затеи:
    «построю башню», «спрячусь и найдусь», «устрою папе сюрприз».

Игра питается настроением: играют, когда сыт, в безопасности и в хорошем
настроении. Игра повышает дофамин и снимает напряжение — как у детей.
"""
import json
import os
import random
import time

from core.temperament import clip


PLAY_FILE = "data/play.json"


# Воображаемые игры: чем заняться «понарошку». В каждой — цепочка действий.
MAKE_BELIEVE = [
    ('строю башню до неба', ['place_block', 'place_block', 'jump_forward']),
    ('копаю пещеру-секрет', ['dig_nearby', 'dig_forward', 'look_around']),
    ('играю в прятки', ['step_back', 'look_around', 'spin_around']),
    ('скачу как зайчик', ['jump_once', 'jump_forward', 'jump_once']),
    ('плыву как рыбка', ['step_forward', 'look_around', 'spin_around']),
    ('лечу как птица', ['jump_forward', 'look_up', 'jump_forward']),
    ('делаю папе сюрприз', ['step_forward', 'place_block', 'look_at_player']),
    ('охраняю сокровище', ['look_around', 'step_forward', 'look_around']),
    ('разговариваю с облаками', ['look_up', 'wait_1sec', 'look_up']),
    ('меряюсь силой с деревом', ['dig_tree', 'dig_tree', 'spin_around']),
]

# «Игрушки» — предметы, которые воображение превращает в другое.
TOY_TRANSFORM = {
    'stick': 'меч', 'log': 'дубина', 'stone': 'мяч', 'white_wool': 'облако',
    'feather': 'крыло', 'coal': 'чёрный камень', 'oak_planks': 'доска-щит',
}


class Play:
    def __init__(self, temperament, file=PLAY_FILE):
        self.temperament = temperament
        self.file = file
        self.imagination = clip(0.4 + temperament.t('openness') * 0.6)
        self.current_game = None       # (название, [действия], шаг)
        self.games_played = 0
        self.favorite = None
        self.toy = None                # во что превратил предмет
        self.last_play = 0.0
        self.cooldown = 20.0
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.games_played = d.get('games_played', 0)
            self.favorite = d.get('favorite')
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'games_played': self.games_played,
                           'favorite': self.favorite}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============ МОЖНО ЛИ ИГРАТЬ ============

    def can_play(self, drives, emotions, in_danger):
        """Играют, когда сыт, в безопасности и в хорошем настроении."""
        d = drives.to_dict()
        return (not in_danger and d['hunger'] < 0.5 and d['pain'] < 0.4
                and d['fear'] < 0.5 and emotions.pleasure > -0.1
                and (time.time() - self.last_play) > self.cooldown)

    # ============ ВООБРАЖЕНИЕ ============

    def imagine(self, inventory=None):
        """Придумать игру «понарошку» — из воображения, не из нужды."""
        # Иногда превратить предмет в «игрушку».
        self.toy = None
        if inventory:
            names = [i.get('name', '') for i in inventory]
            for key, role in TOY_TRANSFORM.items():
                if any(key in n for n in names):
                    if random.random() < 0.4 * self.imagination:
                        self.toy = (key, role)
                    break

        game = random.choice(MAKE_BELIEVE)
        name, steps = game
        if self.toy:
            name = f"{name} (а {self.toy[0]} у меня {self.toy[1]})"
        self.current_game = {'name': name, 'steps': list(steps), 'i': 0}
        return name

    def next_step(self):
        """Следующее действие воображаемой игры."""
        if not self.current_game:
            return None
        steps = self.current_game['steps']
        i = self.current_game['i']
        if i >= len(steps):
            self.finish()
            return None
        self.current_game['i'] += 1
        return steps[i]

    def finish(self):
        """Игра закончилась — радость и «это моя любимая игра»."""
        if not self.current_game:
            return None
        name = self.current_game['name']
        self.games_played += 1
        if random.random() < 0.3:
            self.favorite = name
        self.current_game = None
        self.last_play = time.time()
        self.save()
        return name

    def playing(self):
        return self.current_game is not None

    def summary(self):
        if self.current_game:
            return f"играю: {self.current_game['name']} (шаг {self.current_game['i']})"
        fav = f", любимая: {self.favorite}" if self.favorite else ""
        return f"игр сыграно: {self.games_played}{fav}, воображение {self.imagination:.2f}"
