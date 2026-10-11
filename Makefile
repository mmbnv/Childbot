.PHONY: install test compile mock body brain clean

install:      ## зависимости мозга
	pip install -r requirements.txt

compile:      ## проверка синтаксиса Python и JS
	python -m py_compile core/*.py adapters/*.py run.py tests/*.py
	node --check bot.js

test: compile ## все тесты мозга (без Minecraft)
	python tests/run_all.py

mock:         ## короткий прогон на искусственном теле
	python run.py --mock --steps=100

body:         ## тело: подключение к серверу Minecraft
	node bot.js

brain:        ## мозг: подключение к телу на localhost:3000
	python run.py

clean:        ## убрать состояние и кэш
	rm -rf data __pycache__ core/__pycache__ adapters/__pycache__ tests/__pycache__
