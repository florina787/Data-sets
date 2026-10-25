"""Print allowlist pins for the registered agent tools (run after a deliberate, reviewed change).

Usage: backend/.venv/bin/python scripts/pin_tools.py > /tmp/pins.yaml   # review, then copy into
fixtures/policies/tool_allowlist.yaml. Pins are never updated automatically.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.tools import tool_specs  # noqa: E402

print(yaml.safe_dump({"tools": [{"name": t.name, "version": t.version, "schema_sha256": t.schema_sha256, "action": t.action} for t in tool_specs()]}, sort_keys=False))
