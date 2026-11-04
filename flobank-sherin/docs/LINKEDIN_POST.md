# LinkedIn post

Attach `docs/media/sherin-guided-journey.mp4` as a native video (82 s, 1600×900, recorded from a live run).
Replace anything in brackets before posting.

---

Meet Sherin. She runs FLO Bank’s AI agents, and she shows you exactly what they cost.

Most AI dashboards for banks stop at activity: tokens used, tasks run, uptime. That isn’t what a CFO asks. The questions are simpler and harder. What did we earn? What did we spend? What did the AI cost? What verified value did it create? Which decisions still need a human?

So I built Sherin, a walking guide for an enterprise AI platform, and gave her three rules.

Money first: one deterministic engine feeds every chart, KPI and chat answer. Cost avoidance is never counted as revenue, and every ROI states its denominator.

Follow the real work: fifteen agents run in LangGraph. When an agent starts, Sherin walks to it. While a tool runs, she works. When validation begins, she moves to the verification station. Every step she takes comes from a recorded execution event, not a script.

Humans decide: material actions pause at the manager’s desk until an authorized person approves. A policy block can’t be overridden by a model or by anyone. And she doesn’t celebrate until the task has actually completed and been verified.

Ask her “why did AI spending increase this month?” and she walks to the cost chart, points at the largest increase, and lets you click through to the underlying records.

Under the hood it’s React, TypeScript, Plotly, React Flow, FastAPI, LangGraph and PostgreSQL, with 109 backend tests and 39 browser checks run against the live app. The bank’s financial figures in the demo are synthetic and labelled that way on screen. This is a working prototype, not a production bank.

If you’re working out how to make AI agents legible to executives, I’d like to compare notes. Message me or comment below.

---

Shorter caption for the video itself:

> Sherin walking through a live agent run: revenue, costs, agents, Guardian, a real approval pause, and a verified result. Demo figures are synthetic.
