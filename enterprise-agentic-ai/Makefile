.PHONY: install install-embeddings test api ui docker-up docker-down

install:
	pip install -r requirements-dev.txt

install-embeddings:
	pip install -r requirements-embeddings.txt

test:
	python -m pytest

api:
	uvicorn app.api.main:app --reload --port 8000

ui:
	streamlit run frontend/streamlit_app.py --server.port 8501

docker-up:
	docker compose up --build

docker-down:
	docker compose down
