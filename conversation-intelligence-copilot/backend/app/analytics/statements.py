"""Top-N customer statements by sentiment: what customers actually said, ranked by an explicit rule.

Only customer-authored messages are considered, using the sentiment label assigned to every message at
ingestion (no model at query time). Identical statements are grouped on their PII-masked text. Ranking:
  * frequency (default): most mentions first, then strongest sentiment, then text (stable order);
  * strength: strongest sentiment first (highest score for positive, lowest for negative), then mentions.
Every item carries real message IDs as evidence. When fewer distinct statements exist than requested, the
actual number is returned and the shortfall is stated; nothing is padded or invented.
"""

from __future__ import annotations

from app.analytics.db import AnalyticsDB, where
from app.analytics.topics import _rows
from app.schemas.analysis import AnalysisResult, Metric, Scope, Table

EXAMPLES_PER_ITEM = 3


def top_statements(db: AnalyticsDB, scope: Scope, polarity: str = "positive", top_n: int = 5, rank_by: str = "frequency") -> AnalysisResult:
    w, p = where(scope)
    direction = "DESC" if polarity == "positive" else "ASC"
    order = (f"mentions DESC, mean_score {direction}, statement" if rank_by == "frequency"
             else f"mean_score {direction}, mentions DESC, statement")
    base = f"""FROM messages m JOIN message_labels l USING (message_id) JOIN conversations c ON c.conversation_id = m.conversation_id
               WHERE {w} AND m.speaker_role = 'customer' AND l.sentiment = ?"""
    df = db.query(
        f"""SELECT m.masked_text AS statement, COUNT(*) AS mentions, COUNT(DISTINCT m.conversation_id) AS conversations,
                   ROUND(AVG(l.sentiment_score), 3) AS mean_score,
                   list(m.message_id ORDER BY m.message_id)[1:{EXAMPLES_PER_ITEM}] AS example_message_ids,
                   list(m.conversation_id ORDER BY m.message_id)[1:{EXAMPLES_PER_ITEM}] AS example_conversation_ids
            {base} GROUP BY m.masked_text ORDER BY {order} LIMIT ?""", [*p, polarity, top_n])
    totals = db.query(f"SELECT COUNT(*) AS messages, COUNT(DISTINCT m.masked_text) AS distinct_statements {base}", [*p, polarity])
    all_customer = db.query(
        f"""SELECT COUNT(*) AS n FROM messages m JOIN conversations c ON c.conversation_id = m.conversation_id
            WHERE {w} AND m.speaker_role = 'customer'""", p)
    n_msgs, n_distinct = int(totals["messages"].iloc[0]), int(totals["distinct_statements"].iloc[0])
    n_customer = int(all_customer["n"].iloc[0])
    if df.empty:
        return AnalysisResult(operation="top_statements", params={"polarity": polarity, "top_n": top_n, "rank_by": rank_by}, scope=scope,
                              status="insufficient_data", uncertainty_notes=[f"No {polarity} customer statements in scope."])
    df.insert(0, "rank", range(1, len(df) + 1))
    df["share_of_polarity"] = (df["mentions"] / n_msgs).round(4)
    unc = []
    if n_distinct < top_n:
        unc.append(f"Only {n_distinct} distinct {polarity} customer statement{'s' if n_distinct != 1 else ''} exist in scope, so "
                   f"{n_distinct} {'are' if n_distinct != 1 else 'is'} shown rather than {top_n}. The dataset is generated from message "
                   "templates, so customers repeat a small set of phrasings.")
    unc.append("Sentiment labels come from a documented template mapping applied to every message at ingestion (see ASSUMPTIONS.md); "
               "they are not human-validated.")
    evidence = [mid for ids in df["example_message_ids"] for mid in list(ids)[:1]]
    rule = ("most frequent first (ties: strongest sentiment)" if rank_by == "frequency" else
            f"strongest {polarity} sentiment first (ties: most frequent)")
    return AnalysisResult(
        operation="top_statements", params={"polarity": polarity, "top_n": top_n, "rank_by": rank_by}, scope=scope,
        metrics=[Metric(id="statements_returned", label=f"{polarity.title()} statements shown", value=len(df), unit="count"),
                 Metric(id="distinct_statements", label=f"Distinct {polarity} statements", value=n_distinct, unit="count"),
                 Metric(id="polarity_messages", label=f"{polarity.title()} customer messages", value=n_msgs, unit="count"),
                 Metric(id="polarity_share", label=f"Share of customer messages that are {polarity}", value=round(n_msgs / n_customer, 4) if n_customer else None,
                        unit="percent", numerator=n_msgs, denominator=n_customer)],
        table=Table(columns=["rank", "statement", "mentions", "conversations", "mean_score", "share_of_polarity", "example_message_ids",
                             "example_conversation_ids"],
                    rows=_rows(df.assign(example_message_ids=df["example_message_ids"].map(list),
                                         example_conversation_ids=df["example_conversation_ids"].map(list)))),
        evidence_refs=evidence,
        method_notes=[f"Customer-authored messages labelled {polarity}, grouped on identical (PII-masked) text and ranked {rule}.",
                      "Statements are quoted from real messages; each lists example message IDs that open the source transcript."],
        uncertainty_notes=unc,
        coverage={"customer_messages": n_customer, "polarity_messages": n_msgs, "distinct_statements": n_distinct},
    )
