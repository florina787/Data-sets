# Evidence behind the showcase documents

Every number in `CloudNova_FDE_Engineering_Showcase.pptx`, `CloudNova_FDE_Engineering_Case_Study.pdf` and
`MEDIUM_ARTICLE.md` comes from one of these commands, re-run on 2026-11-07 on branch
`claude/great-hamilton-8s8wk9-assurance` (submission figures from `claude/great-hamilton-8s8wk9`).

| Figure | Value | Source |
|---|---|---|
| Raw rows → clean invoices → rejected | 5,125 → 5,000 + 125 (82 exact, 27 synonym, 16 lost conflicts) | `python -m app build --force`; `GET /api/v1/reconciliation` |
| Paid revenue overstatement avoided | $2,121,660.87 ($122,268,789.42 vs $120,147,128.55) | `app/reconciliation.py` |
| Conflict swing | −$168,441.54 | `app/reconciliation.py` |
| Q1–Q6 | $32,686,371.16 · APAC $6,147.30 · $8,925,163.80 / 292 · 21.92% vs 18.81% · ACC-7509, ACC-1420, ACC-9946, ACC-1196, ACC-5211 (none CSAT ≤ 2) · 894 / $28,983,255.91 | `python -m app demo`; matched by `evals/oracle.py` |
| Date-order evidence | 1,320 / 786; 151; 81 ambiguous | profiling scripts; `specs/cloudnova_data_contract.md` §1 |
| FX evidence | 0 / 1,421 vs 1,421 / 1,421; Q1 $29,595,624.38 under inverse | `GET /api/v1/policy` (`app/policy.py::impact`) |
| Identity evidence | 3,815 ids, 24.4% inconsistent; 200 names, 100% | `app/policy.py::impact` |
| Hybrid vs Qwen-only | 6/6, 10 ms median, 61 ms max · 2/6, 20,619 ms median, 42,858 ms max | `evals/results/mode_comparison.json` (2026-11-07T18:45:41Z) |
| Unit tests | 156 passed (assurance) · 114 passed (submission) | `python -m pytest` |
| Per-file tests | rules 58 · governance 25 · planner 17 · enhancements 16 · policy 11 · studio 10 · pipeline 6 · journey 5 · reconciliation/API 5 · API/LLM 3 | `pytest <file> -o addopts=''` |
| Evals | PASS 31 FAIL 0 XFAIL 2 SKIP 3 · with Qwen PASS 33 FAIL 0 XFAIL 3 | `python -m evals`, `python -m evals --llm` |
| Startup | READY 2.0 s / 0.8 s / 4.5 s | README §7 (clean-shell runs) |
| Legacy adapter | 12 rows → 9 mapped, 3 rejected, 1 dedup-rejected, 1 pricing violation | `tests/test_enhancements.py::test_legacy_preview_maps_validates_and_traces_lineage` |
| Browser checks | 0 console errors / HTTP ≥ 400; guide placement at 4 viewport sizes | Playwright scripts run during the build |

Screenshots in `docs/media/` were captured from the running app with Playwright on 2026-11-07.
`build_showcase.py` regenerates the PowerPoint; `case_study.html` is the PDF source (printed with Chromium).
