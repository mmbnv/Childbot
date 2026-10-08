"""
Curriculum — «учебная программа» существа: путь от палки до железа.

Человек-ребёнок развивается ступенями: сначала просто хватает предмет,
потом собирает, потом делает инструмент, потом инструмент получше. Здесь то
же самое — упорядоченный список целей-умений. Каждая следующая ступень
опирается на предыдущую.

Существо идёт по программе само, когда сыто и в безопасности. Прогресс
переживает перезапуск, поэтому оно «умнеет» не за один день, а бесконечно:
список можно продолжать, и по нему видно, чему оно уже научилось.
"""
import json
import os
import time


CURRICULUM_FILE = "data/curriculum.json"


# Ступени: (id, предмет-цель, человеческое название, что нужно уметь)
STEPS = [
    ('wood',     'oak_log',        'добыть дерево',            'рубить дерево'),
    ('planks',   'oak_planks',     'сделать доски',            'крафт без верстака'),
    ('sticks',   'stick',          'сделать палки',            'крафт без верстака'),
    ('table',    'crafting_table', 'сделать верстак',          'крафт без верстака'),
    ('wpick',    'wooden_pickaxe', 'сделать деревянную кирку', 'верстак'),
    ('cobble',   'cobblestone',    'добыть камень',            'деревянная кирка'),
    ('spick',    'stone_pickaxe',  'сделать каменную кирку',   'верстак + камень'),
    ('ssword',   'stone_sword',    'сделать каменный меч',     'верстак + камень'),
    ('saxe',     'stone_axe',      'сделать каменный топор',   'верстак + камень'),
    ('furnace',  'furnace',        'сделать печь',             'верстак + камень'),
    ('coal',     'coal',           'добыть уголь',             'кирка'),
    ('torch',    'torch',          'сделать факелы',           'уголь + палки'),
    ('iron',     'raw_iron',       'добыть железо',            'каменная кирка'),
    ('ingot',    'iron_ingot',     'переплавить железо',       'печь + уголь'),
    ('ipick',    'iron_pickaxe',   'сделать железную кирку',   'верстак + железо'),
    ('isword',   'iron_sword',     'сделать железный меч',     'верстак + железо'),
    ('ihelm',    'iron_helmet',    'сделать железный шлем',    'верстак + железо'),
    ('ichest',   'iron_chestplate','сделать железную броню',   'верстак + железо'),
    ('door',     'wooden_door',    'сделать дверь',            'верстак + доски'),
    ('chest',    'chest',          'сделать сундук',           'верстак + доски'),
    ('wool',     'white_wool',     'добыть шерсть',            'охота/стрижка'),
    ('bed',      'bed',            'сделать кровать',          'верстак + шерсть'),
    ('leggings', 'iron_leggings',  'сделать железные штаны',   'верстак + железо'),
    ('boots',    'iron_boots',     'сделать железные ботинки', 'верстак + железо'),
    ('bucket',   'bucket',         'сделать ведро',            'верстак + железо'),
    ('string',   'string',         'добыть нити',              'паук'),
    ('bow',      'bow',            'сделать лук',              'палки + нити'),
    ('arrow',    'arrow',          'сделать стрелы',           'кремень + перо'),
]

# Бесконечная программа: после ступеней существо поддерживает снаряжение
# и запасы — всегда есть чему учиться и что улучшать.
UPKEEP = ['iron_pickaxe', 'iron_sword', 'iron_chestplate', 'iron_helmet',
          'torch', 'bread', 'stone_pickaxe', 'stone_axe']


class Curriculum:
    def __init__(self, recipes, file=CURRICULUM_FILE):
        self.recipes = recipes
        self.file = file
        self.steps = list(STEPS)
        self.current = 0            # индекс текущей ступени
        self.done = []              # id пройденных ступеней
        self.last_attempt = 0.0
        self.fail_count = 0
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.current = d.get('current', 0)
            self.done = d.get('done', [])
            self.fail_count = d.get('fail_count', 0)
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'current': self.current, 'done': self.done,
                           'fail_count': self.fail_count}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- СОСТОЯНИЕ ----------

    def all_done(self):
        return self.current >= len(self.steps)

    def current_step(self):
        if self.all_done():
            return None
        sid, item, name, need = self.steps[self.current]
        return {'id': sid, 'item': item, 'name': name, 'need': need}

    def progress(self):
        ids = {s[0] for s in self.steps}
        learned = sum(1 for d in self.done if d in ids)
        return f"{learned}/{len(self.steps)}"

    def next_goal(self, inventory):
        """Какую вещь делать прямо сейчас. Возвращает dict или None.

        Если текущая ступень уже достигнута (предмет есть в инвентаре) —
        отмечает её пройденной и переходит к следующей. Когда все ступени
        пройдены, начинается бесконечный режим: существо поддерживает
        снаряжение (инструменты, броню, свет) и запасы еды — всегда есть
        чему учиться и что улучшать.
        """
        while not self.all_done():
            sid, item, name, need = self.steps[self.current]
            if self._has(inventory, item):
                if sid not in self.done:
                    self.done.append(sid)
                    print(f"🎓 Научился: {name} ({item}) — {self.progress()}")
                self.current += 1
                self.fail_count = 0
                self.save()
                continue
            return {'id': sid, 'item': item, 'name': name, 'need': need,
                    'craft': self.recipes.is_craft(item),
                    'base': self.recipes.base_ingredients(item)}
        return self._upkeep_goal(inventory)

    def _upkeep_goal(self, inventory):
        """Бесконечная программа: поддерживать снаряжение и запасы."""
        for want in UPKEEP:
            have = self._count(inventory, want)
            if have < 2:
                return {'id': f'keep_{want}', 'item': want,
                        'name': f'запас: {want} ({have}/2)', 'need': 'бесконечный рост',
                        'craft': self.recipes.is_craft(want),
                        'base': self.recipes.base_ingredients(want)}
        return None

    @staticmethod
    def _count(inventory, item):
        total = 0
        for i in inventory:
            n = i.get('name', '')
            if n == item or item in n:
                total += i.get('count', 0)
        return total

    def ids(self):
        return {s[0] for s in self.steps}

    def mark_done(self, sid):
        if sid not in self.done:
            self.done.append(sid)
            self.save()

    def note_failure(self):
        self.fail_count += 1
        self.save()

    # ---------- ПЛАН ПО СТУПЕНИ ----------

    def plan_for(self, goal):
        """Разложить текущую цель на шаги (добыча + крафт по порядку)."""
        return self.recipes.plan(goal['item'])

    @staticmethod
    def _has(inventory, item):
        for i in inventory:
            n = i.get('name', '')
            if n == item or item in n:
                return True
        return False

    def summary(self):
        if self.all_done():
            return f"программа пройдена ({self.progress()}) — учусь сама"
        s = self.current_step()
        return f"учусь: {s['name']} ({self.progress()})"
