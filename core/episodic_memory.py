"""
EpisodicMemory — эпизодическая память (автобиография).

В отличие от семантической памяти (Memory — «что где лежит»), эпизодическая
хранит события «что случилось со мной, когда и почему»:
  * эпизод = (что было, что сделал, что почувствовал, результат);
  * эмоциональная окраска (valence) — как в амигдале: яркое помнится лучше;
  * консолидация: во время «сна» эпизоды уплотняются, слабые забываются;
  * извлечение похожих эпизодов — основа для обучения на своём опыте.

Сохранение на диск — память переживает перезапуск, как у живого существа.
"""
import json
import os
import time
import random


EPISODES_FILE = "data/episodes.json"


class Episode:
    __slots__ = ('what', 'action', 'feeling', 'result', 'valence', 'time', 'importance')

    def __init__(self, what, action, feeling, result, valence, importance=1.0):
        self.what = what
        self.action = action
        self.feeling = feeling
        self.result = result
        self.valence = valence          # -1 плохо .. +1 хорошо
        self.time = time.time()
        self.importance = importance

    def to_dict(self):
        return {
            'what': self.what, 'action': self.action, 'feeling': self.feeling,
            'result': self.result, 'valence': self.valence,
            'time': self.time, 'importance': self.importance,
        }

    @classmethod
    def from_dict(cls, d):
        e = cls(d['what'], d['action'], d.get('feeling', ''),
                d.get('result', ''), d.get('valence', 0.0),
                d.get('importance', 1.0))
        e.time = d.get('time', time.time())
        return e

    def text(self):
        age = time.time() - self.time
        when = f"{age/60:.0f} мин назад" if age > 60 else f"{age:.0f} сек назад"
        feel = f" чувствовал {self.feeling}" if self.feeling else ""
        return f"{self.what} → {self.action}{feel} [{when}]"


class EpisodicMemory:
    MAX_EPISODES = 400
    CONSOLIDATE_AT = 300

    def __init__(self, file=EPISODES_FILE):
        self.file = file
        self.episodes = []
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.episodes = [Episode.from_dict(d) for d in data]
            if self.episodes:
                print(f"📖 Автобиография: помню {len(self.episodes)} эпизодов")
        except Exception:
            pass

    def save(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump([e.to_dict() for e in self.episodes[-self.MAX_EPISODES:]],
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def remember(self, what, action, feeling="", result="", valence=0.0, importance=1.0):
        """
        Записать эпизод. Важные и эмоционально яркие события хранятся дольше.
        """
        ep = Episode(what, action, feeling, result, valence, importance)
        self.episodes.append(ep)
        if len(self.episodes) > self.MAX_EPISODES:
            self.episodes.sort(key=lambda e: -(e.importance + abs(e.valence)))
            self.episodes = self.episodes[:self.MAX_EPISODES]
            self.episodes.sort(key=lambda e: e.time)
        return ep

    def recall_similar(self, keyword, n=3):
        """Извлечь похожие эпизоды (по ключевому слову в 'what' или 'action')."""
        kw = keyword.lower()
        hits = [e for e in self.episodes
                if kw in e.what.lower() or kw in e.action.lower()]
        hits.sort(key=lambda e: -e.time)
        return hits[:n]

    def recent(self, n=5):
        return self.episodes[-n:]

    def salient_memories(self, n=3):
        """Самые яркие (эмоциональные) воспоминания."""
        return sorted(self.episodes, key=lambda e: -(abs(e.valence) * e.importance))[:n]

    def consolidate(self):
        """
        «Сон»: убрать эмоционально пустые и старые эпизоды, оставить значимые.
        """
        if len(self.episodes) < self.CONSOLIDATE_AT:
            return 0
        before = len(self.episodes)
        now = time.time()
        keep = []
        for e in self.episodes:
            age_h = (now - e.time) / 3600.0
            # значимость = эмоция + важность, затухает со временем
            strength = abs(e.valence) * e.importance / (1.0 + age_h * 0.5)
            if strength > 0.05 or age_h < 0.5:
                keep.append(e)
        self.episodes = keep
        self.save()
        return before - len(keep)

    def summary(self):
        if not self.episodes:
            return "автобиография пуста"
        last = self.episodes[-1]
        vivid = self.salient_memories(1)
        vivid_str = ""
        if vivid:
            vivid_str = f" | самое яркое: {vivid[0].what}"
        return f"{len(self.episodes)} эпизодов, последний: {last.text()}{vivid_str}"
