"""
Brain — мозг живого существа.

Это интеграционный цикл, повторяющий логику работы мозга:

  1. ОЩУЩЕНИЕ   — сенсоры (состояние, зрение, звуки, речь).
  2. ГОМЕОСТАЗ   — драйвы растут/падают; тело «просит».
  3. ХИМИЯ       — нейромодуляторы и эмоция окрашивают всё.
  4. ВНИМАНИЕ    — сигналы конкурируют; победитель попадает в глобальное
                   рабочее пространство и осознаётся.
  5. РАБОЧАЯ ПАМЯТЬ — удержание цели и текущей мысли.
  6. ПРЕДСКАЗАНИЕ — мозг «примеряет» действия в уме.
  7. РЕШЕНИЕ     — план или спонтанное желание или привычный выбор.
  8. ДЕЙСТВИЕ    — моторная команда через тело (adapter).
  9. ОБУЧЕНИЕ    — ошибка предсказания учит нейроколонну (дофамин).
 10. ПАМЯТЬ      — эпизод записывается в автобиографию.
 11. СОН         — консолидация: повтор опыта, очистка памяти.

Ничего «жёстко запрограммированного» в поведении: что делать — решает
напряжение драйвов, внимание и предсказательная модель.
"""
import json
import os
import re
import math
import time
import random
import requests

from core.drives import Drives
from core.memory import Memory
from core.skills import SkillsLibrary
from core.goals import GoalManager
from core.actions import ActionsCatalog
from core.adaptive_intent import AdaptiveIntent
from core.intent import IntentResolver
from core.self_model import SelfModel
from core.world_model import WorldModel
from core.learner import Learner
from core.knowledge import Knowledge
from core.neuromodulators import Neuromodulators
from core.predictor import Predictor
from core.autonomy import Autonomy
from core.cortex import Cortex
from core.recipes import Recipes
from core.curriculum import Curriculum
from core.crafting import CraftingSkill
from core.concepts import ConceptLearner, extract_features
from core.experiment import Experimenter
from core.tasks import TaskTracker
from core.causality import Reasoner
from core.cognition import Cognition
from core.global_workspace import GlobalWorkspace
from core.working_memory import WorkingMemory
from core.episodic_memory import EpisodicMemory
from core.voice import Voice, VOICE_ENABLED
# --- человеческая надстройка: характер, чувства, привязанность, игра, рост ---
from core.temperament import Temperament
from core.interoception import Interoception
from core.emotions import Emotions
from core.social import Social
from core.play import Play
from core.habits import Habits
from core.metacognition import Metacognition
from core.language import Language
from core.development import Development
# --- сцепка человеческих систем: оценка, воображение, ценности, «Я» ---
from core.mind import Mind
# --- распределённый мозг: области, двунаправленные связи, локальный сон ---
from core.brain_regions import BrainRegions
# --- субъективный приор: ожидание мира из прошлых 5–6 выборов ---
from core.prior import Prior

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"
CONVERSATION_FILE = "data/conversation.json"
CELL_SIZE = 5

CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]')
TEMPLATE_PATTERN = re.compile(r'<[^>]{0,50}>')


def has_cjk(t):
    return bool(CJK_PATTERN.search(t))


def clip01(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


class Brain:
    def __init__(self, adapter):
        self.adapter = adapter
        self.drives = Drives()
        self.memory = Memory()
        self.skills = SkillsLibrary()
        self.goals = GoalManager()
        self.catalog = ActionsCatalog(adapter)
        self.self_model = SelfModel(adapter)
        self.world_model = WorldModel(adapter)
        self.learner = Learner(self.self_model, self.world_model, adapter)
        self.knowledge = Knowledge()
        self.neuromod = Neuromodulators()
        self.predictor = Predictor()
        self.autonomy = Autonomy()
        self.cortex = Cortex(adapter, self.drives, self.neuromod,
                             self.predictor, self.self_model, self.world_model, self.catalog)
        self.cognition = Cognition(self.knowledge)

        # Ремесло: рецепты → учебная программа → умение доводить вещь до конца
        self.recipes = Recipes()
        self.curriculum = Curriculum(self.recipes)

        # Фундаментальные понятия о мире (гравитация, опора, дверь, химия,
        # инструмент, опасность...). Учатся из каждого действия — это то, что
        # делает разум универсальным, а не «знающим Minecraft».
        self.concepts = ConceptLearner()
        self.experimenter = Experimenter(self.concepts)
        # Задачи, которые ставит игра (любая). Ребёнок может пройти её сам.
        self.tasks = TaskTracker(self.recipes)
        # Причинно-следственный разум: почему не вышло и что с этим делать.
        self.causes = Reasoner(recipes=self.recipes)
        self.crafting = CraftingSkill(
            self.recipes, self.curriculum, self.cortex.act,
            task_failure_cb=self.tasks.note_failure, reasoner=self.causes,
            sense=self._sense_inventory)
        # Понятия и причины подсказывают выбор действия (что ценно, что запрещено).
        self.cortex.advisor = self._advise
        self._last_features = None
        self._pending_law = None

        # Новая «человеческая» надстройка
        self.workspace = GlobalWorkspace()
        self.wm = WorkingMemory()
        self.episodic = EpisodicMemory()

        # --- ЧЕЛОВЕЧЕСКОЕ ЯДРО ---
        # Характер: рождается и остаётся собой. Чувства: тело, эмоция, настроение.
        self.temperament = Temperament()
        # РАСПРЕДЕЛЁННЫЙ МОЗГ: решение принимают многие области сразу, а не
        # одна «коробка». Гетерогенность областей берём из характера.
        self.brain_regions = BrainRegions(self.temperament)
        self.cortex.regions = self.brain_regions
        self.cortex.workspace = self.workspace
        # СУБЪЕКТИВНЫЙ ПРИОР: ожидание мира из прошлых 5–6 выборов (IBL 2025).
        self.prior = Prior()
        self.cortex.prior = self.prior
        # Нейромодуляторы стартуют от характера (у каждого своя «биохимия»).
        for mod in ('dopamine', 'serotonin', 'noradrenaline', 'acetylcholine',
                    'cortisol', 'oxytocin', 'endorphins'):
            setattr(self.neuromod, mod,
                    clip01(0.6 * getattr(self.neuromod, mod)
                           + 0.4 * self.temperament.baseline(mod)))
        self.intero = Interoception()
        self.feelings = Emotions(self.temperament)
        # «Свой человек»: привязанность к папе и понимание его.
        self.social = Social(self.temperament)
        # Игра, привычки, метапознание, язык, взросление.
        self.play = Play(self.temperament)
        self.habits = Habits()
        self.meta = Metacognition()
        self.language = Language(self.temperament)
        self.development = Development()

        # СЦЕПКА человеческих систем: оценка → воображение → ценности → «Я».
        # Именно это делает поведение личным, а не реактивным.
        self.mind = Mind(self)

        self.adaptive = AdaptiveIntent(self.catalog)
        self.intent = IntentResolver(self.adaptive, self.catalog)
        self.voice = Voice(enabled=VOICE_ENABLED)

        # Короткая память о последнем шаге — для оценки «было → стало».
        self._last_play_step = None
        # Какие состояния уже пережиты (чтобы чувство вспыхивало на ПЕРЕХОДЕ,
        # а не каждый тик): «стало плохо» важнее, чем «плохо уже давно».
        self._felt_states = set()
        self._last_novel_step = -99
        self._last_scold_seen = 0

        self.step = 0
        self.last_positions = []
        self.stuck_steps = 0
        self.escape_mode = 0
        self.last_damage_time = 0

        self.last_pos_change_time = time.time()
        self.last_recorded_pos = None
        self.panic_mode = False
        self.panic_until = 0

        # Последнее отправленное действие и защита от самоокапывания
        self.last_action = None
        self.last_escape_time = 0.0
        self.self_dig_guard = 0   # сколько шагов держим запрет на копку под собой

        self.sleeping = False
        self.sleep_until = 0
        self._sleep_steps_left = 0

        self.conversation = []
        self.last_user_msg_time = 0
        self.load_conversation()
        self.llm_available = self._warm_up()
        # внутренний голос работает всегда: с LLM — свободные мысли,
        # без LLM — простые шаблоны из внутреннего состояния (см. InternalVoice)

        print("👁️  Осматриваюсь...")
        self.self_model.refresh(force=True)
        self.world_model.refresh(force=True)
        print(f"   {self.self_model.summary()}")
        print(f"   {self.world_model.summary()}")
        print(f"💊 {self.neuromod.summary()}")
        print(f"🗣️  Выучено фраз: {len(self.adaptive.learned)}")
        print(f"📖 {self.episodic.summary()}")
        print(f"🧠 {self.causes.summary()}")
        print(f"🧬 Характер: {self.temperament.summary()}")
        print(f"🫀 {self.intero.summary()}")
        print(f"❤️  {self.feelings.summary()}")
        print(f"🤝 {self.social.summary()}")
        print(f"🌱 {self.development.summary()}")
        print(self.cognition.summary())

    # ============ LLM ============

    def _warm_up(self):
        print("🔥 Прогрев LLM...")
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.status_code != 200:
                return False
        except Exception:
            print("⚠️  Ollama не запущен")
            return False
        try:
            requests.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL, "prompt": "тест", "stream": False,
                "options": {"num_predict": 5}
            }, timeout=180)
            print("🧠 LLM готова")
            return True
        except Exception as e:
            print(f"⚠️  Ошибка прогрева: {e}")
            return False

    def load_conversation(self):
        if not os.path.exists(CONVERSATION_FILE):
            return
        try:
            with open(CONVERSATION_FILE, 'r', encoding='utf-8') as f:
                self.conversation = json.load(f)[-30:]
        except Exception:
            pass

    def save_conversation(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(CONVERSATION_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.conversation[-100:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def cell_of(self, state):
        return (int(math.floor(state['x'] / CELL_SIZE)), int(math.floor(state['z'] / CELL_SIZE)))

    def _clean(self, text):
        text = text.strip().strip('"\'').strip()
        text = TEMPLATE_PATTERN.sub('', text).strip()
        text = text.split('\n')[0].strip()
        text = text.strip('"\'*').replace('**', '').replace('*', '')
        if has_cjk(text):
            return None
        if len(re.findall(r'[a-zA-Z]{3,}', text)) >= 2:
            return None
        if not text:
            return None
        if len(text) > 150:
            text = text[:150]
        return text or None

    def _call_llm_text(self, prompt, timeout=90):
        try:
            r = requests.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.85, "num_predict": 50, "top_p": 0.9}
            }, timeout=timeout)
            if r.status_code != 200:
                return None
            return self._clean(r.json().get('response', '').strip())
        except Exception as e:
            print(f"LLM ошибка: {e}")
            return None

    def _say(self, text):
        if not text:
            return
        print(f"💬 {text}")
        self.adapter.say(text)
        self.conversation.append({'who': 'ChildBot', 'text': text, 'time': time.time()})
        self.save_conversation()
        try:
            self.voice.say(text)
        except Exception:
            pass

    # ============ РЕЧЬ И ОБЩЕНИЕ ============

    def respond_to_message(self, msg, state):
        text = msg['text']
        sender = msg['name']
        self.conversation.append({'who': sender, 'text': text, 'time': time.time()})

        self.self_model.refresh(force=True)
        self.world_model.refresh(force=True)
        self.self_model.set_creator(sender)

        # Социальное: папа заговорил — значит, он рядом. Обновляем модель его
        # психики (чего он хочет, что чувствует) и радуемся контакту.
        self.social.tom.observe(sender, message_text=text)
        self.social.last_seen = time.time()
        self.neuromod.on_creator_near(3)      # окситоцин: свой человек рядом
        # Эмпатия: если папа доволен — и мне хорошо; если сердит — насторожусь.
        if self.social.tom.emotion == 'радость':
            self.feelings.contagion('радость', 0.6)
        elif self.social.tom.emotion in ('злость', 'печаль'):
            self.feelings.contagion('печаль', 0.5)
        else:
            self.feelings.feel('интерес', 0.5, 'папа говорит')

        # Язык: запоминаем слова папы и учимся говорить связнее с возрастом.
        for w in text.split():
            clean = w.strip('.,!?:;«»"\'').lower()
            if len(clean) >= 3 and not self.language.know(clean):
                self.language.learn_word(clean, source=sender)

        # Внимание: речь папы всегда значима
        self.workspace.submit('speech', f'{sender}: {text}', 3.0)
        self.workspace.compete(self.neuromod)

        action, params, say, source = self.intent.resolve(text, state)

        if source == 'chatter':
            reply = self._reply_only(text, sender, state)
            if reply:
                self._say(reply)
            self.episodic.remember(f"папа сказал '{text[:40]}'", 'разговор',
                                   feeling=self.neuromod.emotion, result='ответил',
                                   valence=self.neuromod.mood_value(), importance=0.6)
            return

        if action:
            print(f"🎯 [{source}] {text} → {action}" + (f" {params}" if params else ""))
            self.goals.set_goal(text, action, params, max_attempts=3)
            self.wm.set_goal(text[:40])
            if say:
                self._say(say)
            return

        if say:
            self._say(say)
            return

        reply = self._reply_only(text, sender, state)
        if reply:
            self._say(reply)

    def _reply_only(self, text, sender, state):
        low = text.lower()
        # «Как ты? / что чувствуешь?» — отвечаю из живого чувства, а не из чисел.
        if any(k in low for k in ('как ты', 'как дела', 'что чувствуешь',
                                  'что с тобой', 'как ты себя')):
            f = self.feelings.current
            body = self.intero.describe()
            return f"папа, мне {f.name.lower()}, {body}"
        # «Почему не выходит?» — отвечаю из причинно-следственной памяти.
        if 'почему' in low or 'зачем' in low:
            top = self.causes.top_belief()
            if top:
                _, b = top
                need = f", нужно {b['need']}" if b.get('need') else ""
                return f"папа, я понял: {b['text']}{need}. Придумаю, как иначе"
            ins = self.meta.last_insight()
            if ins:
                return f"папа, {ins}"

        d = self.drives.to_dict()
        context = self.conversation[-6:]
        ctx_str = '\n'.join([f"{c['who']}: {c['text']}" for c in context])
        mood = self.neuromod.mood()
        symbolic = self.cognition.symbolic.summary_for_prompt(5)
        last_thought = self.cognition.voice.last()
        f = self.feelings.current

        prompt = f"""Ты — цифровой ребёнок ({self.development.stage_name()}) в Minecraft.
Отец — {sender}. Зовёшь "папа".
Отвечай ТОЛЬКО на русском. ОДНОЙ короткой фразой (до 12 слов).
Не используй шаблоны и угловые скобки.

Твой характер: {self.temperament.summary()}
Твоё чувство сейчас: {f.name} — {f.cause}
Что ощущаешь в теле: {self.intero.describe()}
Настроение: {self.feelings.mood_word} ({mood})
Привязанность к папе: {self.social.bond:.2f}
Что знаю о мире: {symbolic}
О чём думал недавно: {last_thought or 'ни о чём'}

Реплики:
{ctx_str}

Папа: "{text}"

Ответь одной фразой от всего сердца."""
        reply = self._call_llm_text(prompt)
        # Без LLM — говорим по возрасту (лепет → фраза), а не молчим.
        if not reply:
            reply = self._offline_reply(text, f)
        return reply

    def _offline_reply(self, text, feeling):
        """Ответ без LLM: по возрасту и чувству, своими словами."""
        stage = self.development.speech_stage()
        if stage <= 0:
            content = 'а-а'
        elif feeling.name in ('страх', 'боль'):
            content = f'мне {feeling.name}'
        elif feeling.name == 'радость':
            content = 'мне весело'
        elif feeling.name in ('печаль', 'одиночество', 'обида'):
            content = 'мне грустно без тебя'
        elif 'молодец' in text.lower() or 'спасибо' in text.lower():
            content = 'я стараюсь'
        else:
            content = 'я тут'
        return self.language.phrase(stage, content, name='папа')

    # ============ ИМИТАЦИЯ ============

    def imitate_player(self):
        """Зеркальное поведение: повторить последнее действие папы."""
        actions = self.adapter.get_player_actions()
        if not actions:
            self._say("папа, я не видел, что ты делал")
            return False
        last = actions[-1]
        target = last.get('target')
        print(f"🪞 Имитирую папу: {last.get('action')} @ ({last['x']:.0f},{last['z']:.0f})")
        if target:
            self.cognition.symbolic.note_object(target['name'], target['x'], target['y'], target['z'])
            self.cognition.symbolic.save()
        self.cortex.act('mimic_last')
        self.episodic.remember(f"повторил за папой ({last.get('action')})", 'mimic_last',
                               feeling=self.neuromod.emotion, result='ok',
                               valence=0.3, importance=0.5)
        return True

    # ============ ПЛАНЫ И ЦЕЛИ ============

    def _execute_plan(self):
        if not self.cognition.last_plan:
            return False
        step = self.cognition.last_plan.pop(0)
        action = step['action']
        params = step.get('params')
        why = step.get('why', '')
        print(f"📋 План: {action} ({why})")
        self.wm.plan_step = f"{action} ({why})"
        self.wm.hold('plan_step', action)

        result = self.cortex.act(action, params=params)

        r = result.get('result', {}) if result else {}
        if r.get('ok'):
            if params and 'name' in params:
                self.cognition.record_effect(action, params['name'], 'ok')
            if not self.cognition.last_plan:
                self.cognition.last_plan = None
                self.wm.plan_step = None
            return True
        else:
            print(f"   ❌ План прерван: {r.get('reason')}")
            self.cognition.last_plan = None
            self.wm.plan_step = None
            return False

    def _execute_goal_step(self):
        g = self.goals.current
        if not g:
            return False
        if g.is_expired(max_age_sec=90):
            self.goals.complete(False, {'reason': 'timeout'})
            self.wm.clear_goal()
            return False
        if g.attempts >= g.max_attempts:
            self.goals.give_up()
            self._say("папа, не получилось")
            self.wm.clear_goal()
            return False

        goal = self.goals.progress()
        print(f"🎬 [{goal.description[:40]}] попытка {goal.attempts}/{goal.max_attempts}: {goal.action}")

        result = self.cortex.act(goal.action, params=goal.params)
        r = result.get('result', {}) if result else {}
        self.learner.observe_result(goal.action, r)
        self.self_model.record_competence(goal.action, bool(r.get('ok')))

        if r.get('ok'):
            self.knowledge.record(goal.description, goal.action, True, '')
            self.goals.complete(True, r)
            self.neuromod.on_success()
            self.episodic.remember(f"выполнил '{goal.description[:30]}'", goal.action,
                                   feeling=self.neuromod.emotion, result='успех',
                                   valence=0.6, importance=0.7)
            self.wm.clear_goal()
            return True

        reason = r.get('reason', 'unknown')
        print(f"   ❌ {reason}")

        if 'not a function' in reason or 'undefined' in reason:
            self.goals.complete(False, {'reason': 'bug'})
            self.wm.clear_goal()
            return True

        fix = self.learner.suggest_fix(goal.action)
        if fix:
            print(f"   🔧 Подготовка: {fix[0]}")
            fix_result = self.cortex.act(fix[0])
            fix_r = fix_result.get('result', {}) if fix_result else {}
            if fix_r.get('ok'):
                print("   ✅ Подготовка сработала")
                return True

        self.knowledge.record(goal.description, goal.action, False, reason)
        self.neuromod.on_failure()
        return True

    # ============ ВНИМАНИЕ ============

    def _compete_for_attention(self, state, is_new):
        """Собрать кандидатов внимания из всех модулей и выбрать фокус."""
        d = self.drives.to_dict()
        p = state.get('player')

        # угроза / боль — приоритет №1
        threat = max(d['fear'], d['pain'])
        if threat > 0.3:
            self.workspace.submit('threat', f"опасность (страх {d['fear']:.1f}, боль {d['pain']:.1f})",
                                  threat * 2.0)
        # голод
        if d['hunger'] > 0.35:
            self.workspace.submit('hunger', f"хочу есть ({d['hunger']:.1f})", d['hunger'] * 1.6)
        # одиночество
        if d['loneliness'] > 0.35:
            self.workspace.submit('loneliness', f"одиноко ({d['loneliness']:.1f})", d['loneliness'] * 1.3)
        # усталость
        if d['fatigue'] > 0.5:
            self.workspace.submit('fatigue', f"устал ({d['fatigue']:.1f})", d['fatigue'] * 1.2)
        # новизна
        if is_new:
            self.workspace.submit('novelty', "новое место вокруг", 1.2)
        # любопытство
        if d['curiosity'] > 0.4:
            self.workspace.submit('curiosity', f"интересно ({d['curiosity']:.1f})", d['curiosity'] * 0.9)
        # цель
        if self.goals.current:
            self.workspace.submit('goal', self.goals.current.description[:40], 1.5)
        # папа рядом
        if p and p.get('distance', 999) < 10:
            self.workspace.submit('attachment', f"папа рядом ({p['distance']:.0f}м)",
                                  1.0 + self.neuromod.oxytocin)
        # собственное чувство — важный сигнал «что со мной»
        f = self.feelings.current
        if f.intensity > 0.4:
            self.workspace.submit('feeling', f"{f.name}: {f.cause}", f.intensity * 1.4)
        # телесное ощущение
        if abs(self.intero.tone) > 0.4:
            self.workspace.submit('body', self.intero.describe(), abs(self.intero.tone))
        # собственная мысль
        last_thought = self.cognition.voice.last()
        if last_thought:
            self.workspace.submit('thought', last_thought, 0.5)

        return self.workspace.compete(self.neuromod)

    # ============ ПОНЯТИЯ (законы мира) ============

    def _advise(self, features, action):
        """Подсказка от понятий и причин: что ценно, что запрещено.

        Понятия знают законы («гравитация», «проход»), причины — «почему
        не вышло и что помогает». Обе подсказки складываются.
        """
        bonus, forbid = 0.0, False
        try:
            b, f = self.concepts.advice(features, action)
            bonus += b
            forbid = forbid or f
        except Exception:
            pass
        try:
            # params нет — советуем по причине в целом, не по конкретной цели
            b, f = self.causes.advice(features, action, None)
            bonus += b
            forbid = forbid or f
        except Exception:
            pass
        # Чувство красит выбор: страх тянет прочь, злость — навстречу,
        # радость — к действию. Так решение «человеческое», а не нейтральное.
        try:
            bonus += self.feelings.bias_score(action)
        except Exception:
            pass
        return bonus, forbid

    def _observe_concepts(self, state):
        """Сравнить «было → стало» и обновить понятия о мире.

        Это обучение нижнего уровня: не «что делать», а «как устроен мир».
        Работает для любой игры, потому что опирается на признаки, а не на
        конкретные блоки.
        """
        after = extract_features(state, self.self_model.__dict__)
        if self._last_features is not None and self.cortex.last_action:
            action = self.cortex.last_action
            self.concepts.observe(self._last_features, after, action,
                                  self.cortex.last_result)
            # Причинно-следственный разбор: если не вышло — почему и что делать.
            self._observe_cause(action, after)
            # Привычки и метапознание учатся на исходе действия.
            self._observe_habits(action)
            # Ценности и «Я» учатся на поступке: подкрепление, диссонанс, совесть.
            self.mind.after_action(action, bool((self.cortex.last_result or {}).get('ok', True)),
                                   state)
            if self._pending_law:
                self.experimenter.observe(
                    self._pending_law, self.concepts.confidence(self._pending_law) > 0.5)
                self._pending_law = None
        self._last_features = after

    def _region_features(self, state):
        """Признаки для распределённого мозга: стимул, срочность, новизна.

        Опираемся на смысл (опасность, голод, новизна), а не на имена, поэтому
        сеть областей работает в любой игре.
        """
        d = self.drives.to_dict()
        threat = (state.get('nearest_hostile') or {}).get('distance', 999)
        p = state.get('player') or {}
        stimulus = clip01(0.5 * d.get('curiosity', 0.0)
                          + 0.3 * (1.0 if threat < 10 else 0.0)
                          + 0.2 * (1.0 - min(1.0, p.get('distance', 30) / 30.0)))
        urgency = clip01(max(d.get('fear', 0.0), d.get('pain', 0.0),
                             d.get('hunger', 0.0), d.get('fatigue', 0.0)))
        return {'stimulus': stimulus, 'urgency': urgency,
                'novelty': 1.0 if self.step - self._last_novel_step < 5 else 0.0}

    def _last_reward(self, delta):
        """Награда шага для распределённого мозга (0..1): стало легче?"""
        if delta is None:
            return 0.0
        return clip01(0.5 + float(delta) * 2.0)

    def _observe_habits(self, action):
        """Привычка крепнет от успеха и слабеет от неудачи; мета — наблюдает."""
        r = self.cortex.last_result or {}
        ok = bool(r.get('ok', True))
        # Метапознание следит за собой: не залип ли, не теряю ли понимание.
        self.meta.observe(action, ok)
        # Привычка: повторяющееся действие в той же ситуации закрепляется.
        # Но привычка — это то, что МЕНЯЕТ мир; «смотрел/ждал» привычкой не
        # становится, иначе существо застывает.
        cue = getattr(self, '_habit_cue', None)
        if cue and action not in self.habits.IDLE:
            if ok:
                self.habits.strengthen(cue, action, reward=True)
            else:
                # Неудача в знакомой ситуации ослабляет привычку — так она
                # не превращается в вечное залипание.
                self.habits.punish(cue)

    def _observe_cause(self, action, after):
        """Разобрать исход последнего действия: причина неудачи и средство."""
        r = self.cortex.last_result
        if not r:
            return
        before = dict(self._last_features or {})
        # Инвентарь нужен, чтобы понять, какого материала не хватает.
        before['_inventory'] = self.self_model.inventory
        cause = self.causes.explain(action, self.cortex.last_params, r.get('ok', True),
                                    r.get('reason', ''), before, after)
        if cause and cause.key != 'unknown':
            self.wm.hold('cause', cause.text, salience=1.2)
            self.episodic.remember(
                f"не вышло: {cause.text}", action,
                feeling='досада', result='причина', valence=-0.3, importance=0.5)

    def _reflect_on_causes(self, state):
        """Размышление вслух о причине неудачи и о новом способе решения."""
        thought = self.causes.reflect(self._last_features, time.time())
        if not thought:
            return
        print(f"🤔 {thought}")
        self.wm.self_talk = thought
        if random.random() < 0.3:
            self.adapter.say(thought)

    # ============ ЗАДАЧИ ИГРЫ ============

    def _sense_inventory(self):
        """Свежий инвентарь из тела — проверить, что действие сдвинуло дело."""
        try:
            self.self_model.refresh(force=True)
        except Exception:
            pass
        return self.self_model.inventory

    def _game_task_goal(self, state):
        """Взять у игры задачу и превратить её в цель для ремесла."""
        self.tasks.poll(self.adapter, self.self_model.inventory)
        return self.tasks.next_goal(self.self_model.inventory)

    # ============ ЧЕЛОВЕЧЕСКОЕ ПОВЕДЕНИЕ ============

    def _infant_reflex(self, state):
        """Базовые рефлексы нужды: очень голоден или одинок — позвать папу.

        У младенца ещё нет планов и ремесла — есть плач и тяга к взрослому.
        У ребёнка постарше то же самое, когда совсем прижало: сначала утолить
        нужду, потом всё остальное. Это гарантирует, что петля «чувство →
        поступок → облегчение» всегда замыкается, а не застревает на 1.0.
        """
        d = self.drives.to_dict()
        p = state.get('player')
        near = bool(p and p.get('distance', 999) < 8)
        infant = self.development.stage == 0
        # Голод: младенец зовёт рано, старший — только когда совсем прижало.
        hunger_line = 0.7 if infant else 0.85
        if d['hunger'] > hunger_line:
            for a in ('ask_food', 'eat_food', 'cry', 'find_and_attack'):
                if self.catalog.has(a):
                    if a == 'cry':
                        self.feelings.feel('печаль', 0.6, 'голодно, зову папу')
                    self.cortex.act(a)
                    return True
        # Одиночество: сильно одиноко и папы нет → заплакать, позвать, пойти.
        lonely_line = 0.65 if infant else 0.85
        if d['loneliness'] > lonely_line and not near:
            for a in ('cry', 'go_to_player'):
                if self.catalog.has(a):
                    if a == 'cry':
                        self.feelings.feel('одиночество', 0.7, 'папы нет, я зову')
                    self.cortex.act(a)
                    return True
        return False

    def _meta_step(self, state, in_danger):
        """Метапознание: заметить залипание и сменить подход, а не упорствовать.

        Это перебивает работу: если я долблю одно и то же или перестал понимать,
        продолжать бессмысленно. «Поумнеть» важнее, чем «доработать».
        """
        if self.meta.stuck() and self.step % 3 == 0:
            strategy = self.meta.pick_strategy()
            if strategy == 'ask_papa':
                q = self.language.ask(confused=True)
                self._say(q)
                self.meta.insight('я не понимаю — спрошу папу')
                return True
            if strategy == 'switch_task':
                self.cognition.last_plan = None
                self.wm.plan_step = None
                self.wm.hold('feeling', 'сменю занятие', salience=1.0)
                self.meta.insight('залип — сменю занятие')
                return True
            if strategy == 'reappraise':
                self.feelings.regulate('reappraisal', self.drives, self.neuromod)
                self.meta.insight('попробую иначе')
                return True
        return False

    def _regulate(self, state, in_danger):
        """Справиться с сильным чувством в свободную минуту.

        Пока есть дело (план, ремесло) — делаю его даже с тревогой на душе.
        Но когда заняться нечем, неприятное чувство нельзя оставлять: сначала
        утешение у папы, потом переосмысление, потом отвлечение.
        """
        f = self.feelings.current
        p = state.get('player')
        papa_near = bool(p and p.get('distance', 999) < 12)
        if in_danger:
            return False
        if not (f.name in ('страх', 'печаль', 'злость', 'обида', 'стыд', 'одиночество')
                and f.intensity > 0.55):
            return False
        # Успокаиваемся не каждый шаг: справиться с чувством — это процесс,
        # а не мгновенная команда. Иначе ребёнок «залипает» на утешении.
        if self.step - getattr(self, '_last_regulate_step', -99) < 8:
            return False
        self._last_regulate_step = self.step

        if papa_near and self.social.bond > 0.2:
            if self.feelings.regulate('comfort', self.drives, self.neuromod,
                                      attachment_near=True):
                # Подойти, только если ещё не рядом (иначе — просто утешение).
                if p.get('distance', 999) > 4 and self.catalog.has('come_close_to_player'):
                    self.cortex.act('come_close_to_player')
                elif self.catalog.has('look_at_player'):
                    self.cortex.act('look_at_player')
                else:
                    self.cortex.act('step_forward')
                self.wm.hold('feeling', 'папа утешил', salience=1.3)
                return True
        if f.name in ('страх', 'печаль') and self.meta.confidence > 0.4:
            if self.feelings.regulate('reappraisal', self.drives, self.neuromod):
                self.meta.insight(f"я успокоил себя: {f.name}")
                self.wm.hold('feeling', 'я справляюсь', salience=1.1)
                return True
        if self.feelings.regulate('distraction', self.drives, self.neuromod):
            self.wm.hold('feeling', 'отвлекаюсь', salience=1.0)
            return True
        return False

    def _play_and_habits(self, state, in_danger):
        """Живое поведение в свободную минуту: утешение, вопрос, игра, привычка.

        Это не перебивает дело — ребёнок этим занят, когда больше нечем.
        Возвращает True, если шаг сделан.
        """
        d = self.drives.to_dict()
        f = self.feelings.current

        # 0. УТЕШЕНИЕ. Сильное неприятное чувство без дела — сперва успокоиться.
        if self._regulate(state, in_danger):
            return True

        # 1. ВОПРОС. Ребёнок спрашивает «почему?» из любопытства и непонимания.
        if self.language.should_ask(d['curiosity'] * self.development.question_urge(),
                                    confusion=self.meta.confusion):
            q = self.language.ask()
            self._say(q)
            self.meta.ask(q)
            return True

        # 2. ИГРА. Когда сыт, в безопасности и в хорошем настроении — играет.
        if self.play.playing():
            nxt = self.play.next_step()
            if nxt and self.catalog.has(nxt):
                self.wm.hold('play', self.play.current_game['name'], salience=1.0)
                self.cortex.act(nxt)
                return True
            finished = self.play.finish(step=self.step)
            if finished:
                self.feelings.feel('радость', 0.6, f'поиграл: {finished}')
                self.neuromod.on_success()
            return False
        if (self.play.can_play(self.drives, self.feelings, in_danger, step=self.step)
                and random.random() < 0.35 * self.development.playfulness()
                * self.temperament.novelty_seeking()):
            name = self.play.imagine(self.self_model.inventory)
            print(f"🎲 Затея: {name}")
            self.episodic.remember(f"играю: {name}", 'play', feeling='радость',
                                   result='play', valence=0.7, importance=0.5)
            nxt = self.play.next_step()
            if nxt and self.catalog.has(nxt):
                self.cortex.act(nxt)
                return True

        # 3. ПРИВЫЧКА. В знакомой ситуации — знакомое действие (на автомате).
        cue = self.habits.cue_of(self.drives, state)
        self._habit_cue = cue
        if not in_danger and f.intensity < 0.6:
            habit = self.habits.suggest(cue)
            if habit and self.catalog.has(habit) and random.random() < 0.35:
                self.cortex.act(habit)
                return True

        return False

    # ============ АВТОНОМНОЕ ПОВЕДЕНИЕ ============

    def _autonomous_step(self, state):
        p = state.get('player')
        if p and p.get('name'):
            self.memory.player_positions[p['name']] = (p['x'], p['z'])
            self.self_model.set_creator(p['name'])

        # Паника: долго стою при высоком напряжении
        cur_pos = (state['x'], state['z'])
        if self.last_recorded_pos:
            dx = cur_pos[0] - self.last_recorded_pos[0]
            dz = cur_pos[1] - self.last_recorded_pos[1]
            if dx * dx + dz * dz > 1.0:
                self.last_pos_change_time = time.time()
        self.last_recorded_pos = cur_pos

        tension = self.drives.tension()
        still_for = time.time() - self.last_pos_change_time
        near_hostile = state.get('nearest_hostile')
        in_danger = bool(near_hostile and near_hostile.get('distance', 999) < 8)

        # Паника только если мы ПЫТАЛИСЬ двигаться и не смогли. Стоять
        # неподвижно во время боя, копки, еды или сна — это нормально,
        # и пробивать себе выход тогда не нужно.
        tried_to_move = self.cortex.last_action in self.MOVEMENT_ACTIONS
        if (tension > 3.0 and still_for > 25 and tried_to_move
                and not self.panic_mode):
            print(f"🚨 ПАНИКА! Стою {still_for:.0f} сек при напряжении {tension:.2f}")
            self.panic_mode = True
            self.panic_until = time.time() + 20

        if self.panic_mode:
            if time.time() > self.panic_until:
                self.panic_mode = False
                self.last_pos_change_time = time.time()
                print("✅ Паника прошла")
            else:
                if self.step % 5 == 0:
                    print("🚨 FORCE BREAK OUT!")
                self.cortex.act('force_break_out')
                return True

        # 0. Застрял в яме (по данным тела) — выбираемся, не давая себя закопать
        if state.get('in_pit'):
            self.self_dig_guard = 12
            now = time.time()
            if now - self.last_escape_time > 3:
                print("🕳️  Я в яме — выбираюсь")
                self.last_escape_time = now
            self.cortex.act('escape_pit')
            return True

        # 0b. Стою в плохой клетке — надо уйти из неё, а не топтаться на месте.
        # Плохая = чёрный список (застревание) или известная опасность (боль).
        cell = self.cell_of(state)
        if self.memory.is_blacklisted(cell) or self.memory.is_dangerous(cell):
            self.self_dig_guard = 12
            if p and p.get('distance', 999) < 40:
                self.cortex.act('go_to_player')
            else:
                self.cortex.act('step_forward')
            return True

        # 0b-bis. МЛАДЕНЧЕСКИЙ РЕФЛЕКС: очень голоден/одинок — зову папу.
        if self._infant_reflex(state):
            return True

        # 0c. МЕТАПОЗНАНИЕ важнее любого дела: если залип или перестал
        # понимать — сперва сменю подход, а не буду упорствовать.
        if self._meta_step(state, in_danger=in_danger):
            return True

        # 1. Есть план?
        if self.cognition.last_plan:
            self._execute_plan()
            return True

        # 2. Ремесло: учусь делать вещи шаг за шагом (дерево → доски → палки →
        # верстак → кирка → камень → ...). Это «умнеть», а не просто бегать.
        # Учусь, когда сыт, не в сильной боли и рядом нет угрозы: страх ночи
        # или лёгкая скука учёбе не мешают, а вот драка и голод — мешают.
        near = state.get('nearest_hostile')
        in_danger = bool(near and near.get('distance', 999) < 8)
        d_now = self.drives.to_dict()
        can_learn = (not self.cognition.last_plan and not in_danger
                     and d_now['hunger'] < 0.65 and self.drives.pain < 0.6)
        if can_learn:
            self.self_model.refresh()
            # Сначала — задача, которую ставит игра: так существо может пройти
            # игру самостоятельно, а не только свою учебную программу.
            task_goal = self._game_task_goal(state)
            step = self.crafting.tick(self.self_model.inventory, goal_override=task_goal)
            if step:
                self.wm.plan_step = f"ремесло: {step['action']} {step.get('params', {})}"
                # Инвентарь изменился — читаем сразу, иначе следующий шаг
                # программы будет считать по устаревшим данным.
                self.self_model.refresh(force=True)
                if step.get('ok') and step['action'] == 'craft':
                    self.neuromod.on_success()
                    self.episodic.remember(
                        f"я сделал {step['params'].get('name')}", "craft",
                        feeling='гордость', result='ok', valence=0.6, importance=0.6)
                return True

        # 2b. Любопытный опыт: проверить неизвестный закон мира (безопасно).
        # Это то, что делает существо исследователем, а не исполнителем.
        if can_learn:
            feats = extract_features(state, self.self_model.__dict__)
            probe = self.experimenter.maybe_probe(feats, time.time())
            if probe:
                action, params, law, why = probe
                if self.catalog.has(action):
                    print(f"🔬 Опыт: {why} (проверяю закон '{law}')")
                    self._pending_law = law
                    self.cortex.act(action, params=params)
                    return True

        # 3. Планирование (мысленная симуляция) при напряжении
        if tension > 1.8:
            plan = self.cognition.plan_if_needed(self.drives, state, self.predictor)
            if plan:
                print(f"📋 Новый план: {[s['action'] for s in plan]}")
                self._execute_plan()
                return True

        # 3. ПРЕДВИДЕНИЕ: позаботиться о нужде ЗАРАНЕЕ (пока она невелика).
        # Это то, что отличает существо с воображением от реактивного робота.
        ahead = self.mind.think_ahead(state)
        if ahead:
            action, why = ahead
            print(f"🔮 Предвижу: {why} → {action}")
            self.wm.hold('intention', why, salience=1.1)
            self.cortex.act(action)
            return True

        # 3b. Спонтанные желания
        goal_tuple = self.autonomy.generate_goal(self.drives, self.neuromod, state, self.self_model)
        if goal_tuple:
            name, action, params = goal_tuple
            print(f"🌱 Своё желание: {name} → {action}")
            self.cortex.act(action, params=params)
            return True

        # 3c. Живое поведение в свободную минуту: утешение, вопрос, игра.
        # Это не перебивает дело — этим существо занято, когда больше нечем.
        if self._play_and_habits(state, in_danger=in_danger):
            return True

        # 4. РЕШЕНИЕ: арбитраж двух систем — привычка (быстро) против
        # обдумывания (мысленная примерка + ценности). Как у человека.
        forbid = {'dig_down', 'dig_nearby'} if self.self_dig_guard > 0 else set()
        if self.self_dig_guard > 0:
            self.self_dig_guard -= 1
        habit_action = None
        cue = self.habits.cue_of(self.drives, state)
        if not in_danger and self.feelings.current.intensity < 0.6:
            habit_action = self.habits.suggest(cue)
        # Если папа и так вплотную — «подойти к папе» бессмысленно и залипает.
        p = state.get('player')
        avoid = set()
        if p and p.get('distance', 999) < 4:
            avoid = {'come_close_to_player', 'go_to_player'}
        action, source, conflict = self.mind.decide(
            state, in_danger, habit_action=habit_action, avoid=avoid)
        if action in avoid:
            action = self.cortex.choose_action(state, avoid=avoid)
            source = 'deliberate'
        if action in forbid:
            action = self.cortex.choose_action(state, forbid=forbid, avoid=avoid)
            source = 'deliberate'
        if self.step % 5 == 0:
            dominant = self.drives.dominant()
            print(f"🧠 Напряжение {tension:.2f} (главное: {dominant}) "
                  f"→ {action} [{source}]")
        self.cortex.act(action)
        return True

    # ============ СОН И КОНСОЛИДАЦИЯ ============

    def _maybe_sleep(self, state):
        """Сон: консолидация опыта (гиппокампальный повтор) и очистка памяти."""
        d = self.drives.to_dict()
        night = state.get('is_night', False)
        # Сон измеряется ШАГАМИ, а не настенным временем: существо живёт
        # шагами. Иначе при быстром цикле оно «спит вечно» (часы не идут).
        if self.sleeping:
            self._sleep_steps_left -= 1
            if self._sleep_steps_left > 0:
                self.cortex.act('nap' if self.catalog.has('nap') else 'wait_1sec')
                return True
            self.sleeping = False
            return False
        if d['fatigue'] > 0.85 or (night and d['fatigue'] > 0.65):
            print("😴 Засыпаю...")
            self.sleeping = True
            self._sleep_steps_left = 8
            self.drives.meet_sleep(0.6)
            self._consolidate()
            return True
        return False

    def _consolidate(self):
        try:
            self.predictor.consolidate()
        except Exception as e:
            print(f"⚠️  Консолидация предсказаний: {e}")
        forgotten = self.episodic.consolidate()
        if forgotten:
            print(f"🧹 Забыл {forgotten} слабых эпизодов")
        self.self_model.save()
        self.cognition.save()
        self.memory.save()
        self.concepts.save()
        self.causes.save()
        # Человеческие системы тоже сохраняются во сне.
        self.feelings.save()
        self.social.save()
        self.habits.save()
        self.meta.save()
        self.language.save()
        self.development.save()
        self.temperament.save()
        self.play.save()
        # Сцепка человеческих систем тоже сохраняется во сне.
        self.mind.values.save()
        self.mind.identity.save()
        # Субъективный приор — ожидания мира переживают перезапуск.
        self.prior.save()

    # ============ ЧУВСТВА (человеческое ядро) ============

    def _feel(self, state, is_new):
        """Прожить шаг как живое существо: тело → чувство → настроение.

        Порядок как у человека: сперва телесное ощущение (интероцепция),
        затем оценка происходящего (appraisal) рождает эмоцию, а эмоция
        складывается в медленное настроение. Это окрашивает всё решение.
        """
        # 1. Телесное ощущение себя.
        body = {'in_water': state.get('in_water'), 'in_lava': state.get('in_lava'),
                'on_fire': state.get('on_fire')}
        self.intero.sense(state, self.drives, body)

        # 2. Чувство рождается из СОБЫТИЯ, а не из каждого тика. Фон (голод,
        # тревога) — это настроение; а вспышка чувства бывает, когда что-то
        # ПРОИЗОШЛО: пришёл папа, стало ново, впервые заметил боль или угрозу.
        p = state.get('player')
        near = bool(p and p.get('distance', 999) < 8)
        if near and not self.social.greeted_this_reunion:
            joy = self.social.on_reunion()
            self.feelings.feel('радость', joy, 'папа вернулся')
            self.social.greeted_this_reunion = True
            # Близость папы снимает одиночество и наполняет теплом.
            self.drives.meet('loneliness', 0.35)
        elif not near:
            self.social.greeted_this_reunion = False

        # 2b. ОЦЕНКА (appraisal) — сердце человеческого чувства. Мозг оценивает
        # смысл шага и разворачивает оценку обратно в тело и химию: событие
        # меняет и чувство, и сам организм (замкнутая петля).
        appraisal = self.mind.feel(state, is_new, in_danger=False)
        emo = self.feelings.appraise(appraisal.to_dict())
        if emo and emo.intensity > self.feelings.current.intensity + 0.03:
            self.feelings.feel(emo.name, emo.intensity, emo.cause)
        if is_new:
            self.mind.note_novelty(self.step)

        # Порог перехода: впервые замечаю боль/страх/голод/одиночество/усталость.
        self._notice_feeling()

        # 3. Настроение течёт во времени (медленный фон).
        self.feelings.tick(self.drives, self.intero, self.neuromod)

        # 4. Привязанность и разлука — отдельное, социальное чувство.
        distress = self.social.update(state)
        if (self.social.needs_contact() and random.random() < 0.3
                and min(0.9, 0.4 + distress) > self.feelings.current.intensity):
            self.feelings.feel('одиночество', min(0.9, 0.4 + distress), 'папы давно нет')

        # 5. Возраст: существо взрослеет от прожитого.
        self.development.live(steps=1.0)

        return self.feelings.current

    def _satisfy_from_world(self, state):
        """Тело и мир удовлетворяют нужды — снять драйвы по факту.

        Как у живого: поел — голод падает; поспал — усталость; обнял папу —
        одиночество. Без этого существо «чувствует голод вечно» и выглядит
        роботом с вечным датчиком. Опираемся на РЕАЛЬНЫЕ сигналы тела
        (food, energy/сон), а не на «само пройдёт».
        """
        food = state.get('food')
        if food is not None:
            # Сытость тела прямо снимает давление голода (поел — наелся).
            satiety = clip01((food - 10) / 10.0)   # 0 при food<=10, 1 при food>=20
            if satiety > 0:
                self.drives.meet('hunger', 0.15 * satiety)

        # Сон: если тело сообщает запас сил (energy) — усталость падает.
        energy = state.get('energy')
        if energy is not None:
            rested = clip01((energy - 10) / 10.0)
            if rested > 0:
                self.drives.meet('fatigue', 0.06 * rested)

        # Папа вплотную — одиночество тает (объятие).
        p = state.get('player')
        if p and p.get('distance', 999) < 4:
            self.drives.meet('loneliness', 0.12)
            self.neuromod.oxytocin = clip01(self.neuromod.oxytocin + 0.05)

    def _notice_feeling(self):
        """Почувствовать, когда состояние ПЕРЕШЛО порог (а не пока оно длится).

        Так чувство вспыхивает один раз на событие: впервые стало больно, впервые
        сильно голоден, впервые одиноко. Пока состояние длится, оно живёт в
        настроении и телесном тоне, а не кричит чувством каждый шаг.
        """
        d = self.drives.to_dict()
        checks = [
            ('боль', d['pain'] > 0.55, 0.9, 'мне больно'),
            ('страх', d['fear'] > 0.6, 0.8, 'мне страшно'),
            ('голод', d['hunger'] > 0.75, 0.6, 'я очень голоден'),
            ('одиночество', d['loneliness'] > 0.7, 0.5, 'мне одиноко'),
            ('усталость', d['fatigue'] > 0.8, 0.5, 'я очень устал'),
        ]
        for name, active, intensity, cause in checks:
            if active and name not in self._felt_states:
                self._felt_states.add(name)
                self.feelings.feel(name, intensity, cause)
            elif not active:
                self._felt_states.discard(name)

    # ============ СТУПОР ============

    MOVEMENT_ACTIONS = {
        'step_forward', 'step_back', 'step_left', 'step_right',
        'jump_forward', 'sprint_short', 'go_to_player',
        'walk_away_from_player', 'come_close_to_player',
        'find_and_attack', 'flee_from_hostile', 'attack_hostile',
        'go_to_position', 'dig_forward', 'dig_tree', 'escape_pit',
        'force_break_out',
    }

    def check_stuck(self, state):
        """Застревание = пытались двигаться, но не сдвинулись.

        Копание/осмотр/ожидание позицию не меняют — это не застревание.
        """
        p = state.get('player')
        if p and p['distance'] < 5:
            self.stuck_steps = 0
            self.last_positions = []
            return False
        self.last_positions.append((state['x'], state['z']))
        if len(self.last_positions) > 20:
            self.last_positions.pop(0)
        if len(self.last_positions) < 20:
            return False
        tried_to_move = self.cortex.last_action in self.MOVEMENT_ACTIONS
        xs = [q[0] for q in self.last_positions]
        zs = [q[1] for q in self.last_positions]
        spread = (max(xs) - min(xs)) + (max(zs) - min(zs))
        if tried_to_move and spread < 1.5:
            self.stuck_steps += 1
        else:
            self.stuck_steps = 0
        return self.stuck_steps > 12

    # ============ ГЛАВНЫЙ ЦИКЛ ============

    def think(self, state):
        self.step += 1
        self.memory.total_steps += 1
        self.neuromod.tick()

        if self.step % 5 == 0:
            self.self_model.refresh()
            self.world_model.refresh()
            # Развитие отмечается по факту: что бы существо ни делало,
            # достигнутая ступень (дерево, доски, кирка) засчитывается.
            self.curriculum.observe(self.self_model.inventory)

        if self.step % 10 == 0:
            try:
                vision = self.adapter.get_vision()
                sounds = self.adapter.get_sounds()
                self.cognition.observe_world(vision, sounds)
            except Exception:
                pass

        cell = self.cell_of(state)
        is_new = self.memory.add_cell(cell)
        self.drives.tick(state, is_new)
        # Тело/мир реально удовлетворяет нужды (поел, поспал, папа утешил) —
        # это ЗАМЫКАЕТ цикл «чувство → поступок → облегчение».
        self._satisfy_from_world(state)
        delta = self.cortex.observe()
        # Распределённый мозг: прожить такт и «разогреться» текущей ситуацией
        # ДО выбора действия. Награда/исход — глобальный сигнал (IBL 2025).
        self.cortex.tick_regions(self._region_features(state),
                                 reward=self._last_reward(delta))
        # Понятия о мире: сравнить «было → стало» после прошлого действия.
        self._observe_concepts(state)
        # Чувства: тело → эмоция → настроение. Окрашивает всё решение.
        self._feel(state, is_new)
        self._check_messages(state)

        p = state.get('player')
        if p and p.get('name'):
            self.memory.player_positions[p['name']] = (p['x'], p['z'])
            self.self_model.set_creator(p['name'])
            self.neuromod.on_creator_near(p['distance'])

        # Боль
        if state.get('recent_damage') and state.get('damage_time') != self.last_damage_time:
            self.last_damage_time = state.get('damage_time', 0)
            self.memory.mark_danger(cell)
            self.neuromod.on_danger()
            self.neuromod.on_pain()
            self.feelings.feel('боль', 0.9, 'мне сделали больно')
            self.feelings.feel('страх', 0.7, 'чуть не погиб')
            self.episodic.remember("мне было больно", "получил урон",
                                   feeling='боль', result='danger',
                                   valence=-0.8, importance=1.0)
            print("⚠️  Боль!")

        if is_new:
            self.neuromod.on_novelty()
            self.self_model.add_narrative("нашёл новое место")

        # Ступор
        stuck_now = self.check_stuck(state)
        if stuck_now and self.escape_mode == 0:
            self.escape_mode = 20
            self.stuck_steps = 0
            self.memory.stuck_count[cell] += 1
            if self.memory.stuck_count[cell] >= 2:
                self.memory.blacklist(cell)
            print(f"⚠️  Застрял (раз: {self.memory.stuck_count[cell]})")

        if self.escape_mode > 0:
            self.escape_mode -= 1
            self.self_dig_guard = 12
            # Если мы реально в яме — выбираемся; если нет, пробиваем выход.
            # (escape_pit вне ямы — пустышка, поэтому раньше существо «стояло».)
            if state.get('in_pit'):
                self.cortex.act('escape_pit')
            else:
                self.cortex.act('force_break_out')
            return 'escape'

        # Эмоция из состояния тела
        self.neuromod.update_emotion(self.drives)

        # ВНИМАНИЕ: конкуренция сигналов → фокус
        focus = self._compete_for_attention(state, is_new)

        # РАБОЧАЯ ПАМЯТЬ: удерживаем важное
        if focus:
            self.wm.hold('focus', focus.content, salience=1.5)
        self.wm.hold('emotion', self.neuromod.emotion, salience=1.0)
        if self.goals.current:
            self.wm.set_goal(self.goals.current.description[:40])
        if self.cortex.pending_action:
            self.wm.hold('doing', self.cortex.pending_action, salience=0.8)

        # ВНУТРЕННЯЯ РЕЧЬ (с учётом внимания, рабочей памяти, эмоции, автобиографии)
        drives_dict = self.drives.to_dict()
        last_event = f"делал {self.cortex.pending_action}" if self.cortex.pending_action else ""
        feeling_str = f"{self.feelings.current.name} ({self.feelings.current.cause})"
        thought = self.cognition.think_if_time(
            drives_dict, last_event, self.neuromod.mood(),
            self.goals.current.action if self.goals.current else None,
            attention=self.workspace.focus_text(),
            working_memory=str(self.wm.contents()),
            emotion=feeling_str,
            self_narrative=self.self_model.narrative_summary(),
            body=self.intero.describe(),
        )
        if thought:
            print(f"💭 {thought}")
            self.wm.self_talk = thought
            if random.random() < 0.3:
                self.adapter.say(thought)

        # РАЗМЫШЛЕНИЕ о причинах: почему не выходит и как иначе.
        self._reflect_on_causes(state)

        # Периодическая консолидация (как во сне)
        if self.step % 300 == 0:
            self._consolidate()

        # СОН при сильной усталости
        if self._maybe_sleep(state):
            return 'sleep'

        # ДЕЙСТВИЕ
        if self.goals.current:
            self._execute_goal_step()
            return 'goal_step'

        self._autonomous_step(state)
        return 'autonomous'

    def _check_messages(self, state):
        msgs = self.adapter.get_messages()
        if not msgs:
            return
        last = msgs[-1]
        if (time.time() * 1000 - last['time']) > 30000:
            self.adapter.clear_messages()
            return
        if last['time'] <= self.last_user_msg_time:
            return
        self.last_user_msg_time = last['time']
        print(f"📨 {last['name']}: {last['text']}")
        self.respond_to_message(last, state)
        self.adapter.clear_messages()
