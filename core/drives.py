"""
Drives — система потребностей, как у живого существа.

Драйвы — это внутренние «давления», которые заставляют действовать.
Чем сильнее неудовлетворённый драйв, тем выше напряжение и тем вероятнее
действие, которое его снизит (гомеостаз).

Потребности:
  * hunger    — голод (из реальной еды)
  * fear      — страх (угроза, ночь, боль)
  * pain      — боль (телесный сигнал, не гаснет сразу)
  * loneliness— одиночество (привязанность к значимому другому)
  * fatigue   — усталость (циркадный ритм + активность)
  * boredom   — скука (нужна новизна)
  * curiosity — любопытство (тяга исследовать неизвестное)
  * comfort   — комфорт (производная: безопасность + сытость; снижает напряжение)

Ключевое отличие от «ползунков»: когда тело реально удовлетворяет нужду
(поел, поспал, обнял папу), драйв ПАДАЕТ — иначе цикл «чувство → действие →
облегчение» не замкнут, и существо чувствует голод вечно. Пока нужда не
удовлетворена, она медленно РАСТЁТ (давление копится). Еда/сон/близость
приходят из внешнего мира (тела), а не «сами собой».

tension() — интегральный «дискомфорт», который запускает поведение.
"""


def clip(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


class Drives:
    # Скорость, с которой нужда растёт, пока не удовлетворена.
    # Голод растёт медленно: человек не ест непрерывно — он ест, а потом
    # живёт (играет, учится, работает), пока снова не проголодается.
    GROWTH = {'hunger': 0.007, 'loneliness': 0.012, 'boredom': 0.015}

    def __init__(self):
        self.hunger = 0.0
        self.fear = 0.0
        self.pain = 0.0
        self.boredom = 0.0
        self.loneliness = 0.0
        self.fatigue = 0.0
        self.curiosity = 0.4
        self.comfort = 0.5

        # Циркадный ритм
        self.circadian_phase = 0.0   # 0..1 (0=полночь, 0.5=полдень)
        self.awake_hours = 0.0       # сколько «бодрствует» (давление сна)
        self._last_damage_time = None

    # ============ ТЕЧЕНИЕ ВРЕМЕНИ ============

    def tick(self, state, is_new_cell, dt=1.0):
        # --- ГОЛОД: тело отдаёт реальную сытость (food), но нужда ещё и растёт ---
        real_food = state.get('food', 20)
        food_hunger = (20.0 - real_food) / 20.0
        # Давление копится само; реальная еда (food высок) его снимает.
        if food_hunger <= self.hunger:
            self.hunger = clip(self.hunger + self.GROWTH['hunger'] * dt)
        else:
            self.hunger = clip(food_hunger)

        # --- ЦИРКАДНЫЙ РИТМ ---
        tod = state.get('time_of_day', 0)
        self.circadian_phase = (tod % 24000) / 24000.0
        is_night = state.get('is_night', False)

        # --- УСТАЛОСТЬ: растёт со временем, быстрее ночью ---
        self.awake_hours += dt / 60.0
        fatigue_rate = 0.010 if not is_night else 0.022
        fatigue_rate += 0.004 * min(2.0, self.awake_hours / 10.0)
        self.fatigue = clip(self.fatigue + fatigue_rate * dt)

        # --- БОЛЬ: телесный сигнал, спадает медленно ---
        # Удар — это СОБЫТИЕ, а не «пока висит флаг». Иначе в быстром цикле
        # флаг «recent_damage» (по настенным часам) держится сотни шагов, боль
        # копится до 1.0 и не спадает — дурная петля «боль навсегда».
        hp = state.get('health', 20)
        dmg_time = state.get('damage_time')
        # Если адаптер даёт метку удара — считаем удар один раз (иначе флаг
        # «recent_damage» висит сотни шагов и боль копится вечно). Если метки
        # нет — доверяем флагу, как раньше.
        fresh_hit = state.get('recent_damage', False) and (
            dmg_time is None or dmg_time != self._last_damage_time)
        if fresh_hit:
            self._last_damage_time = dmg_time
            self.pain = clip(self.pain + 0.5)
            self.fear = clip(self.fear + 0.4)
        if hp < 10:
            self.pain = clip(self.pain + 0.03 * dt)
            self.fear = clip(self.fear + 0.04 * dt)
        self.pain = clip(self.pain - 0.02 * dt)  # естественное заживление

        # --- СТРАХ: угрозы. Страх тянется к «уровню опасности», а не копится
        # вечно: лёгкая тревога ночью, сильный страх вблизи врага. Это гасит
        # дурную петлю «страх 1.0 навсегда», из-за которой существо замирало.
        nearest = state.get('nearest_hostile')
        danger = 0.0
        if is_night:
            danger = max(danger, 0.25)
        if nearest:
            dd = nearest.get('distance', 999)
            if dd < 4:
                danger = 1.0
            elif dd < 10:
                danger = 0.6
            elif dd < 16:
                danger = 0.35
        if state.get('recent_damage', False):
            danger = max(danger, 0.7)
        # Подход к уровню опасности (быстро вверх, медленнее вниз — как у людей).
        rate = 0.35 if danger > self.fear else 0.06
        self.fear += (danger - self.fear) * rate * dt
        self.fear = clip(self.fear)

        # --- СКУКА: нужна новизна ---
        self.boredom = clip(self.boredom + 0.015 * dt)
        if is_new_cell:
            self.boredom = clip(self.boredom - 0.6)

        # --- ЛЮБОПЫТСТВО: тянет к новому; падает, когда новое найдено ---
        self.curiosity = clip(self.curiosity + 0.008 * dt)
        if is_new_cell:
            self.curiosity = clip(self.curiosity - 0.25)

        # --- ОДИНОЧЕСТВО: привязанность ---
        self.loneliness = clip(self.loneliness + self.GROWTH['loneliness'] * dt)
        p = state.get('player')
        if p and p.get('distance', 999) < 10:
            self.loneliness = clip(self.loneliness - 0.15)
        if p and p.get('distance', 999) < 5:
            self.loneliness = clip(self.loneliness - 0.35)

        # --- КОМФОРТ: безопасность + сытость + крыша ---
        safety = 1.0 - self.fear
        satiety = 1.0 - self.hunger
        shelter = 1.0 if not state.get('has_sky_above', True) else 0.7
        self.comfort = clip(0.45 * safety + 0.35 * satiety + 0.20 * shelter)

    # ============ ДЕЙСТВИЯ, МЕНЯЮЩИЕ ДРАЙВЫ ============

    def meet_sleep(self, amount=0.5):
        self.fatigue = clip(self.fatigue - amount)
        self.pain = clip(self.pain - 0.1)
        self.awake_hours = 0.0

    def meet(self, drive, amount):
        """Удовлетворить нужду телом: поел, поспал, обнял папу — стало легче.

        Именно это замыкает цикл «чувство → действие → облегчение». Без этого
        существо «чувствует голод вечно» — как робот с датчиком, а не как
        живое, которому реально становится лучше.
        """
        if hasattr(self, drive) and drive != 'comfort':
            setattr(self, drive, clip(getattr(self, drive) - amount))

    def relieve(self, drive, amount):
        self.meet(drive, amount)

    # ============ ИНТЕГРАЦИЯ ============

    def to_dict(self):
        return {
            'hunger': round(self.hunger, 2),
            'fear': round(self.fear, 2),
            'pain': round(self.pain, 2),
            'boredom': round(self.boredom, 2),
            'loneliness': round(self.loneliness, 2),
            'fatigue': round(self.fatigue, 2),
            'curiosity': round(self.curiosity, 2),
            'comfort': round(self.comfort, 2),
        }

    def tension(self):
        d = self.to_dict()
        weights = {
            'fear': 1.5, 'pain': 1.4, 'hunger': 1.2, 'loneliness': 1.0,
            'fatigue': 0.9, 'boredom': 0.7, 'curiosity': 0.5,
            'comfort': -1.0,
        }
        return sum(d[k] * weights[k] for k in d)

    def dominant(self):
        d = self.to_dict()
        needs = {k: v for k, v in d.items() if k != 'comfort'}
        return max(needs, key=needs.get)

    def summary(self):
        d = self.to_dict()
        return (f"голод {d['hunger']}, страх {d['fear']}, боль {d['pain']}, "
                f"скука {d['boredom']}, один {d['loneliness']}, устал {d['fatigue']}, "
                f"любопыт {d['curiosity']} | напряжение {self.tension():.2f}")

    def unmet(self):
        d = self.to_dict()
        return [k for k, v in d.items() if v > 0.4 and k != 'comfort']

    def mood_bias(self):
        """Вклад драйвов в настроение (-1..+1)."""
        d = self.to_dict()
        neg = (d['fear'] + d['pain'] + d['hunger'] + d['loneliness']
               + d['fatigue'] + d['boredom'])
        return clip(1.0 - neg / 4.0, -1.0, 1.0)
