# Demo script (≈15 minutes)

Start: `make dev` (or `docker compose up --build` → http://localhost:8080). Open http://localhost:5173. Optional: set `GEMINI_API_KEY` first; the header shows **Gemini · model** or **Deterministic mode**.

## 1. Q1 — negative topics (3 min)
1. Click the **Sentiment × topics** card.
2. Point at the progress chips: real LangGraph nodes as they start and finish (input → memory → intent → supervisor → topic agent → evidence → explanation → visualisation → QA → governance → response).
3. Answer: November 2025 is the latest month **in the data** (the calendar note explains the rule and coverage); 239 of 682 conversations negative; top 5 by count.
4. Show **Negative rate with 95% CI**: highest count ≠ highest rate (General help leads by count because it merges two templates; Duplicate charge leads by rate). Uncertainty: chi-square p = 0.057.
5. Click a bar → the conversations behind it → a transcript with CSV line references.
6. Click **QA 10/10** to show the checks; click **Trace** → Agent Harness.

## 2. Q2 — coaching (2 min)
1. **Agent coaching** card. Headline: no agent has ≥ 3 conversations (2,974 of 2,987 have one), so it ranks **conversations** for review, not people.
2. Heatmap of review signals; workforce figure: 29.3% of negative customer turns got an acknowledgement or apology; 57.3% of assessable closing actions don't fit the issue.
3. Human-review banner; evidence cards; "Which agents should be fired?" is refused.

## 3. Q3 — trajectory (2 min)
1. Conversation Explorer → C0000479 → **Analyse sentiment trajectory**.
2. Line chart with turning points; annotated timeline; note that turn order is used because timestamps are not monotonic.

## 4. Q4 — leadership (3 min)
1. **Leadership priorities** card or the Leadership Command page.
2. Priority matrix; stacked bars show what drives each score; weights are visible and documented.
3. Recommendations: finding, metric, action, owner, evidence, uncertainty; sensitivity table (13 scenarios).

## 5. Bonus — retrieval (1 min)
"Find conversations where the customer asked to escalate an app crash." → filtered semantic search, one passage per conversation, similarity explained as a ranking signal. Mention the LSA fallback and its measured weakness.

## 6. Bonus — memory (2 min)
After Q1: "Compare the top two topics." → "What about the previous month?" → "Now show similar conversations for the first one." Point at the plan notes ("Resolved '#1, #2' …", "Kept the previous date window …"). Then "Which findings are uncertain?" re-runs the analysis rather than trusting earlier text.

## 7. Engineering depth (2 min)
Agent Harness (skipped vs completed nodes, node inspector, model calls) → Prompt Library → System Metrics (latency per node, requests by intent, model errors) → Governance (controls incl. "not implemented", blind human review, audit log).
