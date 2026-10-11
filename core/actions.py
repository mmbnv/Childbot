"""
ActionsCatalog — какие действия вообще доступны телу.

Мозг не должен знать имена действий «наизусть» — он спрашивает у тела.
"""


class ActionsCatalog:
    def __init__(self, adapter):
        self.adapter = adapter
        self.actions = []
        self.refresh()

    def refresh(self):
        getter = getattr(self.adapter, "get_actions", None)
        if callable(getter):
            try:
                self.actions = getter() or []
                print(f"📋 Доступно действий: {len(self.actions)}")
                return
            except Exception as e:
                print(f"⚠️  Не могу получить действия: {e}")
        self.actions = []

    def describe_for_prompt(self):
        return "\n".join([f"- {a['name']}: {a['desc']}" for a in self.actions])

    def names(self):
        return [a['name'] for a in self.actions]

    def has(self, name):
        return name in self.names()
