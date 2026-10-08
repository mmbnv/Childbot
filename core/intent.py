"""
Intent — тонкая обёртка вокруг AdaptiveIntent.
"""


class IntentResolver:
    def __init__(self, adaptive_intent, catalog):
        self.adaptive = adaptive_intent
        self.catalog = catalog

    def resolve(self, user_text, context):
        return self.adaptive.resolve(user_text, context)


def is_chatter(text):
    t = text.lower().strip()
    return len(t) < 3
