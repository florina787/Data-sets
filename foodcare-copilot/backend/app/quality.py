"""Quality intelligence overview: aggregates the user's inspection batches, corrections and evaluations.

Every number is computed from stored records. Recommendations are suggestions for people:
rejecting physical product always needs a human decision.
"""

from __future__ import annotations

import json

from app.memory.store import get_store
from app.ml import registry

ACTION = {"Good": "Accept", "Moderate": "Send to review", "Not Good": "Reject candidate · needs approval",
          None: "Re-image (not graded)"}
SEVERITY = {"Not Good": 0, "Moderate": 1, None: 2, "Good": 3}


def overview(username: str, days: int | None = None, supplier: str | None = None) -> dict:
    store = get_store()
    where, params = ["b.username = ?"], [username]
    if days:
        where.append("b.created_at >= datetime('now', ?)")
        params.append(f"-{int(days)} days")
    if supplier:
        where.append("b.supplier = ?")
        params.append(supplier)
    clause = " AND ".join(where)
    batches = store.query(f"SELECT b.id, b.title, b.supplier, b.created_at, b.summary_json FROM inspection_batches b"
                          f" WHERE {clause} ORDER BY b.created_at", tuple(params))
    for b in batches:
        b["summary"] = json.loads(b.pop("summary_json") or "{}")
    rows = store.query(
        f"SELECT p.batch_id, p.potato_no, p.grade AS model_grade, p.corrected_grade, p.detection_score,"
        f" p.reasons_json, p.dark_pct, p.green_pct FROM inspection_potatoes p JOIN inspection_batches b"
        f" ON b.id = p.batch_id WHERE {clause}", tuple(params))
    recs, totals = [], {"Good": 0, "Moderate": 0, "Not Good": 0, "Not graded": 0}
    for r in rows:
        grade = r["corrected_grade"] or r["model_grade"]
        totals[grade or "Not graded"] += 1
        recs.append({"batch_id": r["batch_id"], "potato_no": r["potato_no"], "grade": grade,
                     "top_finding": json.loads(r["reasons_json"])[0] if r["reasons_json"] else "",
                     "score": r["detection_score"], "corrected": r["corrected_grade"] is not None,
                     "action": ACTION.get(grade, ACTION[None])})
    recs.sort(key=lambda x: (SEVERITY.get(x["grade"], 2), -(x["score"] or 0)))
    graded = totals["Good"] + totals["Moderate"] + totals["Not Good"]
    corrections = store.query(
        f"SELECT COUNT(*) AS n FROM inspection_corrections c JOIN inspection_batches b ON b.id = c.batch_id"
        f" WHERE {clause}", tuple(params))[0]["n"]
    queue = sum(1 for r in recs if r["grade"] in ("Moderate", "Not Good") and not r["corrected"])
    evals = registry.evaluations(limit=20)
    detection = next((e for e in evals if e["task"] == "detection+counting"), None)
    grading = next((e for e in evals if e["task"] == "grading"), None)
    suppliers = [r["supplier"] for r in store.query(
        "SELECT DISTINCT supplier FROM inspection_batches WHERE username = ? AND supplier IS NOT NULL"
        " AND supplier != '' ORDER BY supplier", (username,))]
    return {
        "filters": {"days": days, "supplier": supplier, "suppliers": suppliers},
        "totals": {**totals, "graded": graded, "potatoes": len(rows), "batches": len(batches)},
        "trend": [{"batch_id": b["id"], "title": b["title"], "created_at": b["created_at"],
                   "good_pct": b["summary"].get("pct", {}).get("Good"),
                   "not_good_pct": b["summary"].get("pct", {}).get("Not Good"),
                   "detected": b["summary"].get("detected", 0)} for b in batches],
        "recommendations": recs[:40],
        "review": {"queue": queue, "corrections": corrections,
                   "rules_agreement_pct": round(100 * (1 - corrections / graded), 1) if graded else None,
                   "note": "Agreement = share of graded potatoes whose rules grade was not corrected by an inspector."},
        "model_health": {"detection": detection, "grading": grading},
    }
