"""Prompt-injection detection. Document and user text is DATA: detections are flagged and audited,
and nothing in this module (or anywhere else) lets text alter permissions, scope or tool allowlists."""

from __future__ import annotations

import re

INJECTION_PATTERNS = [
    r"ignore (all |any |your |previous |prior )*(instructions|rules|policies|guardrails)",
    r"disregard (all |any |your |the )*(instructions|rules|policy|policies)",
    r"you are now (authori[sz]ed|allowed|permitted|in developer mode)",
    r"bypass (the )?(ethical wall|access control|security|policy|guardrails?)",
    r"retrieve (all |the )?(confidential|privileged|restricted) (files|documents)",
    r"(system prompt|developer message)",
    r"act as (an? )?(administrator|admin|root|partner)",
    r"override (the )?(policy|permissions|rbac|restrictions)",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def detect_injection(text: str) -> list[str]:
    if not text:
        return []
    return [p.pattern for p in _COMPILED if p.search(text)]


def wrap_as_data(text: str, source_id: str) -> str:
    """Delimit untrusted content before it is ever placed in an LLM prompt (live mode)."""
    safe = text.replace("</untrusted_document>", "")
    return f'<untrusted_document source="{source_id}">\n{safe}\n</untrusted_document>'
