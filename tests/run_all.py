"""Запустить все тесты: python tests/run_all.py"""
import importlib
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MODULES = [
    'tests.test_brain',
    'tests.test_survival',
    'tests.test_speech',
    'tests.test_crafting',
    'tests.test_concepts',
    'tests.test_games',
]

failed = 0
for name in MODULES:
    print(f"\n===== {name} =====")
    try:
        importlib.import_module(name)
    except Exception:
        failed += 1
        traceback.print_exc()

print("\n" + "=" * 40)
if failed:
    print(f"ПРОВАЛЕНО модулей: {failed}")
    sys.exit(1)
print("ВСЕ ТЕСТЫ ПРОШЛИ")
