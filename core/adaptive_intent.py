"""
AdaptiveIntent — понимание речи папы.

Ребёнок учится понимать команды постепенно: сначала по подсказкам-словам,
затем через LLM, и запоминает выученное. Отдельно — имитация: «повтори за
мной» запускает зеркальное поведение (mimic_last).
"""
import json
import os
import re
import requests


LEARNED_FILE = "data/learned_intents.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"

# LLM иногда возвращает пример из промпта целиком ("<фраза ребёнка>").
PLACEHOLDER = re.compile(r'[<{][^<>{}]{0,60}[>}]')


HINTS = {
    'go_to_player': ['подойди', 'ко мне', 'иди сюда', 'за мной', 'следуй'],
    'walk_away_from_player': ['отойди', 'отходи', 'уйди', 'подальше', 'отвали'],
    'come_close_to_player': ['вплотную', 'прижмись', 'обними'],
    'sprint_short': ['побеги', 'беги', 'спринт', 'пробегись', 'быстрее', 'рвани', 'ускорься'],
    'sneak': ['присядь', 'красться', 'приседай'],
    'jump_once': ['прыгни', 'прыгай', 'прыжок'],
    'jump_forward': ['прыгни вперёд', 'прыгни далеко'],
    'spin_around': ['покрутись', 'обернись', 'вращайся', 'кругом'],
    'look_at_player': ['посмотри на меня', 'взгляни на меня'],
    'stop': ['стой', 'остановись', 'замри', 'не двигайся'],
    'stay_here': ['оставайся', 'стой тут', 'стой здесь'],
    'dig_tree': ['сруби дерев', 'добудь дерев', 'руби дерев', 'добыть дерев', 'брёвн', 'сруби дерево'],
    'dig_down': ['копай вниз', 'копай под собой'],
    'dig_forward': ['копай вперёд'],
    'dig_up': ['копай вверх'],
    'dig_nearby': ['копай', 'копа', 'руби', 'ломай', 'добудь землю', 'добывай землю'],
    'place_block': ['поставь блок', 'положи блок', 'строй', 'построй'],
    'build_shelter': ['построй укрытие', 'построй дом', 'построй домик', 'укрытие', 'домик'],
    'drop_item': ['выброси', 'брось', 'выкинь', 'дропни'],
    'eat_food': ['съешь', 'поешь', 'покушай', 'поесть'],
    'equip_best_armor': ['надень броню', 'одень броню', 'натяни броню'],
    'unequip_armor': ['сними броню', 'снять броню', 'убери броню'],
    'find_and_attack': ['убей', 'атакуй', 'ударь'],
    'attack_nearest': ['атакуй ближайшего'],
    'mimic_last': ['повтори за мной', 'сделай как я', 'повтори', 'имитируй', 'как я сделал'],
}


CHATTER_MARKERS = [
    'молодец', 'спасибо', 'класс', 'супер', 'ого', 'вау', 'круто',
    'как дела', 'что ты', 'ты кто', 'это кто', 'хватит',
    'что можешь', 'что умеешь', 'почему', 'зачем',
    # приветствия — это разговор, а не команда: иначе «привет! я тут»
    # превращается в цель и бот бесконечно идёт к папе.
    'привет', 'здравствуй', 'хай', 'доброе утро', 'добрый день',
    'добрый вечер', 'как ты', 'что делаешь',
]


class AdaptiveIntent:
    def __init__(self, actions_catalog):
        self.catalog = actions_catalog
        self.file = LEARNED_FILE
        self.learned = {}
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                self.learned = json.load(f)
            if self.learned:
                print(f"🗣️  Помню {len(self.learned)} фраз → действие")
        except Exception:
            pass

    def save(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump(self.learned, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _normalize(self, text):
        t = text.lower().strip()
        t = re.sub(r'[^а-яёa-z0-9 ]', '', t)
        t = re.sub(r'\s+', ' ', t)
        return t

    def _is_chatter(self, text):
        t = text.lower().strip()
        for m in CHATTER_MARKERS:
            if m in t:
                return True
        if len(t.split()) > 12:
            return True
        return False

    def _hint_for(self, text):
        t = text.lower()
        for action, keywords in HINTS.items():
            for kw in keywords:
                if kw in t:
                    if self.catalog.has(action):
                        return action
        return None

    def resolve(self, user_text, context):
        if self._is_chatter(user_text):
            return None, None, None, 'chatter'

        norm = self._normalize(user_text)
        if norm in self.learned:
            action = self.learned[norm]
            if self.catalog.has(action):
                return action, None, None, 'learned'

        hint = self._hint_for(user_text)
        if hint:
            self.learned[norm] = hint
            self.save()
            return hint, None, None, 'hint'

        action, params, say = self._ask_llm(user_text, context)
        if action and action != 'unknown' and self.catalog.has(action):
            self.learned[norm] = action
            self.save()
            print(f"🗣️  Выучил: '{user_text}' → {action}")
            return action, params, say, 'llm'

        if say:
            return None, None, say, 'llm_none'
        return None, None, None, 'none'

    def _clean_say(self, say):
        """Отбросить примеры из промпта и слишком длинные/английские ответы."""
        if not say or not isinstance(say, str):
            return None
        say = PLACEHOLDER.sub('', say).strip().strip('"\'').strip()
        if not say:
            return None
        if len(re.findall(r'[a-zA-Z]{3,}', say)) >= 2:
            return None
        if len(say) > 150:
            say = say[:150]
        return say or None

    def _ask_llm(self, user_text, context):
        actions_list = self.catalog.describe_for_prompt()
        hint = self._hint_for(user_text)
        hint_str = f"\nПОДСКАЗКА: '{hint}'" if hint else ""

        prompt = f"""Ты — мозг ребёнка в игре. Пойми команду игрока.

ДЕЙСТВИЯ:
{actions_list}
{hint_str}

Игрок: "{user_text}"

ПРАВИЛА:
- Если это РАЗГОВОР (похвала, вопрос) → action="none".
- Если команда и есть действие → точное имя.
- Если команда, но нет действия → action="unknown".

Ответь ОДНИМ JSON:
{{"action": "...", "params": null, "say": "<фраза ребёнка>"}}"""

        try:
            r = requests.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                "format": "json",
                "options": {"temperature": 0.2, "num_predict": 80}
            }, timeout=60)
            if r.status_code != 200:
                return None, None, None
            data = json.loads(r.json().get('response', '').strip())
            return data.get('action'), data.get('params'), self._clean_say(data.get('say'))
        except Exception as e:
            print(f"AdaptiveIntent LLM ошибка: {e}")
            return None, None, None

    def summary(self):
        if not self.learned:
            return "пока ничего не выучил"
        items = list(self.learned.items())[-10:]
        return '\n'.join([f"- '{k}' → {v}" for k, v in items])
