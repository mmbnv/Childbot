"""
WorldModel — модель окружающего мира (что вокруг, день/ночь).
"""
import time
import requests


class WorldModel:
    def __init__(self, adapter):
        self.adapter = adapter
        self.last_update = 0
        self.blocks = []
        self.is_day = True
        self.time_of_day = 0

    def refresh(self, force=False):
        now = time.time()
        if not force and (now - self.last_update) < 3:
            return
        self.last_update = now
        try:
            data = self.adapter.get_world()
            if data is None:
                return
            self.blocks = data.get('blocks', [])
            self.time_of_day = data.get('time', 0)
            self.is_day = data.get('isDay', True)
        except Exception:
            pass

    def summary(self):
        if not self.blocks:
            return "вокруг ничего не вижу"
        counts = {}
        for b in self.blocks:
            counts[b['name']] = counts.get(b['name'], 0) + 1
        top = sorted(counts.items(), key=lambda x: -x[1])[:6]
        blocks_str = ', '.join([f"{name}×{cnt}" for name, cnt in top])
        day_str = "день" if self.is_day else "ночь"
        return f"{day_str}. Вокруг: {blocks_str}"

    def find_blocks(self, name_contains):
        return [b for b in self.blocks if name_contains in b['name']]

    def has_diggable(self):
        return any(b.get('diggable') for b in self.blocks)
