"""Meeting agent: notes, decisions and action items from an authorised transcript."""

from __future__ import annotations

import json
from typing import Any

from ..llm.ollama import OllamaClient
from ..security.prompt_guard import SECURITY_PREAMBLE, wrap_untrusted

PROMPT = (
    "You write faithful meeting notes from a transcript. Include only what the transcript supports. "
    "If an owner or due date is not stated, use null. Return JSON only: "
    '{"summary": string, "key_points": [string], "decisions": [string], '
    '"action_items": [{"owner": string|null, "task": string, "due": string|null}], "open_questions": [string]}'
)

MERGE_PROMPT = "Merge these partial meeting notes (JSON objects) into one, removing duplicates. Same JSON schema. Return JSON only."


def _chunks(lines: list[str], max_chars: int) -> list[str]:
    out, cur = [], ""
    for line in lines:
        if len(cur) + len(line) + 1 > max_chars and cur:
            out.append(cur)
            cur = ""
        cur += line + "\n"
    if cur:
        out.append(cur)
    return out


def _parse(raw: str) -> dict[str, Any]:
    s, e = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[s : e + 1]) if s != -1 and e != -1 else {}
    items = []
    for a in data.get("action_items", []) or []:
        if isinstance(a, dict) and a.get("task"):
            items.append({"owner": a.get("owner"), "task": str(a["task"]), "due": a.get("due")})
        elif isinstance(a, str):
            items.append({"owner": None, "task": a, "due": None})
    return {
        "summary": str(data.get("summary", "")),
        "key_points": [str(x) for x in data.get("key_points", []) or []],
        "decisions": [str(x) for x in data.get("decisions", []) or []],
        "action_items": items,
        "open_questions": [str(x) for x in data.get("open_questions", []) or []],
    }


async def summarize(llm: OllamaClient, model: str, transcript_lines: list[str], max_chars: int = 6000) -> dict[str, Any]:
    if not transcript_lines:
        return _parse("{}") | {"chunks": 0}
    parts = _chunks(transcript_lines, max_chars)
    partials = []
    for p in parts:
        raw = await llm.chat(
            model,
            [
                {"role": "system", "content": PROMPT + "\n\n" + SECURITY_PREAMBLE},
                {"role": "user", "content": wrap_untrusted("transcript", p)},
            ],
            fmt="json",
            options={"temperature": 0.1, "num_predict": 900},
        )
        partials.append(_parse(raw))
    if len(partials) == 1:
        return partials[0] | {"chunks": 1}
    raw = await llm.chat(
        model,
        [{"role": "system", "content": MERGE_PROMPT}, {"role": "user", "content": json.dumps(partials)[:12000]}],
        fmt="json",
        options={"temperature": 0.1, "num_predict": 1200},
    )
    return _parse(raw) | {"chunks": len(parts)}


def to_markdown(notes: dict[str, Any]) -> str:
    out = ["## Summary", "", notes.get("summary") or "_No summary._", ""]
    for title, key in (("Key points", "key_points"), ("Decisions", "decisions"), ("Open questions", "open_questions")):
        if notes.get(key):
            out += [f"## {title}", "", *[f"- {x}" for x in notes[key]], ""]
    if notes.get("action_items"):
        out += ["## Action items", "", "| Owner | Task | Due |", "|---|---|---|"]
        out += [f"| {a.get('owner') or '—'} | {a['task']} | {a.get('due') or '—'} |" for a in notes["action_items"]]
    return "\n".join(out)
