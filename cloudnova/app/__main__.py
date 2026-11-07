"""Single entry point.

    python -m app                      build data if needed + answer the six stakeholder questions
    python -m app ask "question" [--session ID]
    python -m app chat                 interactive multi-turn session
    python -m app serve [--port 8000]  API + UI
    python -m app build [--force]      rebuild the cleaned DuckDB from the raw CSV
"""
from __future__ import annotations

import argparse
import sys

STAKEHOLDER_QUESTIONS = [
    "What was our total recognized revenue in USD for paid invoices in 2024?",
    "Which region has the highest average MRR per account?",
    "How much have we given back in refunds?",
    "What's the churn rate among Enterprise accounts vs Starter?",
    "List the top 5 accounts by revenue, and flag any with CSAT ≤ 2.",
    "How many invoices are stuck in pending/failed and what's the exposed $?",
]


def _print(resp: dict, show_sql: bool = True) -> None:
    print(resp["answer"].replace("**", ""))
    if show_sql and resp.get("sql"):
        print("\n  SQL ▸ " + resp["sql"].replace("\n", "\n        "))
    for c in resp.get("caveats", []):
        print(f"  ⚠ {c}")
    llm = resp.get("llm", {})
    print(f"  [{resp['intent']} · planner={resp['planner']} · {resp.get('latency_ms', 0):.0f} ms"
          + (f" · {llm.get('model')} {llm.get('latency_ms', 0):.0f} ms" if llm.get("used") else "") + "]")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app", description="CloudNova Revenue Intelligence Copilot")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.add_argument("--session")
    sub.add_parser("chat")
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    b = sub.add_parser("build")
    b.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    from .agent import supervisor
    from .errors import AppError
    from .llm.provider import provider_status
    from .pipeline.build import build

    m = build(force=getattr(args, "force", False), quiet=False)
    if args.cmd == "build":
        return 0
    if args.cmd == "serve":
        import uvicorn
        print(f"CloudNova Copilot → http://{args.host}:{args.port}  (API docs at /docs)")
        uvicorn.run("app.api:app", host=args.host, port=args.port, log_level="warning")
        return 0
    if args.cmd == "ask":
        try:
            r = supervisor.ask(args.question, args.session)
        except AppError as exc:
            print(f"✖ {exc.code}: {exc.message}", file=sys.stderr)
            return 2
        _print(r)
        print(f"  session: {r['session_id']}")
        return 0
    if args.cmd == "chat":
        sid = supervisor.new_session()
        st = provider_status()
        print(f"CloudNova Copilot — {st['label']}. Type 'exit' to quit, 'new' for a new conversation.")
        while True:
            try:
                q = input("\nyou ▸ ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if q.lower() in ("exit", "quit"):
                return 0
            if q.lower() == "new":
                sid = supervisor.new_session()
                print("(new conversation)")
                continue
            try:
                _print(supervisor.ask(q, sid))
            except AppError as exc:
                print(f"✖ {exc.code}: {exc.message}")

    # default: the demo
    st = provider_status()
    print(f"\nCloudNova Revenue Intelligence Copilot — data: {m['clean_invoices']:,} invoices / {m['accounts']:,} accounts "
          f"(raw {m['raw_rows']:,} rows, {m['rejected_rows']} moved to rejected_rows) · LLM: {st['label']}\n")
    sid = supervisor.new_session()
    for i, q in enumerate(STAKEHOLDER_QUESTIONS, 1):
        print("=" * 100)
        print(f"Q{i}. {q}\n")
        _print(supervisor.ask(q, sid))
        print()
    print("Next: `python -m app serve` for the UI, `python -m app chat` to ask your own questions, `python -m evals` to run the evals.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
