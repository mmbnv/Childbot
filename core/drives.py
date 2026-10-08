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

tension() — интегральный «дискомфорт», который запускает поведение.
"""


def clip(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


class Drives:
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

    # ============ ТЕЧЕНИЕ ВРЕМЕНИ ============

    def tick(self, state, is_new_cell, dt=1.0):
        # --- ГОЛОД: из реального food ---
        real_food = state.get('food', 20)
        self.hunger = clip((20.0 - real_food) / 20.0)

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
        hp = state.get('health', 20)
        if state.get('recent_damage', False):
            self.pain = clip(self.pain + 0.5)
            self.fear = clip(self.fear + 0.4)
        if hp < 10:
            self.pain = clip(self.pain + 0.03 * dt)
            self.fear = clip(self.fear + 0.04 * dt)
        self.pain = clip(self.pain - 0.01 * dt)  # естественное заживление

        # --- СТРАХ: угрозы ---
        if is_night:
            self.fear = clip(self.fear + 0.03 * dt)
        nearest = state.get('nearest_hostile')
        if nearest:
            d = nearest.get('distance', 999)
            if d < 4:
                self.fear = clip(self.fear + 0.3 * dt)
            elif d < 10:
                self.fear = clip(self.fear + 0.15 * dt)
            elif d < 16:
                self.fear = clip(self.fear + 0.06 * dt)

        if not nearest and not is_night and not state.get('recent_damage'):
            self.fear *= 0.99

        # --- СКУКА: нужна новизна ---
        self.boredom = clip(self.boredom + 0.015 * dt)
        if is_new_cell:
            self.boredom = clip(self.boredom - 0.6)

        # --- ЛЮБОПЫТСТВО: тянет к новому; падает, когда новое найдено ---
        self.curiosity = clip(self.curiosity + 0.008 * dt)
        if is_new_cell:
            self.curiosity = clip(self.curiosity - 0.25)

        # --- ОДИНОЧЕСТВО: привязанность ---
        self.loneliness = clip(self.loneliness + 0.020 * dt)
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

    def relieve(self, drive, amount):
        if hasattr(self, drive):
            setattr(self, drive, clip(getattr(self, drive) - amount))

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
