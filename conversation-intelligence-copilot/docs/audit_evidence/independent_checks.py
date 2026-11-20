"""Independent re-computation of the four assignment answers (audit evidence; not part of the app).

Independence: conversation structure, turn order, timestamps, months and text come from the raw
CSV inside data/raw/cs_conversations.csv.zip. Message-level labels (sentiment score, act, empathy,
resolution, opening topic) are read from the app's message_labels table: they are the labelling
step under test elsewhere, not the analytics. Every aggregation, ranking and score below is
re-implemented here with pandas, without importing app.analytics.

Run: backend/.venv/bin/python docs/audit_evidence/independent_checks.py
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "docs" / "audit_evidence"
raw = pd.read_csv(zipfile.ZipFile(ROOT / "data/raw/cs_conversations.csv.zip").open("cs_conversations.csv"))
raw["ts"] = pd.to_datetime(raw["timestamp"])
raw["message_id"] = raw["conv_id"] + "-T" + raw["turn_index"].astype(str).str.zfill(2)
con = duckdb.connect(str(ROOT / "data/processed/analytics.duckdb"), read_only=True)
lab = con.execute("SELECT message_id, act, sentiment, sentiment_score, empathy, resolution, topic FROM message_labels").df()
msgs_db = con.execute("SELECT message_id, masked_text, clean_text, speaker_role, turn_index FROM messages WHERE dataset_source='original'").df()
m = raw.merge(lab, on="message_id", how="left").sort_values(["conv_id", "turn_index"])
out: dict = {"label_join_missing": int(m["sentiment_score"].isna().sum())}

# Conversation-level facts recomputed from scratch.
start = m.groupby("conv_id")["ts"].min()
cust = m[m["role"] == "customer"]
mean_score = cust.groupby("conv_id")["sentiment_score"].mean()
opening_topic = m[m["turn_index"] == 0].set_index("conv_id")["topic"]
conv = pd.DataFrame({"start": start, "mean": mean_score, "topic": opening_topic})
conv["negative"] = conv["mean"] <= -0.25  # documented rule (README / topics.NEGATIVE_RULE)
conv["month"] = conv["start"].dt.to_period("M").astype(str)
TOPIC_LABEL = dict(con.execute("SELECT DISTINCT topic, topic_label FROM conversations").fetchall())

# ---------------- Q1 ----------------
last = conv["month"].max()
q = conv[conv["month"] == last]
by = q.groupby("topic").agg(conversations=("negative", "size"), negative=("negative", "sum")).reset_index()
by["name"] = by["topic"].map(TOPIC_LABEL)
top5 = by.sort_values(["negative", "name"], ascending=[False, True]).head(5)
r1 = json.loads((EV / "q1_response.json").read_text())
app_rows = r1["rankings"]
out["q1"] = {
    "last_month_independent": last, "app_window": r1["dataset_scope"]["window"]["label"],
    "conversations_in_month": int(len(q)), "negative_in_month": int(q["negative"].sum()),
    "top5_independent": [(r["name"], int(r["negative"]), int(r["conversations"])) for _, r in top5.iterrows()],
    "top5_app": [(r["name"], int(r["negative"]), int(r["conversations"])) for r in app_rows],
}
out["q1"]["match"] = out["q1"]["top5_independent"] == out["q1"]["top5_app"]
nxt = by.sort_values(["negative", "name"], ascending=[False, True]).iloc[4:7]
out["q1"]["rank5_tie_check"] = [(r["name"], int(r["negative"])) for _, r in nxt.iterrows()]

# ---------------- Q2 ----------------
rows = []
for cid, g in m.groupby("conv_id", sort=False):
    g = g.sort_values("turn_index")
    neg_turns = empathic = 0
    turns = g.to_dict("records")
    for i, t in enumerate(turns):
        if t["role"] == "customer" and t["sentiment"] == "negative":
            nxt_agent = next((u for u in turns[i + 1:] if u["role"] == "agent"), None)
            if nxt_agent is not None:
                neg_turns += 1
                empathic += int(bool(nxt_agent["empathy"]))
    res = [t["resolution"] for t in turns if t["role"] == "agent" and isinstance(t["resolution"], str)]
    rows.append({"conv_id": cid, "agent": g["agent_name"].iloc[0], "neg_turns": neg_turns, "empathic": empathic, "final_res": res[-1] if res else None,
                 "topic": g["topic"].iloc[0]})
cq = pd.DataFrame(rows)
RELEVANT = {"duplicate_charge": {"refund_issued", "escalated"}, "payment_not_reflected": {"service_activated", "refund_issued", "escalated"},
            "coupon_not_applied": {"coupon_applied", "escalated"}, "not_received": {"out_for_delivery", "refund_issued", "escalated"},
            "app_crash": {"service_activated", "account_reset", "escalated"}, "account_locked": {"account_reset", "escalated"},
            "service_malfunction": {"service_activated", "account_reset", "escalated"}}  # copied from ASSUMPTIONS.md / taxonomy
cq["misfit"] = [None if (fr is None or t not in RELEVANT) else float(fr not in RELEVANT[t]) for fr, t in zip(cq["final_res"], cq["topic"])]
cq["missed"] = [None if n == 0 else 1 - e / n for n, e in zip(cq["neg_turns"], cq["empathic"])]
cq["score"] = cq[["missed", "misfit"]].astype(float).mean(axis=1, skipna=True) * 100
per_agent = cq.groupby("agent")["conv_id"].nunique()
queue = cq.sort_values(["score", "neg_turns", "conv_id"], ascending=[False, False, True]).head(3)
r2 = json.loads((EV / "q2_response.json").read_text())
out["q2"] = {
    "negative_turns_with_reply": int(cq["neg_turns"].sum()), "empathic_replies": int(cq["empathic"].sum()),
    "assessable_resolutions": int(cq["misfit"].notna().sum()), "misfit_resolutions": int(cq["misfit"].fillna(0).sum()),
    "agents": int(len(per_agent)), "max_conversations_per_agent": int(per_agent.max()), "agents_with_3plus": int((per_agent >= 3).sum()),
    "top3_queue_independent": queue["conv_id"].tolist(), "app_answer_excerpt": r2["answer"][:400],
}
db_rep = con.execute("SELECT conversation_id, repeated_agent_phrases FROM conversations WHERE dataset_source='original'").df().set_index("conversation_id")["repeated_agent_phrases"]
mm = msgs_db.merge(lab[["message_id", "resolution"]], on="message_id")
ag = mm[(mm["speaker_role"] == "agent") & ~mm["resolution"].apply(lambda v: isinstance(v, str))]
ag = ag.assign(conv_id=ag["message_id"].str[:8])
rep = ag.groupby("conv_id")["clean_text"].apply(lambda s: int((s.value_counts() - 1).clip(lower=0).sum()))
rep = rep.reindex(db_rep.index, fill_value=0)
out["q2"]["repeated_phrases"] = {"conversations_with_repeat_independent": int((rep > 0).sum()), "db_column_with_repeat": int((db_rep > 0).sum()),
                                 "rows_disagreeing": int((rep != db_rep).sum()), "original_conversations": int(len(db_rep))}

# ---------------- Q3 ----------------
r3 = json.loads((EV / "q3_response.json").read_text())
cid = "C0000479"
g = m[m["conv_id"] == cid].sort_values("turn_index")
dbm = msgs_db[msgs_db["message_id"].str.startswith(cid)].set_index("message_id")
text_ok = all(str(raw_t).startswith(str(dbm.loc[mid, "clean_text"]).strip()) for mid, raw_t in zip(g["message_id"], g["text"]))
c = g[g["role"] == "customer"].reset_index(drop=True)
deltas = c["sentiment_score"].diff()
tps = [(int(c.loc[i, "turn_index"]), round(float(deltas[i]), 2)) for i in range(1, len(c)) if abs(deltas[i]) >= 0.8]
traj = next(x for x in r3["charts"] if x["chart_id"] == "sentiment_trajectory")
out["q3"] = {
    "conversation_exists_in_raw": bool(len(g)), "raw_messages": int(len(g)), "customer_messages": int(len(c)),
    "clean_text_is_prefix_of_raw_text": text_ok, "turn_order_from_turn_index": g["turn_index"].tolist() == sorted(g["turn_index"].tolist()),
    "timestamps_monotonic_in_raw": bool(g["ts"].is_monotonic_increasing),
    "turning_points_independent": tps,
    "app_trajectory_points": [(int(p["turn_index"]), p["sentiment_score"]) for p in traj["data"]],
    "independent_customer_scores": [(int(t), float(s)) for t, s in zip(c["turn_index"], c["sentiment_score"])],
    "evidence_message_ids": [mid for e in r3["evidence"] for mid in e["message_ids"]],
}
out["q3"]["trajectory_match"] = out["q3"]["app_trajectory_points"] == out["q3"]["independent_customer_scores"]

# ---------------- Q4 ----------------
r4 = json.loads((EV / "q4_response.json").read_text())
cv = cq.set_index("conv_id").drop(columns=["topic"]).join(conv)
last_cust = m[m["role"] == "customer"].groupby("conv_id").tail(1).set_index("conv_id")["sentiment"]
esc = m[(m["role"] == "customer") & (m["act"] == "escalation_request")].groupby("conv_id").size()
cv["ends_negative"] = last_cust.reindex(cv.index).eq("negative")
cv["esc"] = esc.reindex(cv.index).fillna(0)
t = cv.groupby("topic").agg(conversations=("negative", "size"), negative_rate=("negative", "mean"), escalation_rate=("esc", "mean"),
                            unresolved_rate=("ends_negative", "mean"), resolution_misfit_rate=("misfit", "mean")).reset_index()
t["resolution_misfit_rate"] = t["resolution_misfit_rate"].fillna(0.0)
mon = cv.groupby(["topic", "month"]).size().unstack(fill_value=0)
latest = conv["month"].max()
prev = str(pd.Period(latest, "M") - 1)
t["trend"] = [(mon.loc[k, latest] - mon.loc[k, prev]) / mon.loc[k, prev] if mon.loc[k, prev] else 0.0 for k in t["topic"]]
t["frequency"] = t["conversations"]
W = {"frequency": 0.30, "negative_rate": 0.25, "escalation_rate": 0.15, "unresolved_rate": 0.15, "resolution_misfit_rate": 0.10, "trend": 0.05}
for k in W:
    lo, hi = t[k].min(), t[k].max()
    t[f"n_{k}"] = 0.5 if hi == lo else (t[k] - lo) / (hi - lo)
t["score"] = 100 * sum(W[k] * t[f"n_{k}"] for k in W)
t["name"] = t["topic"].map(TOPIC_LABEL)
ind = t.sort_values("score", ascending=False)
out["q4"] = {
    "independent_ranking": [(r["name"], round(float(r["score"]), 1), int(r["conversations"])) for _, r in ind.iterrows()],
    "app_ranking": [(r["name"], r["priority_score"], int(r["conversations"])) for r in r4["rankings"]],
}
out["q4"]["order_match"] = [x[0] for x in out["q4"]["independent_ranking"][: len(out["q4"]["app_ranking"])]] == [x[0] for x in out["q4"]["app_ranking"]]
out["q4"]["max_score_diff"] = max(abs(a[1] - b[1]) for a, b in zip(out["q4"]["independent_ranking"], out["q4"]["app_ranking"]))

(EV / "independent_checks_result.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
print(json.dumps(out, indent=1, default=str))

if __name__ == "__main__":
    print(t[t["topic"] == "payment_not_reflected"][["conversations", "negative_rate", "escalation_rate", "unresolved_rate", "resolution_misfit_rate", "trend"]].to_dict("records"))
