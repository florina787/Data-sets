.PHONY: install install-dev test lint api ui docker

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

test:
	python -m pytest

lint:
	ruff check app frontend tests --select F,E9,B,I --ignore B008 --line-length 200

api:
	uvicorn app.api.main:app --reload --port 8000

ui:
	streamlit run frontend/streamlit_app.py

docker:
	docker compose up --build
