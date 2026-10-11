"""
Mind — человеческое ядро в действии: как чувство, воображение и ценности
вместе рождают поступок.

Отдельные системы (характер, тело, чувство, привязанность, игра, привычки,
метапознание, язык, рост) уже есть. Но живым существо делает не наличие
деталей, а их СЦЕПКА: тело рождает чувство, чувство окрашивает оценку,
оценка двигает тело и химию, воображение заглядывает вперёд, ценности
взвешивают варианты, привычка и обдумывание спорят, поступок меняет ценности
и историю о себе. Mind — это и есть сцепка.

Полный человеческий такт:

  1. ОЦЕНКА. Что значит происходящее для моих нужд? → чувство + сдвиг тела.
  2. ПРЕДВИДЕНИЕ. Что будет, если не позаботиться? → намерение заранее.
  3. ВООБРАЖЕНИЕ. Если надо — мысленно пройти путь к цели (план).
  4. РЕШЕНИЕ. Привычка (быстро) против обдумывания (медленно) → арбитраж,
     сигнал конфликта, взвешивание ценностями.
  5. ПОСТУПОК. Действие уходит телу.
  6. ОБУЧЕНИЕ. Подкрепление меняет ценности, привычки и историю о себе;
     поступок против себя рождает диссонанс (совесть).

Так поведение перестаёт быть «if-else» и становится личным.
"""
import random
import time

from core.appraisal import Appraiser
from core.imagination import Imagination
from core.values import Values, context_key
from core.identity import Identity
from core.temperament import clip


class Mind:
    def __init__(self, brain):
        self.brain = brain
        # Оценщик, воображение, ценности, «Я».
        self.appraiser = Appraiser(brain.temperament)
        self.imagination = Imagination(
            predictor=brain.predictor, causality=brain.causes, catalog=brain.catalog)
        self.values = Values(brain.temperament)
        self.identity = Identity(brain.temperament)
        self.last_source = None        # 'habit' | 'deliberate' | 'conflict'
        self.last_conflict = 0.0
        self.last_intention = None     # о чём позаботился заранее
        self.last_plan = None
        self.deliberations = 0
        self.habit_wins = 0
        self.last_reward = 0.0

    # ============ 1. ОЦЕНКА ============

    def feel(self, state, is_new, in_danger):
        """
        Оценить шаг и развернуть оценку в тело и химию.

        Возвращает оценку (Appraisal). Чувство рождается из СМЫСЛА события,
        а не из «стимул → реакция», и меняет сам организм.
        """
        b = self.brain
        p = state.get('player')
        near = bool(p and p.get('distance', 999) < 8)
        # «Свой человек рядом» — это польза и привязанность (если он близко).
        benefit = 0.0
        if near:
            benefit = 0.4
        # Норма: если взрослый запретил (scolded) — я поступил против правил.
        norm = 0.0
        scolded = getattr(b.adapter, 'scolded', None)
        if scolded is not None and getattr(b, '_last_scold_seen', 0) != scolded:
            b._last_scold_seen = scolded
            norm = 0.7
            b.feelings.feel('вина', 0.7, 'папа сказал нельзя')
            self.identity.add_to_story('папа сказал «нельзя» — так не надо')

        appraisal = self.appraiser.build(
            b.drives, b.intero, is_new=is_new, danger=in_danger,
            harm=(0.0 if not in_danger else 0.7),
            benefit=benefit, attachment=near, self_agency=True, norm=norm)
        # Развернуть оценку в тело и химию (замкнутая петля).
        self.appraiser.apply_to_body(appraisal, b.drives, b.intero, b.neuromod)
        return appraisal

    # ============ 2. ПРЕДВИДЕНИЕ ============

    def think_ahead(self, state):
        """
        Заглянуть в будущее: не станет ли скоро плохо?

        Возвращает (action, why) — упреждающее намерение, или None. Это
        предусмотрительность: позаботиться о нужде, пока она ещё невелика.
        """
        b = self.brain
        need = self.imagination.anticipate(b.drives, state, b.step)
        if not need:
            return None
        # Чего хочется сделать заранее — по нужде. Первое доступное действие
        # из подходящих (в доме — попросить еды, в Minecraft — поесть).
        urges = {
            'hunger': ([('ask_food', 'скоро проголодаюсь — попрошу еды'),
                        ('eat_food', 'скоро проголодаюсь — поем заранее'),
                        ('find_and_attack', 'скоро проголодаюсь — добуду еды')]),
            'loneliness': [('go_to_player', 'скоро станет одиноко — пойду к папе')],
            'fatigue': ([('nap', 'скоро устану — отдохну'),
                         ('build_shelter', 'скоро устану — укроюсь и отдохну')]),
            'boredom': ([('play', 'скучно — чем-нибудь займусь'),
                         ('step_forward', 'скучно — пойду поищу новое'),
                         ('dig_nearby', 'скучно — покопаюсь')]),
        }.get(need)
        if not urges:
            return None
        for action, why in urges:
            if b.catalog.has(action):
                self.last_intention = (need, action, b.step)
                return action, why
        return None

    # ============ 3. ВООБРАЖЕНИЕ ============

    def imagine_plan(self, state, goal_drive):
        """Мысленно пройти путь к цели — вернуть список действий или None."""
        desc, plan = self.imagination.imagine_goal(self.brain.drives, state, goal_drive)
        if plan:
            self.last_plan = plan
            self.deliberations += 1
        return plan

    # ============ 4. РЕШЕНИЕ (арбитраж двух систем) ============

    def decide(self, state, in_danger, habit_action=None, avoid=None):
        """
        Выбрать поступок: привычка или обдумывание, взвесив ценности.

        Возвращает (action, source, conflict). Мозг затем выполняет действие.
        avoid — действия, бессмысленные сейчас (например, «подойти», когда
        папа и так рядом).
        """
        b = self.brain
        context = context_key(b.drives, state)
        avoid = avoid or set()

        # СИСТЕМА 1: привычка (или сильнейшая выученная ценность).
        if habit_action is None:
            cue = b.habits.cue_of(b.drives, state)
            habit_action = b.habits.suggest(cue)
        known = self.values.best_known(context)
        if habit_action is None and known and b.catalog.has(known):
            habit_action = known
        if habit_action in avoid:
            habit_action = None

        # СИСТЕМА 2: обдуманный выбор (мысленная примерка + чувство).
        deliberate = b.cortex.choose_action(state, avoid=avoid)

        confidence = b.self_model.confidence(deliberate)
        novel = b.step - getattr(b, '_last_novel_step', b.step) < 5

        action, source, conflict = self.values.arbitrate(
            habit_action, deliberate, confidence, b.drives.tension(),
            novel=novel, danger=in_danger)

        self.last_source = source
        self.last_conflict = conflict
        if source == 'habit':
            self.habit_wins += 1
        else:
            self.deliberations += 1

        # КОНФЛИКТ двух систем: замешательство, пауза, внимание.
        if conflict > 0.6:
            b.workspace.submit('conflict', 'привычка и ум спорят — что делать?',
                               conflict * 1.5)
            if random.random() < 0.25:
                b.meta.insight('во мне спорят привычка и разум')

        # Взвесить ценностями: если действие служит сильной ценности — бонус.
        if b.catalog.has(action):
            action = self._apply_values(action, state)
        return action, source, conflict

    def _apply_values(self, action, state):
        """Ценности смещают выбор к тому, что для существа важно (не приказ)."""
        b = self.brain
        # Если действие согласуется с сильной ценностью и есть альтернатива —
        # иногда предпочесть значимое (забота о папе, познание).
        near = (state.get('player') or {}).get('distance', 999) < 12
        if near and self.identity.value_weight('связь') > 0.7:
            if action in ('step_forward', 'look_around') and b.catalog.has('look_at_player'):
                if random.random() < 0.3:
                    return 'look_at_player'
        return action

    # ============ 5-6. ПОСТУПОК И ОБУЧЕНИЕ ============

    def after_action(self, action, ok, state):
        """
        Поступок совершён — учиться: ценности, привычки, история о себе.

        Здесь замыкается петля: подкрепление меняет то, что существо ценит;
        поступок против себя рождает диссонанс (совесть); удача крепит историю.
        """
        b = self.brain
        context = context_key(b.drives, state)
        reward = 0.7 if ok else -0.3
        # Учитываем, стало ли реально легче (облегчение нужды).
        self.values.update(context, action, reward)

        # Согласованность с собой: поступил ли против того, кем себя считаю?
        clash = self.identity.check_consistency(action, b.drives)
        if clash > 0:
            b.feelings.feel('вина' if clash > 0.45 else 'стыд', clash,
                            'поступил не так, как хочу')
            self.identity.add_to_story('я поступил не так, как хочу, — исправлюсь')
        # Помириться с собой, когда сделал доброе дело.
        if action in ('help', 'gather', 'talk') and ok:
            self.identity.soothe()
            self.identity.grow_value('польза', 0.02)
        if action in ('play', 'jump_once', 'spin_around') and ok:
            self.identity.grow_value('игра', 0.01)
            b.feelings.feel('радость', 0.5, 'поиграл')
        if ok and action in ('ask_food', 'go_to_player', 'come_close_to_player'):
            self.identity.grow_value('связь', 0.01)

        self.last_reward = reward

    def note_novelty(self, step):
        self.brain._last_novel_step = step

    def summary(self):
        return (f"ум: решений-обдумываний {self.deliberations}, "
                f"привычка победила {self.habit_wins} раз, "
                f"конфликт {self.last_conflict:.2f} | "
                f"{self.values.summary()} | {self.identity.summary()}")
