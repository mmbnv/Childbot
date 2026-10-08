"""
GlobalWorkspace — «глобальное рабочее пространство» (теория GWT, Баарс).

Идея: мозг — это набор параллельных специализированных модулей. Большинство
сигналов остаются локальными. Но самый важный, «выигравший конкуренцию»
сигнал попадает в рабочее пространство и транслируется ВСЕМ модулям сразу.

Именно этот «broadcast» и есть то, что мы называем осознанным вниманием:
в каждый момент существо осознаёт ровно одну вещь — самую значимую.

Реализация:
  * attention-конкуренция: у каждого кандидата (драйв, угроза, цель, объект,
    новизна, речь) есть вес — salience. Победитель = фокус внимания.
  * broadcast: фокус доступен всем модулям через .focus() / .focus_text().
  * метакогниция: система знает, на что она сейчас направлена.
"""
import time


class Candidate:
    __slots__ = ('channel', 'content', 'salience', 'time')

    def __init__(self, channel, content, salience):
        self.channel = channel
        self.content = content
        self.salience = salience
        self.time = time.time()


class GlobalWorkspace:
    def __init__(self, dwell_sec=1.5):
        self.dwell_sec = dwell_sec
        self.candidates = []
        self._focus = None
        self._focus_time = 0
        self.history = []
        self.broadcast_count = 0

    def submit(self, channel, content, salience):
        """Модуль предлагает сигнал в конкуренцию за внимание."""
        if content is None or salience <= 0:
            return
        self.candidates.append(Candidate(channel, content, float(salience)))

    def compete(self, neuromod=None):
        """
        Провести конкуренцию. Победитель становится фокусом внимания.
        Но внимание инертно (dwell) — оно не переключается мгновенно.
        """
        if not self.candidates:
            return self._focus

        # Скан: чем выше salience, тем больше шанс
        best = max(self.candidates, key=lambda c: c.salience)
        now = time.time()

        # Инерция внимания: держим прежний фокус, если он не угас и не подавлен
        if self._focus is not None and (now - self._focus_time) < self.dwell_sec:
            decayed = self._focus.salience * 0.6
            if decayed >= best.salience:
                self.candidates = []
                return self._focus

        self._focus = best
        self._focus_time = now
        self.broadcast_count += 1
        self.history.append({'channel': best.channel, 'content': best.content,
                             'time': now})
        if len(self.history) > 50:
            self.history.pop(0)

        if neuromod is not None:
            neuromod.on_attention(best.channel)

        self.candidates = []
        return self._focus

    def focus(self):
        return self._focus

    def focus_text(self):
        if not self._focus:
            return "ни на чём"
        return f"{self._focus.channel}: {self._focus.content}"

    def is_focused_on(self, channel):
        return bool(self._focus and self._focus.channel == channel)

    def recent_channels(self, n=5):
        return [h['channel'] for h in self.history[-n:]]

    def summary(self):
        if not self._focus:
            return "внимание: ни на чём"
        return (f"внимание → [{self._focus.channel}] {self._focus.content} "
                f"(salience {self._focus.salience:.2f}, "
                f"переключений {self.broadcast_count})")
