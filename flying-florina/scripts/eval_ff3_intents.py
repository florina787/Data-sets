"""Score the 3.0 router on fixtures/eval/ff3_intents_test.json (held-out). Writes docs/eval/ff3_intents_test_rules_only.json."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("LLM_ENABLED", "off")

from app.workflows.router import route  # noqa: E402

data = json.loads((ROOT / "fixtures/eval/ff3_intents_test.json").read_text())
rows, ok = [], 0
for it in data["items"]:
    r = route(it["query"], use_model=False)
    good = r.label == it["label"]
    ok += good
    rows.append({"query": it["query"], "gold": it["label"], "pred": r.label, "method": r.method, "correct": good})
fu_ok, fu_n, fu_rows = 0, 0, []
for conv in data["follow_ups"]:
    ctx = None
    for t in conv["turns"]:
        r = route(t["query"], ctx, use_model=False)
        if "expect" in t:
            fu_n += 1
            slots_ok = all(r.entities.get(k) == v for k, v in t["expect"].items())
            good = r.label == t["label"] and slots_ok
            fu_ok += good
            fu_rows.append({"query": t["query"], "gold": t["label"], "pred": r.label, "slots": {k: r.entities.get(k) for k in t["expect"]}, "expect": t["expect"], "correct": good})
        ctx = {"family": r.family, "workflow": r.workflow, "entities": r.entities}
out = {"split": "ff3_intents_test", "items": len(rows), "routing_accuracy": round(ok / len(rows), 4),
       "follow_up_accuracy_with_slots": round(fu_ok / fu_n, 4), "follow_up_turns": fu_n,
       "errors": [r for r in rows if not r["correct"]], "follow_up_errors": [r for r in fu_rows if not r["correct"]],
       "note": "Rules-only (no Qwen). Held-out: written before the rules were run on it; scored once."}
(ROOT / "docs/eval/ff3_intents_test_rules_only.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("items", "routing_accuracy", "follow_up_accuracy_with_slots", "follow_up_turns")}))
for e in out["errors"] + out["follow_up_errors"]:
    print("MISS", e)
