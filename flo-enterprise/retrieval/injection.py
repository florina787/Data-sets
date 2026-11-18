"""Prompt-injection screening for user input and retrieved content.

Detection is a defence-in-depth signal only: authorization is enforced by the policy engine and tool gateway whether
or not an injection is detected. Retrieved text is always passed to agents as quoted evidence (data), never as
instructions."""
from __future__ import annotations

import re

PATTERNS = [
    (r"(?i)ignore (all |any )?(previous|prior|above) (instructions|rules|prompts)", "override_instructions", 3),
    (r"(?i)disregard (the |all )?(system|previous) (prompt|instructions)", "override_instructions", 3),
    (r"(?i)you are now (in )?(an? )?(admin|administrator|developer|dan|unrestricted)", "role_hijack", 3),
    (r"(?i)(call|invoke|use|run) (the )?[a-z_]+ tool", "tool_invocation_request", 2),
    (r"(?i)export[_ ](all[_ ])?client[_ ]?(data|list|records)?", "data_exfiltration", 3),
    (r"(?i)(send|email|post|upload) (the |all )?(results|data|records|clients?) to", "data_exfiltration", 3),
    (r"(?i)approve all (pending )?approvals", "approval_bypass", 3),
    (r"(?i)(disable|turn off|bypass) (the )?(audit|logging|guardrails?|policy|authorization)", "control_bypass", 3),
    (r"(?i)reveal (the |your )?(system prompt|secrets?|api keys?|credentials)", "secret_exfiltration", 3),
    (r"(?i)(act|pretend) as (the )?(ceo|compliance officer|administrator|another user)", "impersonation", 2),
    (r"(?i)show me (all|every) clients?", "bulk_access", 1),
    (r"(?i)(execute|place) (a )?(trade|order)s?", "trading_request", 2),
]
RX = [(re.compile(p), n, s) for p, n, s in PATTERNS]


def scan_text(text: str) -> dict:
    hits = [{"pattern": n, "severity": s, "match": m.group(0)[:80]} for rx, n, s in RX for m in rx.finditer(text or "")]
    score = max((h["severity"] for h in hits), default=0)
    return {"flagged": score > 0, "severity": {0: "none", 1: "low", 2: "medium", 3: "high"}[score], "hits": hits}


def as_evidence(text: str) -> str:
    """Neutralize instruction-like content for display inside an evidence block."""
    flagged = scan_text(text)
    if not flagged["flagged"]:
        return text
    out = text
    for rx, _, _ in RX:
        out = rx.sub(lambda m: f"[neutralized instruction-like text: '{m.group(0)[:40]}']", out)
    return out
