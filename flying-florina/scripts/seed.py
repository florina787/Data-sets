"""Regenerate the synthetic database (seed 20261024). Usage: backend/.venv/bin/python scripts/seed.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.seed.generator import reset_database  # noqa: E402

print(json.dumps(reset_database(), indent=2))
