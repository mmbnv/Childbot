"""
Social — «свой человек»: привязанность, разлука и понимание другого.

Человеческий детёныш выживает не силой, а привязанностью. Теория привязанности
(Боулби, Эйнсворт) говорит: у ребёнка есть ОДИН значимый взрослый — «надёжная
база». От неё можно уйти исследовать мир и к ней же вернуться за утешением.

Здесь:
  * Привязанность — прочная связь с папой (не просто «цель: go_to_player»).
    Она растёт от близости и заботы и рождает желание быть рядом.
  * Разлука — когда папы долго нет, возникает дистресс: сначала зов, потом
    поиск, потом печаль. Это не «цель», а чувство.
  * Социальное считывание (social referencing) — ребёнок смотрит на реакцию
    взрослого, чтобы понять, безопасно ли. Здесь: настроение папы заражает.
  * Теория сознания (theory of mind) — понимание, что у другого есть свои
    намерения, знания и чувства, отличные от моих. Ребёнок учится предугадывать
    желания папы и замечать, что папа чего-то не знает (могу показать/сказать).
  * Просоциальность — желание помочь, поделиться, порадовать.
"""
import json
import os
import time

from core.temperament import clip


SOCIAL_FILE = "data/social.json"


class MindReading:
    """Модель чужой психики: что папа знает, чего хочет, что чувствует."""

    def __init__(self):
        self.name = None
        self.beliefs = {}       # что, по-моему, папа знает о мире
        self.desires = []       # чего, по-моему, папа хочет
        self.emotion = None     # как папа, по-моему, себя чувствует
        self.last_seen = 0.0
        self.interactions = 0

    def observe(self, other_name, message_text=None, other_state=None):
        """Обновить модель папы по его словам и поведению."""
        if other_name:
            self.name = other_name
        self.last_seen = time.time()
        self.interactions += 1

        if message_text:
            low = message_text.lower()
            # Что папа хочет (из его просьб).
            for want, keys in (('быть рядом', ['подойди', 'ко мне', 'иди сюда']),
                               ('чтобы я поиграл', ['попрыгай', 'покрутись', 'поиграй']),
                               ('чтобы я поработал', ['копай', 'сруби', 'построй', 'добудь']),
                               ('чтобы я отдохнул', ['стой', 'остановись', 'отдохни'])):
                if any(k in low for k in keys):
                    if want not in self.desires:
                        self.desires.append(want)
                    self.desires = self.desires[-5:]
            # Что папа чувствует (из его слов).
            for emo, keys in (('радость', ['молодец', 'спасибо', 'класс', 'супер', 'круто']),
                              ('злость', ['хватит', 'нельзя', 'перестань', 'плохо']),
                              ('печаль', ['устал', 'грустно', 'плохо'])):
                if any(k in low for k in keys):
                    self.emotion = emo

    def papa_wants(self, what):
        return what in self.desires

    def papa_knows(self, fact):
        return fact in self.beliefs

    def teach(self, fact):
        """Я сообщил папе факт — теперь, по-моему, он его знает."""
        self.beliefs[fact] = time.time()

    def gaps(self):
        """Чего папа, по-моему, ещё не знает — можно рассказать/показать."""
        return [k for k, v in self.beliefs.items() if time.time() - v > 600]

    def summary(self):
        if not self.name:
            return "папу ещё не видел"
        wants = ', '.join(self.desires) or 'не знаю, чего хочет'
        emo = f", кажется, {self.emotion}" if self.emotion else ""
        return f"папа {self.name}: хочет — {wants}{emo}"


class Social:
    def __init__(self, temperament, file=SOCIAL_FILE):
        self.temperament = temperament
        self.file = file
        self.bond = 0.15            # сила привязанности к папе (0..1)
        self.attachment_name = None
        self.last_near = 0.0
        self.last_seen = 0.0
        self.separation_distress = 0.0
        self.lost_count = 0         # сколько раз теряли папу (для чувствительности)
        self.greeted = False
        self.greeted_this_reunion = False   # радость встречи — один раз на возвращение
        self.away_ticks = 0         # сколько шагов папы нет подряд (не время, а шаги)
        self.tom = MindReading()
        self.gifts = 0              # сколько раз делился/помогал
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.bond = d.get('bond', 0.15)
            self.attachment_name = d.get('attachment_name')
            self.lost_count = d.get('lost_count', 0)
            self.gifts = d.get('gifts', 0)
            if self.attachment_name:
                self.tom.name = self.attachment_name
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(self.file) or '.', exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump({'bond': self.bond, 'attachment_name': self.attachment_name,
                           'lost_count': self.lost_count, 'gifts': self.gifts},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============ ПРИВЯЗАННОСТЬ И РАЗЛУКА ============

    def update(self, state, dt=1.0):
        """Течение привязанности: близость укрепляет, разлука томит."""
        p = state.get('player') if state else None
        now = time.time()
        near = bool(p and p.get('distance', 999) < 12)

        if p and p.get('name'):
            self.attachment_name = p['name']
            self.tom.name = p['name']

        if near:
            self.last_near = now
            self.last_seen = now
            self.greeted = True
            self.away_ticks = 0
            # Близость и забота растут медленно — связь не за день.
            self.bond = clip(self.bond + 0.004 * self.temperament.attach_rate() * dt)
            self.separation_distress = clip(self.separation_distress - 0.3 * dt)
        else:
            # Разлука: дистресс растёт от числа шагов без папы, а не от часов
            # (существо живёт шагами, а не настенным временем).
            self.away_ticks += 1
            if self.away_ticks > 20:
                self.separation_distress = clip(
                    self.separation_distress + 0.02 * self.temperament.attach_rate() * dt)
        return self.separation_distress

    def on_separation(self):
        """Папа пропал надолго — это переживается, а не просто «нет цели»."""
        self.lost_count += 1
        self.save()
        return self.separation_distress

    def on_reunion(self):
        """Папа вернулся — радость встречи тем сильнее, чем дольше ждал."""
        joy = clip(0.4 + self.bond * 0.5 + self.separation_distress * 0.5)
        self.separation_distress = 0.0
        self.bond = clip(self.bond + 0.02)
        self.save()
        return joy

    def needs_contact(self):
        """Хочется к папе: связь сильная, а его нет."""
        return self.separation_distress > 0.4 and self.bond > 0.3

    # ============ ПРОСОЦИАЛЬНОСТЬ ============

    def on_help(self):
        """Помог папе — связь крепнет, это радует."""
        self.gifts += 1
        self.bond = clip(self.bond + 0.01)
        self.save()
        return True

    def wants_to_please(self):
        """Из любви хочется радовать папу (а не только выполнять команды)."""
        return self.bond > 0.4 and self.temperament.sociability() > 0.3

    def summary(self):
        return (f"привязанность к {self.attachment_name or 'папе'}: {self.bond:.2f}, "
                f"разлука: {self.separation_distress:.2f}, помог {self.gifts} раз")
