"""Flying Florina 3.0 performance benchmark. Measures; never estimates. Writes docs/performance_3_0_measured.json.

Starts its own backend on a fresh data folder (port 8020), so numbers include seeding and model fitting:
  * startup: process start -> /health, -> /ready, -> forecasting models fitted (cold, no cache) and warm restart (cache present)
  * chat latency: the 12 suggested 3.0 questions and the four 2.0 questions (routing + agents + tools + composition; Qwen only if found)
  * endpoint latency and throughput under concurrency (8 parallel clients)
  * backend process memory (RSS) and CPU time
  * map render time in headless Chromium (optional, needs the Vite dev server on :5173 and Playwright)

Usage: backend/.venv/bin/python scripts/benchmark_3.py [--no-browser]
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8020
BASE = f"http://127.0.0.1:{PORT}"
Q3 = ["Show global component shortages.", "Which components have the highest predicted maintenance demand?", "Forecast hydraulic pump demand for the next 90 days.",
      "Show supplier delays on the global map.", "Explain this component's degradation trend.", "Compare two maintenance planning scenarios.",
      "What evidence supports this forecast?", "Show the agent execution graph.", "What happened in my previous investigation?", "Analyze this prerecorded drone video.",
      "Show historical forecast accuracy.", "Which software dependencies could be affected by this change?"]
Q2 = ["Why is aircraft AC-204 showing abnormal vibration, and what should engineering investigate?",
      "Which recovery option could return AC-204 to service fastest, considering spare parts, maintenance scheduling, and engineering approval?",
      "How can we modernize our legacy aircraft maintenance system using APIs, MCP, and AI without replacing the existing platform?",
      "What is affecting fleet readiness, and which maintenance improvements could reduce downtime and cost?"]


def req(path: str, body: dict | None = None, token: str | None = None, timeout: float = 300) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method="POST" if body is not None else "GET",
                               headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(r, timeout=timeout) as resp:  # noqa: S310 - loopback benchmark server
        return json.loads(resp.read())


def wait(path: str, limit: float) -> float | None:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limit:
        try:
            req(path, timeout=2)
            return time.perf_counter() - t0
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    return None


def rss_mb(pid: int) -> float | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS"):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        return None
    return None


def cpu_s(pid: int) -> float | None:
    try:
        f = Path(f"/proc/{pid}/stat").read_text().split()
        return (int(f[13]) + int(f[14])) / os.sysconf("SC_CLK_TCK")
    except OSError:
        return None


def start(data_dir: str) -> tuple[subprocess.Popen, float]:
    env = {**os.environ, "FF_DATA_DIR": data_dir, "FF_GENERATED_DIR": f"{data_dir}/generated", "LLM_ENABLED": os.environ.get("LLM_ENABLED", "auto"),
           "OFFLINE_MODE": "true", "DEMO_MODE": "true"}
    t0 = time.perf_counter()
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--log-level", "warning"], cwd=ROOT / "backend", env=env,  # noqa: S603
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p, t0


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))], 1)


def main() -> None:
    out: dict = {"machine": {"python": platform.python_version(), "platform": platform.platform(), "cpus": os.cpu_count()},
                 "note": "Measured on this machine by scripts/benchmark_3.py. Qwen explanation time is included only if a local Qwen model was found."}
    data_dir = tempfile.mkdtemp(prefix="ff-bench-")
    proc, t0 = start(data_dir)
    try:
        h = wait("/health", 120)
        r = wait("/ready", 120)
        out["startup_cold"] = {"to_health_s": round(h + 0, 2) if h else None, "to_ready_s": round(r, 2) if r else None}
        tok = req("/api/auth/login", {"user_id": "planner.marco"})["data"]["token"]
        tf = time.perf_counter()
        st = req("/api/global/map?horizon=30", token=tok)  # waits for the background fit if still running
        fresh = st["data"]["freshness"]
        out["forecast_models"] = {"fit_ms_reported": fresh["build_ms"], "first_map_request_s": round(time.perf_counter() - tf, 2),
                                  "loaded_from_cache": fresh.get("loaded_from_cache")}
        llm = req("/api/llm/status", token=tok)["data"]
        out["qwen"] = {"available": llm.get("available"), "model": llm.get("discovery", {}).get("model"), "reason": llm.get("discovery", {}).get("reason")}
        sid = None
        rows = []
        for q in Q3 + Q2:
            t = time.perf_counter()
            d = req("/api/chat/query", {"query": q, "session_id": sid, "wait": True}, token=tok)["data"]
            sid = d["session_id"]
            rows.append({"query": q, "workflow": d["workflow"], "status": d["status"], "ms": round((time.perf_counter() - t) * 1000, 1)})
        three = [r["ms"] for r in rows[: len(Q3)]]
        two = [r["ms"] for r in rows[len(Q3):]]
        out["chat_latency_ms"] = {"three_point_zero": {"p50": pct(three, 0.5), "p95": pct(three, 0.95), "max": max(three)},
                                  "two_point_zero_four_questions": {"p50": pct(two, 0.5), "max": max(two)}, "rows": rows}
        # endpoint latency under concurrency
        def hit(path: str) -> float:
            t = time.perf_counter()
            req(path, token=tok)
            return (time.perf_counter() - t) * 1000

        conc = {}
        for path in ("/api/global/map?horizon=60", "/api/forecast/components?horizon=90", "/api/global/timeline", "/api/harness/control-tower"):
            seq = [hit(path) for _ in range(5)]
            t = time.perf_counter()
            with ThreadPoolExecutor(8) as ex:
                par = list(ex.map(lambda _i, p=path: hit(p), range(40)))
            conc[path] = {"sequential_p50_ms": pct(seq, 0.5), "concurrent8_p50_ms": pct(par, 0.5), "concurrent8_p95_ms": pct(par, 0.95),
                          "throughput_rps": round(40 / (time.perf_counter() - t), 1)}
        out["endpoints"] = conc
        out["backend_process"] = {"rss_mb_after_run": rss_mb(proc.pid), "cpu_seconds_total": round(cpu_s(proc.pid) or 0, 1),
                                  "wall_seconds": round(time.perf_counter() - t0, 1)}
    finally:
        proc.terminate()
        proc.wait(timeout=30)
    # warm restart: same data folder, model results cached on disk
    proc, t0 = start(data_dir)
    try:
        r = wait("/ready", 120)
        tok = req("/api/auth/login", {"user_id": "planner.marco"})["data"]["token"]
        tf = time.perf_counter()
        st = req("/api/global/map?horizon=30", token=tok)
        convs = req("/api/memory/conversations", token=tok)["data"]
        out["startup_warm"] = {"to_ready_s": round(r, 2) if r else None, "first_map_request_s": round(time.perf_counter() - tf, 2),
                               "loaded_from_cache": st["data"]["freshness"].get("loaded_from_cache"), "conversations_restored": len(convs),
                               "rss_mb": rss_mb(proc.pid)}
    finally:
        proc.terminate()
        proc.wait(timeout=30)
        shutil.rmtree(data_dir, ignore_errors=True)
    if "--no-browser" not in sys.argv:
        out["map_render"] = browser_map_render()
    path = ROOT / "docs" / "performance_3_0_measured.json"
    path.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "chat_latency_ms"}, indent=1))
    print("chat", json.dumps({k: v for k, v in out["chat_latency_ms"].items() if k != "rows"}))


def browser_map_render() -> dict:
    js = """
const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});const p=await b.newPage({viewport:{width:1600,height:1000}});
const out={};
for (const mode of ['globe','lite']){
 await p.goto('http://127.0.0.1:5173/global');
 const t0=Date.now();
 await p.waitForFunction(()=>{const k=[...document.querySelectorAll('p')].find(e=>e.textContent.startsWith('Removal demand'));return k&&!k.parentElement.textContent.includes('…')},null,{timeout:120000});
 if(mode==='lite'){await p.click('text=Lite');}
 const sel = mode==='globe' ? 'canvas.maplibregl-canvas' : '[data-testid=lite-map] circle';
 await p.waitForSelector(sel,{timeout:60000});
 out[mode+'_ms_to_data_and_map']=Date.now()-t0;
 const t1=Date.now(); await p.click('text=+90D'); await p.waitForTimeout(50); out[mode+'_horizon_switch_ms']=Date.now()-t1;
}
console.log(JSON.stringify(out));await b.close();})();
"""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, dir=tempfile.gettempdir()) as fh:
            fh.write(js)
        r = subprocess.run(["node", fh.name], capture_output=True, text=True, timeout=300, check=False)  # noqa: S603,S607
        return {**json.loads(r.stdout.strip().splitlines()[-1]), "note": "Headless Chromium with software WebGL (SwiftShader); a GPU is faster. Requires Vite on :5173."}
    except Exception as err:  # noqa: BLE001
        return {"error": str(err)[:200]}


if __name__ == "__main__":
    main()
