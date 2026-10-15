"""Every suggested prompt shown in the UI must work in deterministic demo mode (no model key)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import ask

PANEL = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "CopilotPanel.tsx"


def ui_prompts() -> list[str]:
    source = PANEL.read_text(encoding="utf-8")
    blocks = re.findall(r"prompts:\s*\[(.*?)\]", source, re.S)
    return [p for block in blocks for p in re.findall(r'"([^"]+)"', block)]


def test_prompt_list_is_found():
    assert len(ui_prompts()) >= 15


@pytest.mark.parametrize("prompt", ui_prompts())
def test_suggested_prompt_works_in_demo_mode(client, H, demo_wb, prompt):
    if prompt == "Undo the last change":
        # needs a prior change: make one first
        run, conv = ask(client, H, demo_wb, "Normalize the Region categories on Sales")
        op = run["result"]["operations"][0]
        client.post(f"/api/operations/{op['id']}/approve", headers=H,
                    json={"expected_version": op["base_version"], "change_set_hash": op["change_set_hash"]})
    run, _ = ask(client, H, demo_wb, prompt)
    result = run["result"]
    assert run["state"] in ("COMPLETED", "AWAITING_APPROVAL"), (prompt, run["error"])
    assert result["type"] in ("answer", "proposal"), (prompt, result["type"], result["text"][:200])
    assert result["intent"] != "help"
