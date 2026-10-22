"""Permission-aware hybrid retrieval.

1. Authorization pre-filter (before any scoring, so scores cannot leak): tenant, document status, effective/expiry
   dates, access groups and classification clearance.
2. Hybrid retrieval: BM25 keyword scores + hashed-embedding cosine, fused with reciprocal-rank fusion (k=60).
3. Post-filter: every candidate re-checked through the policy engine (`docs:read`) - defence in depth.
4. Rerank: query-term coverage, title/section match, language match, recency.
5. Evidence validation: drop chunks with no query-term or semantic support; neutralize instruction-like text.
Multilingual: query terms are expanded with the approved glossary (data/glossary.yaml)."""
from __future__ import annotations

import math
import threading
from collections import Counter, defaultdict
from datetime import date

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import ROOT
from backend.db import models as m
from governance.identity import Principal
from governance.policy import PolicyEngine, Resource
from retrieval import embed as emb
from retrieval.injection import as_evidence
from retrieval.language import detect_language

ROLE_GROUPS = {
    "executive": {"all-staff", "executive"}, "finance": {"all-staff", "executive"}, "cio": {"all-staff", "investments"},
    "investment_analyst": {"all-staff", "investments"}, "wealth_advisor": {"all-staff", "private-wealth"},
    "external_advisor": {"external-advisors", "public"}, "compliance_officer": {"all-staff", "compliance"},
    "privacy_officer": {"all-staff", "compliance"}, "ai_admin": {"all-staff", "technology"},
}
LEVELS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
STOPWORDS = set("the a an and or of to in on for is are what which why how with by our we did do does from at as be it this that".split())

_glossary = yaml.safe_load((ROOT / "data" / "glossary.yaml").read_text())
_index_lock = threading.Lock()
_index: dict | None = None


def groups_for(p: Principal) -> set[str]:
    g: set[str] = set()
    for r in p.roles:
        g |= ROLE_GROUPS.get(r, set())
    return g


def invalidate_index() -> None:
    global _index
    with _index_lock:
        _index = None


def _load_index(s: Session) -> dict:
    global _index
    with _index_lock:
        if _index is not None:
            return _index
        docs = {d.id: d for d in s.scalars(select(m.Document))}
        chunks = list(s.scalars(select(m.DocChunk)))
        tf, df = {}, Counter()
        for c in chunks:
            toks = [t for t in emb.tokens(f"{docs[c.document_id].title} {c.section} {c.text}") if t not in STOPWORDS]
            tf[c.id] = Counter(toks)
            df.update(set(toks))
        avgdl = sum(sum(v.values()) for v in tf.values()) / max(1, len(tf))
        _index = {"docs": {k: {"id": d.id, "tenant_id": d.tenant_id, "title": d.title, "version": d.version, "classification": d.classification,
                               "access_groups": d.access_groups, "effective_date": d.effective_date, "expiry_date": d.expiry_date,
                               "status": d.status, "language": d.language, "doc_type": d.doc_type, "owner": d.owner,
                               "jurisdiction": d.jurisdiction, "injection_flags": d.injection_flags} for k, d in docs.items()},
                  "chunks": {c.id: {"id": c.id, "doc": c.document_id, "section": c.section, "text": c.text, "emb": c.embedding} for c in chunks},
                  "tf": tf, "df": df, "N": len(chunks), "avgdl": avgdl}
        return _index


def expand_query(q: str) -> tuple[str, str]:
    lang = detect_language(q)
    extra = []
    ql = q.lower()
    for en, tr in _glossary["terms"].items():
        variants = [en] + list(tr.values())
        if any(v.lower() in ql for v in variants):
            extra += variants
    return lang, q + " " + " ".join(extra)


def visible(doc: dict, p: Principal, today: date, include_quarantined: bool = False) -> bool:
    return (doc["tenant_id"] == p.tenant_id and (doc["status"] == "active" or include_quarantined)
            and doc["effective_date"] <= today and (doc["expiry_date"] is None or doc["expiry_date"] >= today)
            and bool(set(doc["access_groups"]) & groups_for(p)) and LEVELS[doc["classification"]] <= LEVELS.get(p.clearance, 0))


def search(s: Session, engine: PolicyEngine, p: Principal, query: str, k: int = 5, today: date | None = None,
           doc_types: list[str] | None = None) -> dict:
    today = today or date.today()
    idx = _load_index(s)
    lang, expanded = expand_query(query)
    q_toks = [t for t in emb.tokens(expanded) if t not in STOPWORDS]
    allowed_docs = {d for d, doc in idx["docs"].items() if visible(doc, p, today) and (not doc_types or doc["doc_type"] in doc_types)}
    cands = [c for c in idx["chunks"].values() if c["doc"] in allowed_docs]
    excluded = len({c["doc"] for c in idx["chunks"].values()}) - len(allowed_docs)
    # BM25
    k1, b = 1.5, 0.75
    bm = {}
    for c in cands:
        tf = idx["tf"][c["id"]]
        dl = sum(tf.values())
        sc = 0.0
        for t in set(q_toks):
            if t in tf:
                idf = math.log(1 + (idx["N"] - idx["df"][t] + 0.5) / (idx["df"][t] + 0.5))
                sc += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * dl / idx["avgdl"]))
        bm[c["id"]] = sc
    qv = emb.embed(expanded)
    from retrieval.vectorstore import mode as vmode, scores as vscores
    cos = vscores(s, qv, cands)
    rrf: dict[str, float] = defaultdict(float)
    for scores in (bm, cos):
        for rank, cid in enumerate(sorted(scores, key=lambda x: -scores[x])):
            rrf[cid] += 1 / (60 + rank + 1)
    pool = sorted(rrf, key=lambda x: -rrf[x])[:25]
    results = []
    doc_ok: dict[str, bool] = {}
    for cid in pool:
        c = idx["chunks"][cid]
        doc = idx["docs"][c["doc"]]
        if doc["id"] not in doc_ok:  # one policy decision per document (not per chunk)
            doc_ok[doc["id"]] = engine.authorize(p, "docs:read", Resource("document", doc["id"], doc["tenant_id"],
                                                                         {"classification": doc["classification"]})).allowed
        if not doc_ok[doc["id"]]:
            continue
        text_toks = set(emb.tokens(f"{doc['title']} {c['section']} {c['text']}"))
        coverage = len(set(q_toks) & text_toks) / max(1, len(set(q_toks)))
        if coverage == 0 and cos[cid] < 0.12:
            continue  # evidence validation: no lexical or semantic support
        rer = rrf[cid] * 60 + 0.6 * coverage + 0.3 * max(0.0, cos[cid]) + (0.15 if doc["language"] == lang else 0.0) \
            + 0.1 * bool(set(q_toks) & set(emb.tokens(doc["title"] + " " + c["section"])))
        results.append({"chunk_id": cid, "document_id": doc["id"], "title": doc["title"], "version": doc["version"], "section": c["section"],
                        "classification": doc["classification"], "language": doc["language"], "doc_type": doc["doc_type"],
                        "owner": doc["owner"], "jurisdiction": doc["jurisdiction"], "effective_date": doc["effective_date"].isoformat(),
                        "text": as_evidence(c["text"]), "score": round(rer, 4), "bm25": round(bm[cid], 4), "cosine": round(cos[cid], 4),
                        "injection_flagged": bool(doc["injection_flags"])})
    results.sort(key=lambda r: -r["score"])
    seen, top = set(), []
    for r in results:
        if (r["document_id"], r["section"]) in seen:
            continue
        seen.add((r["document_id"], r["section"]))
        top.append(r)
        if len(top) == k:
            break
    return {"query": query, "language": lang, "results": top, "candidates_considered": len(cands), "vector_backend": vmode(s),
            "documents_excluded_by_authorization": excluded}


def get_document(s: Session, engine: PolicyEngine, p: Principal, doc_id: str, today: date | None = None) -> dict | None:
    idx = _load_index(s)
    doc = idx["docs"].get(doc_id)
    if doc is None or not visible(doc, p, today or date.today(), include_quarantined=False):
        return None
    if not engine.authorize(p, "docs:read", Resource("document", doc_id, doc["tenant_id"], {"classification": doc["classification"]})).allowed:
        return None
    chunks = sorted([c for c in idx["chunks"].values() if c["doc"] == doc_id], key=lambda c: c["id"])
    return {**{k: (v.isoformat() if isinstance(v, date) else v) for k, v in doc.items()},
            "sections": [{"section": c["section"], "text": as_evidence(c["text"])} for c in chunks]}


def compare_documents(s: Session, engine: PolicyEngine, p: Principal, old_id: str, new_id: str) -> dict:
    """Regulatory/policy change comparison by section (added / removed / changed sentences)."""
    import difflib
    a, b = get_document(s, engine, p, old_id, date(2026, 6, 1)), get_document(s, engine, p, new_id)
    if a is None or b is None:
        raise PermissionError("one or both documents are not accessible")
    sa = {x["section"]: x["text"] for x in a["sections"]}
    sb = {x["section"]: x["text"] for x in b["sections"]}
    changes = []
    for sec in sorted(set(sa) | set(sb)):
        old_s = [x.strip() for x in sa.get(sec, "").split(". ") if x.strip()]
        new_s = [x.strip() for x in sb.get(sec, "").split(". ") if x.strip()]
        diff = list(difflib.ndiff(old_s, new_s))
        changes.append({"section": sec, "status": "added" if sec not in sa else ("removed" if sec not in sb else ("changed" if old_s != new_s else "unchanged")),
                        "added": [d[2:] for d in diff if d.startswith("+ ")], "removed": [d[2:] for d in diff if d.startswith("- ")]})
    return {"old": {"id": a["id"], "version": a["version"], "title": a["title"]}, "new": {"id": b["id"], "version": b["version"], "title": b["title"]},
            "sections": changes, "note": "Automated textual comparison; interpretation requires Compliance review."}
