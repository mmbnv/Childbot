"""Общая подготовка тестов: путь к проекту + изоляция состояния.

Мозг пишет состояние в ./data относительно текущего каталога, поэтому
каждый тест переключается в свежий временный каталог — рабочие файлы
data/ в репозитории не трогаются.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.chdir(tempfile.mkdtemp(prefix="childbot-test-"))
