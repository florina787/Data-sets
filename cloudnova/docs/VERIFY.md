# Verification routine (run before every commit — referenced from CLAUDE.md)

Run in `cloudnova/` and report actual output — never summarise a run that did not happen.

1. `python -m app build --force` — must report 5000 invoices / 125 rejected rows.
2. `python -m pytest` — all pass.
3. `python -m evals` — `FAIL=0` and `XPASS=0`. If Qwen is reachable, also `python -m evals --llm`.
4. `python -m app demo | head -40` — Q1–Q6 must equal the README table.
5. If a number in README.md or docs/ changed, recompute it from DuckDB or `evals/oracle.py` before editing the doc.
6. `git diff` — no secrets, `.env`, model weights or `data/processed/`.

If a check fails, fix the code or the spec (spec first, with a change-log line). Never loosen a test, the SQL guard,
or an expected value to make it pass.
