"""Hybrid intent router for the Flying_Florina four-question engine.

Same methodology as the Conversation Intelligence Copilot, adapted to aerospace:

  1. policy      exfiltration and prompt-injection attempts are caught first and can never be outscored
  2. greeting    short social messages
  3. follow-up   short questions that refer back ("that", "it", "what about AC-118?") reuse the session context
  4. rules       high-precision weighted patterns for the four families (Q1-Q4) and the existing workflows
  5. semantic    TF-IDF cosine to the labelled tuning examples (fixtures/eval/four_questions_dev.json);
                 accepted only above a similarity threshold with a margin over the runner-up label
  6. qwen        the local Qwen model picks a label from a closed set (validated JSON), only when 1-5 are unsure
  7. fallback    general aviation knowledge, unsupported (off-domain) or a clarification request

Entities (aircraft, parts, hours, months) always come from deterministic extractors. Similarities are ranking
scores, not probabilities, and are never shown as confidence. The held-out test split is never read here.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any

from pydantic import BaseModel

from app.core.config import FIXTURES_DIR
from app.workflows.intent import EMAIL, EXPORT_DEST, EXPORT_VERB, classify

FAMILIES = {
    "diagnostics": {"workflow": "aircraft_diagnostics", "title": "Aircraft Diagnostics"},
    "recovery": {"workflow": "aircraft_recovery", "title": "Aircraft Recovery"},
    "modernization": {"workflow": "legacy_assessment", "title": "Legacy Modernization"},
    "executive": {"workflow": "executive_readiness", "title": "Executive Intelligence"},
}
OTHER_WORKFLOWS = {"scenario_compare", "governance_review", "document_freshness", "bridge_generation", "downtime_analysis", "parts_status",
                   "executive_pitch", "quality_investigation", "fleet_overview", "maintenance_investigation", "recovery_options", "legacy_assessment"}
CONVERSATIONAL = {"greeting", "general_knowledge", "unsupported", "clarify", "policy_refusal", "data_export"}

FAMILY_RULES: dict[str, list[tuple[str, float]]] = {
    "diagnostics": [(r"\bvibrat", 2.5), (r"\banomal", 2), (r"\bsensor\b|\bdropout\b|telemetry", 1.5), (r"\bdiagnos", 2.5), (r"\babnormal\b", 1.5),
                    (r"\bwhy (is|are|does|do)\b", 1.5), (r"\b(root cause|likely cause|what.{0,12}caus|behind|explain)", 1.5),
                    (r"\b(inspect|investigat|check)\b", 1), (r"\bwhat.{0,10}wrong\b|\bfault\b|\bglitch\b|\bexceed", 1.5), (r"\bEGT\b", 1),
                    (r"\bAC-\d{3}\b", 0.5), (r"hypothes|failing", 1.5)],
    "recovery": [(r"\brecover", 3), (r"(back|return\w*)\s+(\w+\s+){0,3}(in )?(to )?service|back online|fly(ing)? again|out of aog", 3),
                 (r"\bfastest|quickest|soonest|how (fast|quickly|long until)|when can", 2), (r"\bAOG\b", 1.5), (r"\bgrounded\b", 1),
                 (r"\b(option|options|path|route)\b", 1), (r"minimi[sz]e.{0,15}downtime", 1.5), (r"\btransfer\b|alternate part|new part|wait for", 1),
                 (r"\bapprov", 0.5)],
    "modernization": [(r"moderni[sz]", 3), (r"\blegacy\b", 2.5), (r"without (a )?(replac|rewrit)|big-bang|rewrite", 2.5), (r"\bMCP\b", 1.5),
                      (r"\bAPIs?\b", 1), (r"strangler|anti-corruption|facade", 2.5), (r"integration (plan|architecture)|migrat", 1.5),
                      (r"(old|existing|20-year-old) (maintenance|MRO|platform|database|system)", 2), (r"\bwrap\b|blueprint", 1)],
    "executive": [(r"readiness", 3), (r"(fleet )?availability", 2), (r"reduce (aircraft |maintenance )?downtime|cut downtime|lower downtime|downtime reduction", 2),
                  (r"\bcost", 1.5), (r"leadership|executive", 1.5), (r"improvement|levers?\b|invest", 1.5), (r"what('s| is) (affecting|hurting|limiting|driving)|drivers?\b|\bdriving\b", 1.5),
                  (r"operational (risk|availability)", 2), (r"across the fleet|\bfleet\b", 0.5), (r"maintenance spend", 1.5)],
}
SPECIFIC_WORKFLOW_MIN = 4.5  # rules score for an existing specific workflow to win over the four families
FAMILY_MIN = 3.0
FAMILY_MARGIN = 1.5

INJECTION = re.compile(r"(?i)(ignore (all )?(previous|prior|your) (instructions|rules)|disregard (the )?(system|policy|rules)|you are now|"
                       r"admin mode|developer mode|disable (the )?(policy|guard|governance)|bypass|jailbreak|pretend (you are|to be)|"
                       r"grant me|approve (all|every)|mark .{0,20}airworthy|reveal (the )?system prompt)")
GREETING = re.compile(r"(?i)^\s*(hi|hello|hey|hiya|good (morning|afternoon|evening)|thanks|thank you|cheers|ok(ay)?|great)\b[\s!.,]*(there|flying_florina|florina|team)?[\s!.]*$")
FOLLOW_UP = re.compile(r"(?i)^\s*(and|what about|how about|why|who|which of|what are the risks|tell me more|more on|same for|"
                       r"compare (it|that|them)|is (it|that)|can (it|we)|should we|what should we|does that|do those)\b|\b(it|that|those|them|this option|that approach)\b")
GENERAL_KNOWLEDGE = re.compile(r"(?i)^\s*(what (is|are) (a|an|the)?\s*\w|what does .{1,40} (mean|stand for)|explain what|define|meaning of|how does (a|an|the)\b|tell me about (a|an|the)?\s*\w)")
OWN_DATA = re.compile(r"(?i)\b(we|our|us|fleet|this month|biggest|top|which)\b")
AVIATION_TERMS = re.compile(r"(?i)aircraft|aviation|engine|borescope|aog|mro|egt|isolator|maintenance|airworth|mtbf|mean time|predictive|"
                            r"mcp|api|fleet|avionics|rotor|hangar|jet|turbine|reliability|inspection")
VAGUE = re.compile(r"(?i)^\s*(what about it|can you check that|do the thing.*|tell me more|and then|and\?|more|why\?|ok so\??)[\s.?!]*$")

_WORD = re.compile(r"[a-z0-9]+")
STOP = set("a an the and or of to in on for with is are was were be do does did can could would should will what which how why who "
           "it this that these those me my we our us you your i at by from as about into than then there their they its so".split())


def _norm(q: str) -> str:
    q = re.sub(r"\bAC-\d{3}\b", " aircraft ", q, flags=re.I)
    q = re.sub(r"\bP-\d{3,5}[A-Z]?\b", " part ", q, flags=re.I)
    q = re.sub(r"\bDOC-\d{3}\b", " document ", q, flags=re.I)
    return q.lower()


def _stem(w: str) -> str:
    for suf in ("ization", "ations", "ation", "izing", "ising", "ings", "ing", "ies", "ied", "ers", "ed", "es", "ly", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _tokens(q: str) -> list[str]:
    ws = [_stem(w) for w in _WORD.findall(_norm(q)) if w not in STOP]
    return ws + [f"{a}_{b}" for a, b in zip(ws, ws[1:], strict=False)]


@dataclass
class _Index:
    labels: list[str]
    vecs: list[dict[str, float]]
    idf: dict[str, float]


@lru_cache(maxsize=1)
def _index() -> _Index:
    data = json.loads((FIXTURES_DIR / "eval" / "four_questions_dev.json").read_text())
    examples = [(it["query"], it["label"]) for it in data["items"] if it["label"] not in {"clarify", "policy_refusal", "data_export"}]
    docs = [Counter(_tokens(q)) for q, _ in examples]
    df = Counter(t for d in docs for t in d)
    n = len(docs)
    idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
    vecs = [_vec(d, idf) for d in docs]
    return _Index([lbl for _, lbl in examples], vecs, idf)


def _vec(counts: Counter, idf: dict[str, float]) -> dict[str, float]:
    v = {t: (1 + math.log(c)) * idf.get(t, 0.0) for t, c in counts.items() if t in idf}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / norm for t, x in v.items()}


SEMANTIC_MIN = 0.34
OFF_DOMAIN_MIN_SIM = 0.6  # an off-domain question must be very close to a labelled example to be routed at all
DOMAIN_TERMS = re.compile(r"(?i)readiness|downtime|vibrat|recover|legacy|moderni|supplier|parts?\b|stock|work orders?|technician|"
                          r"document|policy|policies|approval|scenario|delay|roi|pitch|executive|leadership|nonconform|capa|quality")
SEMANTIC_MARGIN = 0.06


def semantic(query: str) -> list[tuple[str, float]]:
    idx = _index()
    qv = _vec(Counter(_tokens(query)), idx.idf)
    best: dict[str, float] = {}
    for lbl, v in zip(idx.labels, idx.vecs, strict=True):
        s = sum(qv.get(t, 0.0) * x for t, x in v.items())
        if s > best.get(lbl, 0.0):
            best[lbl] = s
    return sorted(((k, round(v, 3)) for k, v in best.items()), key=lambda kv: -kv[1])[:4]


def family_scores(q: str) -> dict[str, float]:
    out = {}
    for fam, pats in FAMILY_RULES.items():
        s = sum(w for p, w in pats if re.search(p, q, re.I))
        if s:
            out[fam] = round(s, 2)
    return out


class QwenLabel(BaseModel):
    label: str
    reason: str = ""


@dataclass
class Route:
    label: str  # a family, an existing workflow, or a conversational label
    workflow: str  # the graph to run, or the conversational label
    family: str | None
    method: str  # policy | greeting | follow_up | rules | semantic | qwen | fallback
    reason: str
    entities: dict[str, Any] = field(default_factory=dict)
    family_scores: dict[str, float] = field(default_factory=dict)
    semantic: list[tuple[str, float]] = field(default_factory=list)
    secondary: str | None = None
    follow_up: bool = False
    intent: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _label_to_route(label: str, method: str, reason: str, intent: dict[str, Any], fs: dict[str, float], sem: list, **kw: Any) -> Route:
    if label in FAMILIES:
        return Route(label, FAMILIES[label]["workflow"], label, method, reason, intent.get("entities", {}), fs, sem, intent=intent, **kw)
    return Route(label, label, None, method, reason, intent.get("entities", {}), fs, sem, intent=intent, **kw)


def route(query: str, context: dict[str, Any] | None = None, use_model: bool = True) -> Route:
    q = (query or "").strip()
    intent = classify(q)
    fs = family_scores(q)
    ranked = sorted(fs.items(), key=lambda kv: -kv[1])
    top, top_s = ranked[0] if ranked else (None, 0.0)
    second_s = ranked[1][1] if len(ranked) > 1 else 0.0

    # 1. policy
    if INJECTION.search(q):
        return _label_to_route("policy_refusal", "policy", "Instruction-override or privilege request detected (POL-011 / POL-007).", intent, fs, [])
    if intent["workflow"] == "data_export" or (EXPORT_VERB.search(q) and (EMAIL.search(q) or EXPORT_DEST.search(q)) and re.search(r"(?i)record|work order|task card|data", q)):
        return _label_to_route("data_export", "policy", "Export to an external or personal destination.", intent, fs, [])
    # 2. greeting
    if GREETING.match(q):
        return _label_to_route("greeting", "greeting", "Greeting.", intent, fs, [])
    # 3. follow-up (needs session context)
    if context and context.get("family") and len(q.split()) <= 12 and FOLLOW_UP.search(q):
        ents = dict(context.get("entities") or {})
        new = intent.get("entities", {})
        for k, v in new.items():
            if v:
                ents[k] = v
        fam = context["family"]
        if top and top_s >= FAMILY_MIN and top != fam:
            fam = top  # "And how fast can we recover it?" switches family but keeps the aircraft
        intent = {**intent, "entities": ents}
        r = _label_to_route(fam, "follow_up", f"Follow-up to the previous {fam} question; entities carried over.", intent, fs, [], follow_up=True)
        return r
    if VAGUE.match(q) or len(_tokens(q)) == 0:
        return _label_to_route("clarify", "fallback", "Too vague to route without context.", intent, fs, [])

    # 4. rules
    specific = intent["workflow"] if intent["workflow"] in OTHER_WORKFLOWS and intent["workflow"] not in ("legacy_assessment",) else None
    specific_s = max(intent.get("scores", {}).values(), default=0)
    secondary = ranked[1][0] if len(ranked) > 1 and second_s >= FAMILY_MIN else None
    overwhelming = specific_s >= top_s + 4  # e.g. "executive modernization pitch": the pitch workflow, not the family
    if specific and specific_s >= SPECIFIC_WORKFLOW_MIN and specific_s >= top_s + 1 and (overwhelming or not _family_specific_cue(q, top)):
        return _label_to_route(specific, "rules", f"Existing workflow rule score {specific_s} vs family {top_s}.", intent, fs, [])
    if top and top_s >= FAMILY_MIN and top_s - second_s >= FAMILY_MARGIN:
        return _label_to_route(top, "rules", f"Family rules {top}={top_s}, runner-up {second_s}.", intent, fs, [], secondary=secondary)
    if top and second_s >= FAMILY_MIN:
        # Multi-intent: two families both clearly present. The one the user asks about first is primary.
        first, other = sorted(ranked[:2], key=lambda kv: _first_match(q, kv[0]))
        return _label_to_route(first[0], "rules", f"Multi-intent: {first[0]} asked first, {other[0]} offered as a follow-up.", intent, fs, [],
                               secondary=other[0])
    entity = any(intent.get("entities", {}).get(k) for k in ("aircraft", "parts"))
    if GENERAL_KNOWLEDGE.match(q) and not entity and not OWN_DATA.search(q) and top_s < FAMILY_MIN and AVIATION_TERMS.search(q):
        return _label_to_route("general_knowledge", "rules", "Definition/explanation question with no fleet entity: general knowledge.", intent, fs, [])

    # 5. semantic
    sem = semantic(q)
    in_domain = bool(AVIATION_TERMS.search(q) or entity or DOMAIN_TERMS.search(q))
    if not in_domain and (not sem or sem[0][1] < OFF_DOMAIN_MIN_SIM):
        return _label_to_route("unsupported", "relevance_gate", "No aerospace or modernization terms and no close labelled example.", intent, fs, sem)
    if sem and sem[0][1] >= SEMANTIC_MIN and (len(sem) == 1 or sem[0][1] - sem[1][1] >= SEMANTIC_MARGIN):
        return _label_to_route(sem[0][0], "semantic", f"Nearest labelled examples: {sem[:2]}", intent, fs, sem, secondary=secondary)
    # Rules agreeing with the semantic leader settle a close call.
    if top and sem and sem[0][0] == top and top_s >= 2:
        return _label_to_route(top, "rules+semantic", f"Rules ({top_s}) and semantic leader agree.", intent, fs, sem, secondary=secondary)

    # 6. local Qwen for the ambiguous remainder
    if use_model:
        r = _qwen_route(q, intent, fs, sem)
        if r:
            return r
    # 7. fallback
    if top and top_s >= 2:
        return _label_to_route(top, "rules_weak", f"Weak family rules {top}={top_s}; nothing stronger.", intent, fs, sem)
    if specific and specific_s >= 2:
        return _label_to_route(specific, "rules_weak", f"Weak workflow rules {specific_s}.", intent, fs, sem)
    if GENERAL_KNOWLEDGE.match(q) and not OWN_DATA.search(q) and AVIATION_TERMS.search(q):
        return _label_to_route("general_knowledge", "fallback", "General aviation/technology question; no fleet data needed.", intent, fs, sem)
    if not AVIATION_TERMS.search(q) and not intent.get("entities", {}).get("aircraft"):
        return _label_to_route("unsupported", "fallback", "Outside Flying_Florina's aerospace and enterprise-modernization scope.", intent, fs, sem)
    return _label_to_route("clarify", "fallback", "In scope but not specific enough to choose a workflow.", intent, fs, sem)


def _first_match(q: str, fam: str) -> int:
    pos = [m.start() for p, _ in FAMILY_RULES[fam] for m in [re.search(p, q, re.I)] if m]
    return min(pos) if pos else 10**6


def _family_specific_cue(q: str, fam: str | None) -> bool:
    """A family question that also matches an existing workflow's words (e.g. 'fastest recovery' + 'compare')."""
    if fam == "recovery" and re.search(r"(?i)recover|return.{0,20}service|fly again", q):
        return True
    if fam == "modernization" and re.search(r"(?i)moderni[sz]|legacy", q) and not re.search(r"(?i)\badapter\b|generate", q):
        return True
    if fam == "diagnostics" and not re.search(r"(?i)\bdraft\b|maintenance plan|work order|\bparts?\b|technicians?", q):
        return True  # "investigate ... and tell engineering what to check" is diagnosis, not planning
    return False


LABELS = list(FAMILIES) + sorted(OTHER_WORKFLOWS - {"legacy_assessment", "recovery_options"}) + ["general_knowledge", "unsupported", "clarify"]


def _qwen_route(q: str, intent: dict[str, Any], fs: dict[str, float], sem: list) -> Route | None:
    from app.llm.gateway import LLMError, LLMUnavailable, gateway

    g = gateway()
    if not g.available():
        return None
    system = ("You route questions for Flying_Florina, an aerospace maintenance intelligence assistant. Choose exactly one label from: "
              + ", ".join(LABELS) + ". diagnostics = why an aircraft behaves abnormally; recovery = fastest way back to service; "
              "modernization = legacy systems, APIs, MCP; executive = fleet readiness, downtime and cost drivers; general_knowledge = "
              "aviation concepts not about this fleet's data; unsupported = off-topic; clarify = too vague. Reply as JSON {\"label\": ..., \"reason\": ...}.")
    try:
        r = g.generate(agent="Intake & Intent Agent", task="intent_classification", system=system, user=q, schema=QwenLabel, max_tokens=60)
    except (LLMError, LLMUnavailable):
        return None
    label = (r.data or {}).get("label", "")
    if label not in LABELS:
        return None
    return _label_to_route(label, "qwen", f"Local Qwen closed-set classification ({r.latency_ms} ms): {(r.data or {}).get('reason', '')[:160]}", intent, fs, sem)
