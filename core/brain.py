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
from core.cognition import Cognition
from core.global_workspace import GlobalWorkspace
from core.working_memory import WorkingMemory
from core.episodic_memory import EpisodicMemory
from core.voice import Voice, VOICE_ENABLED

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"
CONVERSATION_FILE = "data/conversation.json"
CELL_SIZE = 5

CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]')
TEMPLATE_PATTERN = re.compile(r'<[^>]{0,50}>')


def has_cjk(t):
    return bool(CJK_PATTERN.search(t))


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
        self.crafting = CraftingSkill(self.recipes, self.curriculum, self.cortex.act,
                                      task_failure_cb=self.tasks.note_failure)
        # Понятия о мире подсказывают выбор действия (что ценно, что запрещено).
        self.cortex.advisor = self.concepts.advice
        self._last_features = None
        self._pending_law = None

        # Новая «человеческая» надстройка
        self.workspace = GlobalWorkspace()
        self.wm = WorkingMemory()
        self.episodic = EpisodicMemory()

        self.adaptive = AdaptiveIntent(self.catalog)
        self.intent = IntentResolver(self.adaptive, self.catalog)
        self.voice = Voice(enabled=VOICE_ENABLED)

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
        d = self.drives.to_dict()
        context = self.conversation[-6:]
        ctx_str = '\n'.join([f"{c['who']}: {c['text']}" for c in context])
        mood = self.neuromod.mood()
        symbolic = self.cognition.symbolic.summary_for_prompt(5)
        last_thought = self.cognition.voice.last()

        prompt = f"""Ты — цифровой ребёнок 3-5 лет. Отец — {sender}. Зовёшь "папа".
Отвечай ТОЛЬКО на русском. ОДНОЙ короткой фразой (до 12 слов).
Не используй шаблоны и угловые скобки.

Твои чувства: страх {d['fear']}, боль {d['pain']}, голод {d['hunger']}, одиноко {d['loneliness']}, устал {d['fatigue']}.
Эмоция: {self.neuromod.emotion}
Настроение: {mood}
Что знаю о мире: {symbolic}
О чём думал недавно: {last_thought or 'ни о чём'}

Реплики:
{ctx_str}

Папа: "{text}"

Ответь одной фразой."""
        return self._call_llm_text(prompt)

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
        # собственная мысль
        last_thought = self.cognition.voice.last()
        if last_thought:
            self.workspace.submit('thought', last_thought, 0.5)

        return self.workspace.compete(self.neuromod)

    # ============ ПОНЯТИЯ (законы мира) ============

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
            if self._pending_law:
                self.experimenter.observe(
                    self._pending_law, self.concepts.confidence(self._pending_law) > 0.5)
                self._pending_law = None
        self._last_features = after

    # ============ ЗАДАЧИ ИГРЫ ============

    def _game_task_goal(self, state):
        """Взять у игры задачу и превратить её в цель для ремесла."""
        self.tasks.poll(self.adapter, self.self_model.inventory)
        return self.tasks.next_goal(self.self_model.inventory)

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

        # 3. Спонтанные желания
        goal_tuple = self.autonomy.generate_goal(self.drives, self.neuromod, state, self.self_model)
        if goal_tuple:
            name, action, params = goal_tuple
            print(f"🌱 Своё желание: {name} → {action}")
            self.cortex.act(action, params=params)
            return True

        # 4. Обычный выбор (мысленная примерка + уверенность)
        # Запрещаем копать под собой, пока не убедились, что мы не в яме.
        forbid = {'dig_down', 'dig_nearby'} if self.self_dig_guard > 0 else set()
        if self.self_dig_guard > 0:
            self.self_dig_guard -= 1
        action = self.cortex.choose_action(state, forbid=forbid)
        if self.step % 5 == 0:
            dominant = self.drives.dominant()
            print(f"🧠 Напряжение {tension:.2f} (главное: {dominant}) → {action}")
        self.cortex.act(action)
        return True

    # ============ СОН И КОНСОЛИДАЦИЯ ============

    def _maybe_sleep(self, state):
        """Сон: консолидация опыта (гиппокампальный повтор) и очистка памяти."""
        d = self.drives.to_dict()
        night = state.get('is_night', False)
        if self.sleeping:
            if time.time() < self.sleep_until:
                self.cortex.act('wait_1sec')
                return True
            self.sleeping = False
            return False
        if d['fatigue'] > 0.85 or (night and d['fatigue'] > 0.65):
            print("😴 Засыпаю...")
            self.sleeping = True
            self.sleep_until = time.time() + 8
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
        self.cortex.observe()
        # Понятия о мире: сравнить «было → стало» после прошлого действия.
        self._observe_concepts(state)
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
        thought = self.cognition.think_if_time(
            drives_dict, last_event, self.neuromod.mood(),
            self.goals.current.action if self.goals.current else None,
            attention=self.workspace.focus_text(),
            working_memory=str(self.wm.contents()),
            emotion=self.neuromod.emotion,
            self_narrative=self.self_model.narrative_summary(),
        )
        if thought:
            print(f"💭 {thought}")
            self.wm.self_talk = thought
            if random.random() < 0.3:
                self.adapter.say(thought)

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
