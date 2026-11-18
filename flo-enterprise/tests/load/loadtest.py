"""Reproducible load test (asyncio + httpx). Reports MEASURED latency percentiles, throughput, error and load-shed rates.

    python tests/load/loadtest.py --users 50 --duration 60 --base http://localhost:8080

Virtual users cycle through the synthetic identities and run a weighted mix:
  65% dashboard reads (cached aggregates), 15% portfolio/fund detail, 15% Ask Flo (agent workflow), 5% document search.
Each user waits a randomized think time (0.5-2.0 s) between requests. Results are appended to var/load_test_report.json."""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

USERS = ["u-ceo", "u-cfo", "u-cio", "u-analyst"]
# role-appropriate endpoints only: the test measures performance, not authorization denials (those are covered by tests/security)
DASH = {"u-ceo": ["/api/executive/kpis?months=12", "/api/executive/aum-trend", "/api/executive/net-flows", "/api/executive/margin-trend",
                  "/api/executive/risk-heatmap", "/api/investment/concentration", "/api/scenarios/compare", "/api/decisions"],
        "u-cfo": ["/api/executive/kpis?months=24", "/api/executive/revenue-expenses", "/api/executive/actual-vs-budget", "/api/executive/product-profitability"],
        "u-cio": ["/api/investment/funds", "/api/investment/concentration", "/api/investment/correlation", "/api/scenarios/compare", "/api/investment/market"],
        "u-analyst": ["/api/investment/funds", "/api/investment/market", "/api/investment/correlation", "/api/investment/risk-return?universe=funds"]}
DETAIL = {"u-ceo": "/api/executive/revenue-attribution", "u-cfo": "/api/executive/aum-waterfall?months=6"}
QUESTIONS = ["Why did AUM increase while profitability declined?", "Analyze concentration and simulate a 20% equity market drop",
             "What is the client communications approval policy?", "Which decisions delivered measurable value?"]


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(p * (len(xs) - 1)))] * 1000, 1)


async def vu(i, client, tokens, deadline, stats, rng):
    user = USERS[i % len(USERS)]
    h = {"Authorization": f"Bearer {tokens[user]}"}
    while time.monotonic() < deadline:
        r = rng.random()
        if r < 0.65:
            kind, req = "dashboard", ("GET", rng.choice(DASH[user]), None)
        elif r < 0.80:
            kind, req = "detail", ("GET", DETAIL.get(user, f"/api/investment/funds/P-{rng.randint(1, 100):03d}"), None)
        elif r < 0.95:
            kind, req = "ask", ("POST", "/api/ask", {"question": rng.choice(QUESTIONS)})
        else:
            kind, req = "search", ("POST", "/api/docs/search", {"query": rng.choice(["concentration limit", "communications approval", "ETF fees"])})
        t0 = time.monotonic()
        try:
            resp = await client.request(req[0], req[1], json=req[2], headers=h)
            code = resp.status_code
        except Exception as e:  # noqa: BLE001
            code = f"exc:{e.__class__.__name__}"
        dt = time.monotonic() - t0
        stats[kind]["lat"].append(dt)
        stats[kind]["codes"][str(code)] += 1
        await asyncio.sleep(rng.uniform(0.5, 2.0))


async def main(a):
    limits = httpx.Limits(max_connections=min(a.users, 400), max_keepalive_connections=min(a.users, 400))
    async with httpx.AsyncClient(base_url=a.base, timeout=60, limits=limits) as c:
        tokens = {}
        for u in USERS:
            tokens[u] = (await c.post("/api/auth/login", json={"user_id": u})).json()["access_token"]
        stats = defaultdict(lambda: {"lat": [], "codes": defaultdict(int)})
        rng = random.Random(a.seed)
        t0 = time.monotonic()
        deadline = t0 + a.duration
        await asyncio.gather(*[vu(i, c, tokens, deadline, stats, random.Random(rng.random())) for i in range(a.users)])
        wall = time.monotonic() - t0
    out = {"measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "users": a.users, "duration_s": a.duration,
           "wall_s": round(wall, 1), "base": a.base, "host_note": a.note, "by_kind": {}}
    total = ok = shed = 0
    for k, v in stats.items():
        n = len(v["lat"])
        good = sum(cnt for code, cnt in v["codes"].items() if code.startswith("2"))
        out["by_kind"][k] = {"requests": n, "ok": good, "p50_ms": pct(v["lat"], 0.5), "p95_ms": pct(v["lat"], 0.95), "p99_ms": pct(v["lat"], 0.99),
                             "mean_ms": round(statistics.mean(v["lat"]) * 1000, 1) if n else None, "status_codes": dict(v["codes"])}
        total += n
        ok += good
        shed += v["codes"].get("503", 0)
    out["totals"] = {"requests": total, "throughput_rps": round(total / wall, 1), "success_rate": round(ok / total, 4) if total else None,
                     "load_shed_503": shed}
    path = Path(__file__).resolve().parents[2] / "var" / "load_test_report.json"
    path.parent.mkdir(exist_ok=True)
    prev = json.loads(path.read_text()) if path.exists() else {"runs": []}
    prev["runs"] = [r for r in prev.get("runs", []) if r["users"] != a.users] + [out]
    prev["runs"].sort(key=lambda r: r["users"])
    path.write_text(json.dumps(prev, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--users", type=int, default=50)
    p.add_argument("--duration", type=int, default=60)
    p.add_argument("--base", default="http://localhost:8080")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--note", default="")
    asyncio.run(main(p.parse_args()))
