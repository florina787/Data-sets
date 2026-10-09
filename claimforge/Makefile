.PHONY: install test api ui data demo
install: ; pip install -r requirements.txt
test: ; python -m pytest
api: ; uvicorn app.api.main:app --reload --port 8000
ui: ; streamlit run frontend/streamlit_app.py
data: ; python scripts/generate_synthetic_data.py
demo: ; python scripts/run_demo.py
