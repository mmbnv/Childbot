"""
Voice — голос (озвучка мыслей и речи). Не критичен: при отсутствии
pyttsx3 просто молчит.
"""
import threading

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False


class Voice:
    def __init__(self, enabled=True, rate=180, volume=1.0):
        self.enabled = enabled and HAS_PYTTSX3
        self.engine = None
        if not HAS_PYTTSX3:
            print("⚠️  pyttsx3 не установлен. Голос выключен.")
            return

        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', rate)
            self.engine.setProperty('volume', volume)

            voices = self.engine.getProperty('voices')
            russian = None
            for v in voices:
                name = (v.name or '').lower()
                lang = ''
                try:
                    lang = (v.languages[0] if v.languages else '').lower()
                    if isinstance(lang, bytes):
                        lang = lang.decode('utf-8', errors='ignore')
                except Exception:
                    pass
                if 'ru' in lang or 'russian' in name or 'irina' in name or 'pavel' in name:
                    russian = v.id
                    break

            if russian:
                self.engine.setProperty('voice', russian)
                print("🔊 Голос: русский найден")
            else:
                print("🔊 Голос: русского нет, будет стандартный")
        except Exception as e:
            print(f"⚠️  pyttsx3 init ошибка: {e}")
            self.enabled = False

    def say(self, text):
        if not self.enabled or not text:
            return
        try:
            threading.Thread(target=self._speak, args=(text,), daemon=True).start()
        except Exception as e:
            print(f"⚠️  Голос: {e}")

    def _speak(self, text):
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"⚠️  Голос: {e}")


VOICE_ENABLED = True
