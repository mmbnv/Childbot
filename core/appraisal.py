"""
Appraisal — ОЦЕНКА происходящего: смысл события для моих нужд.

Это ядро человеческой эмоции. Животное реагирует на стимул; человек сначала
ОЦЕНИВАЕТ, что событие значит для него, — и уже из этой оценки рождается
чувство и поступок. Одна и та же вещь пугает или радует в зависимости от
смысла (Лазарус, Смит-Элсворт, Шерер).

Оценка идёт по нескольким осям, и каждая ось сдвигает чувство и тело:

  * goal_ok    — помогло ли моим нуждам (+1/−1/0);
  * harm       — насколько вредит (0..1);
  * benefit    — насколько помогает (0..1);
  * novelty    — насколько неожиданно (0..1);
  * control    — могу ли я на это повлиять (0..1);
  * self_agency— сделал ли это Я сам;
  * other      — кто это сделал (имя / None = случай);
  * norm       — поступил ли я против того, что считаю правильным (0..1);
  * attachment — связано ли со «своим» человеком (папой);
  * loss       — потерял ли важное;
  * blocked    — помешали ли мне;
  * certainty  — насколько понятно, что происходит.

Важно: оценка НЕ односторонняя. Она не только рождает чувство — она меняет
тело (интероцепцию), химию (нейромодуляторы) и сами потребности. Так
замыкается петля: чувство → поступок → облегчение → новое чувство.
"""
from core.temperament import clip


# Как каждая ось оценки сдвигает тело и химию.
#   arousal — возбуждение; tone — телесный тон; mods — нейромодуляторы.
AXIS_EFFECTS = {
    'harm':       {'arousal': +0.5, 'tone': -0.5,
                   'mods': {'noradrenaline': +0.25, 'cortisol': +0.25, 'endorphins': +0.15}},
    'pain':       {'arousal': +0.4, 'tone': -0.6,
                   'mods': {'cortisol': +0.25, 'endorphins': +0.25, 'noradrenaline': +0.15}},
    'benefit':    {'arousal': +0.1, 'tone': +0.3,
                   'mods': {'dopamine': +0.25, 'serotonin': +0.10, 'endorphins': +0.10}},
    'loss':       {'arousal': -0.1, 'tone': -0.4,
                   'mods': {'serotonin': -0.15, 'cortisol': +0.10}},
    'novelty':    {'arousal': +0.3, 'tone': +0.0,
                   'mods': {'noradrenaline': +0.15, 'acetylcholine': +0.20, 'dopamine': +0.10}},
    'blocked':    {'arousal': +0.3, 'tone': -0.2,
                   'mods': {'noradrenaline': +0.20, 'cortisol': +0.10}},
    'attachment': {'arousal': -0.1, 'tone': +0.4,
                   'mods': {'oxytocin': +0.30, 'serotonin': +0.10}},
    'norm':       {'arousal': +0.2, 'tone': -0.3,
                   'mods': {'cortisol': +0.20, 'serotonin': -0.10}},
    'threat_uncertain': {'arousal': +0.5, 'tone': -0.5,
                         'mods': {'cortisol': +0.25, 'noradrenaline': +0.25}},
}


class Appraisal:
    """Оценка события — «что это значит для меня?»."""

    AXES = ('goal_ok', 'harm', 'benefit', 'novelty', 'control', 'self_agency',
            'other', 'norm', 'attachment', 'loss', 'blocked', 'certainty', 'pain')

    def __init__(self, **kw):
        for a in self.AXES:
            setattr(self, a, kw.get(a, 0))
        self.other = kw.get('other')
        self.self_agency = bool(kw.get('self_agency', False))
        self.attachment = bool(kw.get('attachment', False))
        self.blocked = bool(kw.get('blocked', False))
        self.certainty = kw.get('certainty', 0.5)

    def to_dict(self):
        return {a: getattr(self, a) for a in self.AXES}

    # ---------- ГЛАВНЫЕ ВЫВОДЫ ОЦЕНКИ ----------

    def is_threat(self):
        return self.harm > 0.4

    def is_gain(self):
        return self.benefit > 0.3 or self.goal_ok > 0

    def is_loss(self):
        return self.loss > 0.4 and self.control < 0.4

    def blame(self):
        """Кто виноват: 'я', 'другой' или 'никто' (обстоятельства)."""
        if self.self_agency:
            return 'я'
        if self.other:
            return 'другой'
        return 'никто'

    def coping_potential(self):
        """Могу ли справиться: контроль + уверенность."""
        return clip(0.6 * self.control + 0.4 * self.certainty)

    def summary(self):
        parts = []
        if self.is_threat():
            parts.append('угроза')
        if self.is_gain():
            parts.append('польза')
        if self.is_loss():
            parts.append('потеря')
        if self.blocked:
            parts.append('помеха')
        if self.novelty > 0.5:
            parts.append('новизна')
        if self.attachment:
            parts.append('свой')
        if self.norm > 0.4:
            parts.append('против правил')
        return ', '.join(parts) or 'нейтрально'


class Appraiser:
    """
    Оценщик: превращает сырой «эпизод шага» в Appraisal и РАЗВОРАЧИВАЕТ его
    обратно в тело и химию. Это двусторонняя связь, которой не хватало:
    событие меняет и чувство, и организм.
    """

    def __init__(self, temperament):
        self.temperament = temperament

    def build(self, drives, intero, *, is_new=False, danger=False, harm=0.0,
              benefit=0.0, loss=0.0, blocked=False, attachment=False, norm=0.0,
              self_agency=False, other=None, unanswered=False, certainty=0.5):
        """Собрать оценку шага из состояния тела и происходящего."""
        d = drives.to_dict()
        pain = d['pain']
        # Опасность и боль — уже вред.
        harm = max(harm, d['pain'], d['fear'] * 0.7 if danger else d['fear'] * 0.3)
        # Комфорт и близость — польза.
        benefit = max(benefit, d['comfort'] * 0.5)
        if attachment:
            benefit = max(benefit, 0.5)
        # Одиночество — потеря близости, если долго.
        if d['loneliness'] > 0.6 and not attachment:
            loss = max(loss, d['loneliness'] * 0.6)

        return Appraisal(
            goal_ok=(1 if benefit > 0.3 else (-1 if harm > 0.4 else 0)),
            harm=harm, benefit=benefit, loss=loss,
            novelty=(0.7 if is_new else 0.0),
            control=(0.5 if not danger else 0.3),
            self_agency=self_agency, other=other, norm=norm,
            attachment=attachment, blocked=blocked, certainty=certainty,
            pain=pain,
        )

    def apply_to_body(self, appraisal, drives, intero, neuromod):
        """
        Развернуть оценку обратно в тело: возбуждение, телесный тон и химию.
        Так «мне страшно» — это не ярлык, а реальное состояние организма.
        """
        a = appraisal
        axes = {
            'harm': a.harm, 'pain': a.pain, 'benefit': a.benefit, 'loss': a.loss,
            'novelty': a.novelty, 'blocked': (0.5 if a.blocked else 0.0),
            'attachment': (0.6 if a.attachment else 0.0), 'norm': a.norm,
        }
        # Опасность при неясном исходе особенно «заводит».
        if a.is_threat() and a.coping_potential() < 0.4:
            axes['threat_uncertain'] = 1.0

        d_arousal = d_tone = 0.0
        for axis, strength in axes.items():
            if strength <= 0:
                continue
            eff = AXIS_EFFECTS.get(axis)
            if not eff:
                continue
            w = strength * self.temperament.reactivity()
            d_arousal += eff['arousal'] * w
            d_tone += eff['tone'] * w
            for mod, delta in eff['mods'].items():
                cur = getattr(neuromod, mod, None)
                if cur is not None:
                    setattr(neuromod, mod, clip(cur + delta * w))

        intero.modulate(arousal=d_arousal, tone=d_tone)
        return d_arousal, d_tone
