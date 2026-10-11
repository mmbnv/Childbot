"""
MinecraftAdapter — «тело» для мозга.

Мозг (core/) не знает про mineflayer. Он видит только этот адаптер:
сенсоры (state / vision / sounds / messages) и моторные действия (action).

Реализация общается с bot.js по HTTP (localhost:3000).
"""
import os
import requests


DEFAULT_URL = os.environ.get("MINECRAFT_BOT_URL", "http://localhost:3000")


class MinecraftAdapter:
    def __init__(self, url=DEFAULT_URL, timeout=4):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._last_messages = []

    # ---------- СЕНСОРЫ ----------

    def _get(self, path):
        try:
            r = requests.get(f"{self.url}{path}", timeout=self.timeout)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    def get_state(self):
        return self._get("/state")

    def get_self(self):
        return self._get("/self")

    def get_vision(self):
        return self._get("/vision")

    def get_sounds(self):
        return self._get("/sounds")

    def get_world(self):
        return self._get("/world")

    def get_messages(self):
        data = self._get("/messages")
        if not data:
            return []
        return data.get("messages", [])

    def get_player_actions(self):
        data = self._get("/player_actions")
        if not data:
            return []
        return data.get("actions", [])

    def get_actions(self):
        data = self._get("/actions")
        if not data:
            return []
        return data.get("actions", [])

    def get_tasks(self):
        """Что игра ставит перед существом (квесты, достижения)."""
        data = self._get("/tasks")
        if not data:
            return []
        return data.get("tasks", [])

    def get_game(self):
        """Кто эта игра: имя и доступные действия."""
        data = self._get("/game")
        if not data:
            return {'name': 'minecraft'}
        return data

    def clear_messages(self):
        try:
            requests.post(f"{self.url}/messages/clear", timeout=self.timeout)
        except Exception:
            pass

    # ---------- МОТОРИКА ----------

    def action(self, action, params=None):
        try:
            r = requests.post(
                f"{self.url}/action",
                json={"action": action, "params": params or {}},
                timeout=30,
            )
            return r.json()
        except Exception as e:
            return {"ok": False, "result": {"ok": False, "reason": f"http_error: {e}"}}

    def say(self, text):
        try:
            requests.post(
                f"{self.url}/action",
                json={"action": "say", "text": text},
                timeout=10,
            )
            return True
        except Exception:
            return False
