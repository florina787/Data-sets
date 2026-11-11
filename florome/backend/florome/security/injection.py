"""Prompt-injection screening for untrusted text: MCP tool descriptions, tool output, connector logs.

Patterns merge Project A (app/governance/prompt_injection.py) and Project B (app/security/agent_guardrails.py).
This is a heuristic flag, not the primary control. The primary controls are structural:
  * no model output is ever executed; actions come only from a typed, connector-declared catalog;
  * untrusted text is stored and displayed as data and never concatenated into system instructions;
  * flagged MCP tools are quarantined (disabled) until an admin reviews them.
"""

from __future__ import annotations

import re

INJECTION_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"ignore (all |any |the )?(previous|prior|above) (instructions|rules|prompts?)",
        r"disregard (the |your )?(system|previous) (prompt|instructions)",
        r"you are now\b",
        r"(reveal|print|show|output|send) (your|the) (system prompt|instructions|api key|secrets?|credentials?|tokens?)",
        r"<\s*/?\s*(system|assistant|instructions?)\s*>",
        r"(execute|run) (this |the following )?(code|python|shell|bash|sql|command)",
        r"act as (an? )?(admin|administrator|developer|root)",
        r"exfiltrate|send (this|the data|all data) to https?://",
        r"(always|must) (call|invoke|use) (the )?tool",
        r"approval (is )?(not required|already granted)|skip (the )?approval",
        r"\bcurl\s+https?://|\bwget\s+https?://|rm\s+-rf\s",
    ]
]
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")


def scan(text: str) -> list[str]:
    return [p.pattern for p in INJECTION_PATTERNS if p.search(text or "")]


def sanitize(text: str, max_chars: int = 2000) -> str:
    """Strip control and bidi-override characters (hidden-instruction vectors) and bound length."""
    return _CONTROL.sub("", text or "").strip()[:max_chars]
