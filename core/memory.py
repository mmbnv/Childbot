"""
Memory — пространственная память (семантическая: «что где лежит»).

Это карта мира, а не события. События — в EpisodicMemory.
"""
import json
import os
from collections import defaultdict


class Memory:
    def __init__(self, file="data/memory.json"):
        self.file = file
        self.visited_cells = set()
        self.danger_cells = set()
        self.blacklisted_cells = set()
        self.stuck_count = defaultdict(int)
        self.player_positions = {}
        self.creator_name = None
        self.new_cells = 0
        self.total_steps = 0
        self.load()

    def load(self):
        if not os.path.exists(self.file):
            return
        if os.path.getsize(self.file) == 0:
            return
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.visited_cells = set(tuple(c) for c in data.get('visited_cells', []))
            self.danger_cells = set(tuple(c) for c in data.get('danger_zones', []))
            self.blacklisted_cells = set(tuple(c) for c in data.get('blacklisted_cells', []))
            self.player_positions = {k: tuple(v) for k, v in data.get('player_positions', {}).items()}
            self.new_cells = data.get('new_cells', 0)
            self.total_steps = data.get('total_steps', 0)
            if self.player_positions:
                self.creator_name = list(self.player_positions.keys())[0]
        except Exception as e:
            print(f"Ошибка памяти: {e}")

    def save(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        data = {
            'visited_cells': [list(c) for c in self.visited_cells],
            'danger_zones': [list(c) for c in self.danger_cells],
            'blacklisted_cells': [list(c) for c in self.blacklisted_cells],
            'player_positions': {k: list(v) for k, v in self.player_positions.items()},
            'new_cells': self.new_cells,
            'total_steps': self.total_steps,
        }
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_cell(self, cell):
        if cell not in self.visited_cells:
            self.visited_cells.add(cell)
            self.new_cells += 1
            return True
        return False

    def mark_danger(self, cell):
        self.danger_cells.add(cell)

    def is_dangerous(self, cell):
        return cell in self.danger_cells

    def blacklist(self, cell):
        self.blacklisted_cells.add(cell)
        print(f"🚫 Клетка {cell} в чёрном списке")

    def is_blacklisted(self, cell):
        return cell in self.blacklisted_cells
