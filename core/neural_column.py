"""
NeuralColumn — биологически вдохновлённая кортикальная колонна.

Принципы, взятые из реальной коры:
1. Разреженное кодирование (sparse coding ~10% активных нейронов)
2. Рекуррентные связи (внутренняя динамика → рабочая память, устойчивая активность)
3. Спайковая динамика: рефрактерность и усталость (нейрон «молчит» после спайка)
4. Hebbian learning + STDP (временная причинность: кто раньше — тот и учит)
5. Дофаминовая модуляция обучения (подкрепление)
6. Гомеостатическая пластичность (активность держится в норме)
7. Структурная пластичность (рост и прунинг синапсов)
8. Метапластичность (per-synapse скорость обучения)

Работает на numpy — быстро, без torch. API совместим с прежним:
    forward(x) -> (h, out)
    learn(x, h, out, target, dopamine=0.5, lr=0.01)
"""
import os
import numpy as np


class NeuralColumn:
    def __init__(self, n_input, n_hidden=64, n_output=5, seed=42,
                 recurrent_gain=0.35, refractory_tau=0.6):
        self.n_input = n_input
        self.n_hidden = n_hidden
        self.n_output = n_output
        self.recurrent_gain = recurrent_gain
        self.refractory_tau = refractory_tau

        rng = np.random.RandomState(seed)

        # Входной слой: разреженная инициализация (~20% связей, как в коре)
        self.W_in = rng.randn(n_input, n_hidden) * 0.1
        self.W_in *= (rng.rand(n_input, n_hidden) < 0.2).astype(np.float64)

        # Рекуррентные связи внутри колонны (рабочая память / устойчивая активность)
        self.W_rec = rng.randn(n_hidden, n_hidden) * 0.05
        self.W_rec *= (rng.rand(n_hidden, n_hidden) < 0.15).astype(np.float64)
        np.fill_diagonal(self.W_rec, 0.0)

        # Выходной слой
        self.W_out = rng.randn(n_hidden, n_output) * 0.1

        # Смещение
        self.bias = rng.randn(n_hidden) * 0.02

        # Гомеостаз: бегущее среднее активности скрытых нейронов
        self.hidden_activity = np.zeros(n_hidden)
        self.target_sparsity = 0.1

        # Метапластичность: per-synapse модификатор скорости обучения
        self.W_in_plastic = np.ones((n_input, n_hidden))
        self.W_out_plastic = np.ones((n_hidden, n_output))
        self.W_rec_plastic = np.ones((n_hidden, n_hidden))

        # Возраст синапса — для прунинга
        self.synapse_age = np.zeros((n_input, n_hidden))

        # Динамическое состояние
        self.prev_h = np.zeros(n_hidden)      # прошлая активность (рекурренция)
        self.refractory = np.zeros(n_hidden)  # след спайка (усталость)
        self.trace_pre = np.zeros(n_hidden)   # STDP: след пресинаптической активности
        self.trace_post = np.zeros(n_hidden)  # STDP: след постсинаптической активности

        # Статистика
        self.total_updates = 0
        self.recent_error = 1.0
        self.spike_count = 0

    # ============ ДИНАМИКА ============

    def reset_state(self):
        """Сбросить рабочую память (напр. перед сном/новым эпизодом)."""
        self.prev_h = np.zeros(self.n_hidden)
        self.refractory = np.zeros(self.n_hidden)

    def forward(self, x, recurrent=True, update_state=True):
        """
        x — вектор (n_input,) → (h, out).

        recurrent: учитывать ли внутреннюю динамику (рабочую память).
        update_state: сохранять ли новое состояние.
        """
        h_pre = self.W_in.T @ x + self.bias
        if recurrent:
            h_pre = h_pre + self.recurrent_gain * (self.W_rec.T @ self.prev_h)

        h = np.tanh(h_pre)

        # Спайковая рефрактерность: только что сработавшие нейроны «отдыхают»
        h = h * (1.0 - self.refractory)

        # Разреженность: k-WTA (top-k активных, как в коре)
        k = max(1, int(self.n_hidden * self.target_sparsity))
        if k < self.n_hidden:
            thresh = np.partition(h, -k)[-k]
            h = np.where(h >= thresh, h, 0.0)

        # Обновляем след рефрактерности (спайк → усталость, экспоненциальный распад)
        spiked = (h > 0).astype(np.float64)
        self.refractory = self.refractory * (1.0 - self.refractory_tau) + spiked * self.refractory_tau
        self.spike_count += int(spiked.sum())

        out = self.W_out.T @ h

        if update_state:
            self.prev_h = h.copy()

        return h, out

    # ============ ОБУЧЕНИЕ ============

    def learn(self, x, h, out, target, dopamine=0.5, lr=0.01):
        """
        target: желаемый выход (n_output,)
        dopamine: 0..1 — модулятор обучения (подкрепление)
        """
        error = target - out
        self.recent_error = float(np.mean(np.abs(error)))

        # --- 1. ВЫХОДНОЙ слой: delta rule с дофаминовой модуляцией ---
        dw_out = np.outer(h, error) * lr * (0.5 + dopamine)
        self.W_out += dw_out * self.W_out_plastic

        # Метапластичность: где ошибка была большой — учимся осторожнее
        self.W_out_plastic *= (1.0 - 0.01 * np.abs(error[None, :]))
        self.W_out_plastic = np.clip(self.W_out_plastic, 0.1, 2.0)

        # --- 2. СКРЫТЫЙ слой: Hebbian с обратно-распространённой ошибкой ---
        error_signal = np.abs(self.W_out @ error)
        hebbian = np.outer(x, h) * lr * (1.0 + error_signal)
        self.W_in += hebbian * self.W_in_plastic

        # --- 3. РЕКУРРЕНТНЫЙ слой: STDP (временная причинность) ---
        self.trace_pre = 0.9 * self.trace_pre + h
        self.trace_post = 0.9 * self.trace_post + h
        # Потенциация: постсинаптический спайк сразу после пресинаптического
        stdp_pot = np.outer(self.trace_pre, h) * lr * 0.2 * (0.5 + dopamine)
        # Депрессия: пресинаптический спайк без последующего постсинаптического
        stdp_dep = np.outer(h, self.trace_post) * lr * 0.05
        self.W_rec += (stdp_pot - stdp_dep) * self.W_rec_plastic
        np.fill_diagonal(self.W_rec, 0.0)

        # --- 4. ГОМЕОСТАЗ: активность в диапазоне ---
        self.hidden_activity = 0.99 * self.hidden_activity + 0.01 * (h > 0).astype(np.float64)
        overactive = self.hidden_activity > self.target_sparsity * 2.0
        silent = self.hidden_activity < self.target_sparsity * 0.5
        self.W_out[overactive, :] *= 0.99
        self.W_out[silent, :] *= 1.01
        self.bias[overactive] -= 0.001
        self.bias[silent] += 0.001

        # --- 5. СТРУКТУРНАЯ ПЛАСТИЧНОСТЬ: прунинг и рост ---
        self.synapse_age += 1
        self.W_in[np.abs(self.W_in) < 0.01] *= 0.95

        dead = (np.abs(self.W_in) < 0.001) & (self.synapse_age > 2000)
        if dead.any():
            n_dead = int(dead.sum())
            rng = np.random.RandomState(self.total_updates)
            self.W_in[dead] = rng.randn(n_dead) * 0.1
            self.synapse_age[dead] = 0
        self.synapse_age[~dead] = 0

        # --- 6. ОГРАНИЧЕНИЯ ---
        np.clip(self.W_in, -3, 3, out=self.W_in)
        np.clip(self.W_out, -3, 3, out=self.W_out)
        np.clip(self.W_rec, -1.5, 1.5, out=self.W_rec)

        self.total_updates += 1

    # ============ МЫСЛЕННАЯ СИМУЛЯЦИЯ ============

    def imagine(self, x, steps=1):
        """
        Прогнать колонну «в уме» без обучения и без изменения состояния.
        """
        saved_prev = self.prev_h.copy()
        saved_refr = self.refractory.copy()
        out = None
        for _ in range(max(1, steps)):
            h, out = self.forward(x, recurrent=True, update_state=True)
        self.prev_h = saved_prev
        self.refractory = saved_refr
        return out

    # ============ SAVE / LOAD ============

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        np.savez(path,
                 W_in=self.W_in, W_rec=self.W_rec, W_out=self.W_out,
                 bias=self.bias,
                 W_in_plastic=self.W_in_plastic,
                 W_out_plastic=self.W_out_plastic,
                 W_rec_plastic=self.W_rec_plastic,
                 hidden_activity=self.hidden_activity,
                 synapse_age=self.synapse_age,
                 prev_h=self.prev_h,
                 refractory=self.refractory,
                 total_updates=self.total_updates,
                 spike_count=self.spike_count)

    def load(self, path):
        if not os.path.exists(path):
            return False
        try:
            d = np.load(path)

            # Если размеры не совпадают с текущей архитектурой (например,
            # изменился список действий → другой n_input), старые веса нельзя
            # использовать напрямую. Проверяем и аккуратно переносим, что можно.
            saved_in = d['W_in'].shape[0]
            saved_hid = d['W_in'].shape[1]
            saved_out = d['W_out'].shape[1]
            if (saved_in != self.n_input or saved_hid != self.n_hidden
                    or saved_out != self.n_output):
                print(f"⚠️  Сохранённая колонна несовместима "
                      f"({saved_in}→{saved_hid}→{saved_out}) с текущей "
                      f"({self.n_input}→{self.n_hidden}→{self.n_output}). "
                      f"Обучаюсь заново.")
                return False

            self.W_in = d['W_in']
            self.W_rec = d['W_rec'] if 'W_rec' in d else self.W_rec
            self.W_out = d['W_out']
            if 'bias' in d:
                self.bias = d['bias']
            self.W_in_plastic = d['W_in_plastic']
            self.W_out_plastic = d['W_out_plastic']
            if 'W_rec_plastic' in d:
                self.W_rec_plastic = d['W_rec_plastic']
            self.hidden_activity = d['hidden_activity']
            self.synapse_age = d['synapse_age']
            if 'prev_h' in d:
                self.prev_h = d['prev_h']
            if 'refractory' in d:
                self.refractory = d['refractory']
            self.total_updates = int(d['total_updates'])
            if 'spike_count' in d:
                self.spike_count = int(d['spike_count'])
            return True
        except Exception as e:
            print(f"⚠️  Не могу загрузить нейроколонну: {e}")
            return False

    def stats(self):
        alive = int((np.abs(self.W_in) > 0.001).sum())
        total = self.W_in.size
        return {
            'updates': self.total_updates,
            'alive_synapses': alive,
            'total_synapses': total,
            'sparsity_pct': 100 * alive / total,
            'avg_activity': float(self.hidden_activity.mean()),
            'recent_error': self.recent_error,
            'spikes': self.spike_count,
        }
