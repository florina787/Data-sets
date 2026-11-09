"""Semantic spine: measures every agent turn against three graphs.

    Ontology          what things are     entity types (name, acronym, identifier, figure)
    Knowledge graph   what is true        entities and their co-occurrence in your documents
    Context graph     what matters now    the subgraph of entities this turn was given
    Procedural graph  what to do next     the allowed steps of the orchestration, and the path taken
    Agent             acting              the outcome, written back as a trace

Every number is computed deterministically from the turn's real inputs and
output. There is no LLM judge, so the measures are cheap, repeatable and
explainable. They are lexical: a claim counts as supported when the same entity
or figure appears in what the agent was given. That catches invented names and
numbers; it cannot tell whether a supported entity was used correctly.
"""

from __future__ import annotations

import re
from collections import Counter
from itertools import combinations
from typing import Any

# ---------------------------------------------------------------- ontology

ENTITY_TYPES = ("name", "acronym", "identifier", "figure")

_CITE = re.compile(r"\[\d{1,2}\]")
_LIST_MARK = re.compile(r"(?m)^\s*(?:\d{1,2}[.)]|[-*•])\s+")
_CODE_FENCE = re.compile(r"```.*?```", re.S)
_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,9}s?\b")
_IDENT = re.compile(r"\b(?:[a-z][a-z0-9]*_[a-z0-9_]+|[a-z]+[A-Z][A-Za-z0-9]+)\b")
_FIGURE = re.compile(r"(?<![\w.:])(?:\$\s?)?\d[\d,]*(?:\.\d+|:\d{2})?(?:\s?(?:%|ms|gb|mb|kb|tb|k|m|bn|x|tok/s))?(?![\w])", re.I)
_NAME = re.compile(r"\b[A-Z][a-zA-Z0-9]*[a-z0-9][a-zA-Z0-9]*(?:[ -](?:of |for |and )?[A-Z][a-zA-Z0-9]+){0,3}\b")
_SENTENCE_START = re.compile(r"(?:^|[.!?:;]\s+|\n\s*|[\"'(]\s*)$")
_SPACE = re.compile(r"\s+")

# Capitalised words that carry no entity on their own.
_COMMON = {
    "a",
    "an",
    "and",
    "answer",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "here",
    "how",
    "i",
    "if",
    "in",
    "it",
    "its",
    "no",
    "not",
    "note",
    "of",
    "on",
    "or",
    "question",
    "so",
    "source",
    "sources",
    "summary",
    "that",
    "the",
    "then",
    "there",
    "these",
    "this",
    "those",
    "to",
    "use",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "yes",
    "you",
    "your",
    "step",
    "example",
    "first",
    "second",
    "finally",
    "also",
}


def _norm(s: str) -> str:
    return _SPACE.sub(" ", s.strip().lower().replace(",", "")).rstrip(".")


def _clean(text: str) -> str:
    return _LIST_MARK.sub("", _CITE.sub(" ", text))


def extract_entities(text: str) -> dict[str, str]:
    """Entities in ``text`` as {normalised form: ontology type}.

    Code blocks are skipped (their tokens are syntax, not claims). A single
    capitalised word at the start of a sentence is ignored unless it looks like
    a proper term, because sentence case would otherwise make every opener an
    entity.
    """
    text = _clean(_CODE_FENCE.sub(" ", text or ""))
    out: dict[str, str] = {}
    for m in _FIGURE.finditer(text):
        raw = m.group(0)
        digits = re.sub(r"\D", "", raw)
        has_unit = bool(re.search(r"[%$:a-z]", raw, re.I))
        # Bare one-digit numbers are counting words, not claims; years and units are.
        if has_unit or len(digits) >= 2:
            out.setdefault(_norm(raw), "figure")
    for m in _ACRONYM.finditer(text):
        tok = m.group(0)
        if tok.lower() not in _COMMON and not tok.isdigit():
            out.setdefault(_norm(tok.rstrip("s") if tok[:-1].isupper() and tok.endswith("s") else tok), "acronym")
    for m in _IDENT.finditer(text):
        out.setdefault(_norm(m.group(0)), "identifier")
    for m in _NAME.finditer(text):
        phrase = m.group(0)
        words = phrase.split()
        if len(words) == 1:
            w = words[0]
            if w.lower() in _COMMON or w.isupper():
                continue
            at_start = bool(_SENTENCE_START.search(text[: m.start()]))
            proper_shape = any(c.isdigit() for c in w) or any(c.isupper() for c in w[1:])
            if at_start and not proper_shape:
                continue
        else:
            while words and words[0].lower() in _COMMON:
                words = words[1:]
            if not words:
                continue
            phrase = " ".join(words)
        key = _norm(phrase)
        if len(key) >= 3 and key not in out:
            out[key] = "name"
    return out


def ontology(entities: dict[str, str]) -> dict[str, int]:
    c = Counter(entities.values())
    return {t: c.get(t, 0) for t in ENTITY_TYPES}


# ---------------------------------------------------------- knowledge graph


def knowledge_graph(passages: list[str], limit: int = 40) -> dict[str, Any]:
    """Entity co-occurrence graph over passages: what your documents say exists."""
    counts: Counter[str] = Counter()
    kinds: dict[str, str] = {}
    per_passage: list[set[str]] = []
    for p in passages:
        ents = extract_entities(p)
        kinds.update(ents)
        counts.update(ents.keys())
        per_passage.append(set(ents))
    top = {e for e, _ in counts.most_common(limit)}
    edges: Counter[tuple[str, str]] = Counter()
    for ents in per_passage:
        for a, b in combinations(sorted(ents & top), 2):
            edges[(a, b)] += 1
    degree: Counter[str] = Counter()
    for (a, b), _w in edges.items():
        degree[a] += 1
        degree[b] += 1
    nodes = [{"id": e, "type": kinds[e], "count": counts[e], "degree": degree[e]} for e, _ in counts.most_common(limit)]
    return {
        "nodes": nodes,
        "edges": [{"a": a, "b": b, "weight": w} for (a, b), w in edges.most_common(limit * 3)],
        "ontology": ontology({e: kinds[e] for e in counts}),
        "entities": len(counts),
        "passages": len(passages),
    }


# ---------------------------------------------------------- procedural graph

# The orchestration as a procedural graph: (step -> allowed next steps).
# Steps up to "compose" are LangGraph nodes; generate and govern run in the
# engine; the last three are outcomes.
PROCEDURE: dict[str, list[str]] = {
    "start": ["supervisor"],
    "supervisor": ["screen_prep", "retrieve", "compose"],
    "screen_prep": ["retrieve", "compose"],
    "retrieve": ["compose"],
    "compose": ["generate"],
    "generate": ["govern", "cancelled"],
    "govern": ["resolved", "flagged", "escalated"],
}
OUTCOMES = ("resolved", "flagged", "escalated", "cancelled", "failed")
STEP_LABELS = {
    "supervisor": "Route",
    "screen_prep": "Read screen",
    "retrieve": "Retrieve",
    "compose": "Compose",
    "generate": "Generate",
    "govern": "Govern",
}


def expected_path(has_image: bool, needs_retrieval: bool) -> list[str]:
    path = ["supervisor"]
    if has_image:
        path.append("screen_prep")
    if needs_retrieval:
        path.append("retrieve")
    return [*path, "compose", "generate", "govern"]


def transitions(path: list[str], outcome: str) -> list[tuple[str, str]]:
    seq = ["start", *path, outcome]
    return list(zip(seq, seq[1:], strict=False))


def unbacked_flag(knowledge: dict[str, Any], sources: list[str] | None = None) -> dict[str, str] | None:
    """A governance flag when an answer built on given material states figures,
    or mostly names, that the material does not contain.

    When a screen is the only material, explanations legitimately name things
    that are not visible ("Python", "dictionary"), which made every screen
    explanation flagged in evaluation; there, only unbacked figures count."""
    rate = knowledge.get("support_rate")
    if rate is None or not knowledge.get("unsupported"):
        return None
    figures = knowledge.get("unsupported_figures", 0)
    grounding = {s for s in (sources or []) if s in GROUNDING_SOURCES}
    if grounding == {"screen"} and figures == 0:
        return None
    if figures == 0 and rate >= 0.5:
        return None
    shown = ", ".join(knowledge["unsupported"][:5])
    return {"kind": "unbacked_claims", "detail": f"the answer states things not found in what VEENA was given: {shown}"}


def classify_outcome(gov: dict | None, cancelled: bool, failed: bool = False) -> str:
    if failed:
        return "failed"
    if cancelled:
        return "cancelled"
    kinds = {f["kind"] for f in (gov or {}).get("flags", [])}
    if "no_evidence" in kinds:
        return "escalated"  # nothing matched: the agent hands the decision back to the user
    return "flagged" if kinds else "resolved"


# ------------------------------------------------------------ per-turn score

GROUNDING_SOURCES = ("transcript", "screen", "documents", "resume", "job")


def measure_turn(
    *,
    question: str,
    answer: str,
    context_blocks: dict[str, str],
    evidence: list[dict],
    cited: list[int],
    path: list[str],
    has_image: bool,
    needs_retrieval: bool,
    outcome: str,
) -> dict[str, Any]:
    """Scores one turn along the spine. ``context_blocks`` maps a source kind
    (question, history, transcript, screen, documents, resume, job) to the text
    the agent was given from it."""
    blocks = {k: v for k, v in context_blocks.items() if v and v.strip()}
    blocks.setdefault("question", question)
    corpus = _norm(_clean(" \n ".join(blocks.values())))

    # Knowledge: are the answer's entities and figures backed by what it was given?
    claims = extract_entities(answer)
    supported = [e for e in claims if e in corpus]
    unsupported = [e for e in claims if e not in corpus]
    # Only material the agent was handed counts as grounding. Without it, an
    # entity missing from the question says nothing about invention: the model
    # may simply know it, so no rate is reported.
    grounding_given = any(k in GROUNDING_SOURCES for k in blocks)
    knowledge = {
        "claims": len(claims),
        "supported": len(supported),
        "support_rate": round(len(supported) / len(claims), 4) if claims and grounding_given else None,
        "unsupported": unsupported[:8],
        "unsupported_figures": sum(1 for e in unsupported if claims[e] == "figure"),
        "grounded_context": grounding_given,
        "ontology": ontology(claims),
    }

    # Context: the scoped subgraph of entities this turn was given, and how much of it was used.
    units = [e.get("text", "") for e in evidence] or []
    units += [v for k, v in blocks.items() if k != "documents"]
    per_unit = [set(extract_entities(u)) for u in units]
    ctx_nodes: Counter[str] = Counter()
    for s in per_unit:
        ctx_nodes.update(s)
    ans_norm = _norm(_clean(answer))
    used = {e for e in ctx_nodes if e in ans_norm}
    top = [e for e, _ in ctx_nodes.most_common(24)]
    edges: Counter[tuple[str, str]] = Counter()
    for s in per_unit:
        for a, b in combinations(sorted(s & set(top)), 2):
            edges[(a, b)] += 1
    retrieved = len(evidence)
    n_cited = len(set(cited))
    context = {
        "sources": sorted(blocks),
        "nodes": len(ctx_nodes),
        "edges": len(edges),
        "used": len(used),
        "utilization": round(len(used) / len(ctx_nodes), 4) if ctx_nodes else None,
        "evidence_retrieved": retrieved,
        "evidence_cited": n_cited,
        "citation_rate": round(n_cited / retrieved, 4) if retrieved else None,
        "graph": {
            "nodes": [{"id": e, "used": e in used, "count": ctx_nodes[e]} for e in top],
            "edges": [{"a": a, "b": b, "weight": w} for (a, b), w in edges.most_common(40)],
        },
    }

    # Procedure: did the agent take the steps its inputs call for?
    exp = expected_path(has_image, needs_retrieval)
    trans = transitions(path, outcome)
    # A failure may stop the procedure at any step; every other move must be an allowed edge.
    legal = all(b in PROCEDURE.get(a, []) or b == "failed" for a, b in trans)
    completed = path[: len(exp)] == exp if outcome != "cancelled" else path == exp[: len(path)]
    procedure = {
        "path": path,
        "expected": exp,
        "adherent": bool(legal and completed),
        "legal_transitions": legal,
        "steps": len(path),
        "outcome": outcome,
    }
    return {"knowledge": knowledge, "context": context, "procedure": procedure}
