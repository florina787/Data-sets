"""Benchmark the Explanation agent on the local model: same question, full pipeline, measured phase by phase.

Measures, per request: wall time, time in each graph node, and for every llama.cpp call the prompt tokens and
prompt-evaluation time, generated tokens and generation time (llama.cpp's own performance counters), tokens/sec,
process CPU time (how many cores were busy), retries, plus answer quality (explanation source, QA status,
groundedness, grounding rejections). The model load is measured separately, so cold and warm runs can be told apart.
The response cache is pointed at an empty file and llama.cpp's KV cache is cleared before each run, so every run
reads its whole prompt, as a new question would.

Usage: LLM_PROVIDER=local uv run python -m scripts.benchmark_explanation --label before --runs 3
Writes data/manifests/explanation_benchmark_<label>.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import tempfile
import time
from pathlib import Path

QUESTION = "Why is duplicate charge so negative?"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--question", default=QUESTION)
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="explbench-"))
    os.environ.setdefault("LLM_PROVIDER", "local")
    os.environ["LLM_CACHE_PATH"] = str(tmp / "llm_cache.sqlite")  # no cache hits: every run calls the model

    import llama_cpp
    from llama_cpp import Llama

    from app.agents.graph import run_chat
    from app.config import PROJECT_ROOT, get_settings
    from app.llm.gemini_client import get_llm
    from app.observability.store import get_telemetry

    calls: list[dict] = []
    original = Llama.create_chat_completion

    def instrumented(self, *a, **kw):
        ctx = self._ctx.ctx
        llama_cpp.llama_perf_context_reset(ctx)
        t0 = time.perf_counter()
        system = (kw.get("messages") or [{}])[0].get("content", "")
        rec = {"prompt": "explanation" if "narrative answer" in system else "general_answer" if "general knowledge" in system else "intent",
               "max_tokens": kw.get("max_tokens"), "stream": bool(kw.get("stream"))}

        def finish():
            p = llama_cpp.llama_perf_context(ctx)
            rec.update(wall_ms=round((time.perf_counter() - t0) * 1000, 1), prompt_tokens=p.n_p_eval, prompt_eval_ms=round(p.t_p_eval_ms, 1),
                       generated_tokens=p.n_eval, generation_ms=round(p.t_eval_ms, 1),
                       prompt_tok_per_s=round(p.n_p_eval / (p.t_p_eval_ms / 1000), 1) if p.t_p_eval_ms else None,
                       gen_tok_per_s=round(p.n_eval / (p.t_eval_ms / 1000), 1) if p.t_eval_ms else None, reused_tokens=p.n_reused)
            calls.append(rec)

        out = original(self, *a, **kw)
        if kw.get("stream"):
            def gen():
                yield from out
                finish()
            return gen()
        finish()
        return out

    Llama.create_chat_completion = instrumented

    s = get_settings()
    llm = get_llm()
    assert llm.provider == "local", f"expected the local model, got {llm.provider}"
    t0 = time.perf_counter()
    _ = llm.llama  # cold load, measured on its own
    load_ms = round((time.perf_counter() - t0) * 1000, 1)

    runs = []
    for i in range(args.runs):
        calls.clear()
        from app.llm.cache import ResponseCache

        llm.cache = ResponseCache(tmp / f"llm_cache_{i}.sqlite")  # no cache hits: every run calls the model
        llm.llama.reset()  # clear llama.cpp's KV cache, so each run reads its prompt like a new question would
        c0, w0 = time.process_time(), time.perf_counter()
        r = run_chat(args.question, analysis_mode="hybrid_ai")
        wall = time.perf_counter() - w0
        cpu = time.process_time() - c0
        trace = get_telemetry().trace(r["request_id"])
        nodes = {n["node"]: round(n["duration_ms"] or 0, 1) for n in trace["nodes"] if n["status"] in ("completed", "failed")}
        governance = [g["detail"] for g in r["governance"] if g["policy"] == "latency_budget"]
        runs.append({
            "latency_fallback": governance,
            "governance": [f"{g['policy']}:{g['outcome']}: {g['detail'][:160]}" for g in r["governance"]],
            "run": i + 1, "wall_s": round(wall, 2), "cpu_s": round(cpu, 2), "avg_cores_busy": round(cpu / wall, 2) if wall else None,
            "nodes_ms": nodes, "explanation_ms": nodes.get("explanation"), "llm_calls": list(calls),
            "retries": sum((c["retries"] or 0) for c in trace["llm_calls"]),
            "telemetry_calls": [{k: c[k] for k in ("purpose", "input_tokens", "output_tokens", "latency_ms", "status", "retries")} for c in trace["llm_calls"]],
            "explanation_source": r["model_metadata"]["explanation_source"], "qa": f"{r['quality_status']['passed']}/{r['quality_status']['total']} {r['quality_status']['status']}",
            "groundedness": (r.get("groundedness") or {}).get("label"), "grounding_rejections": [g["detail"] for g in r["governance"] if g["policy"] == "numeric_grounding"],
            "headline": r["headline"], "answer": r["answer"], "key_points": r["key_points"], "evidence_items": len(r["evidence"]),
        })
        print(f"run {i + 1}: {wall:.1f}s total, explanation {nodes.get('explanation')} ms, source {runs[-1]['explanation_source']}, "
              f"calls {[(c['prompt'], c['prompt_tokens'], c['generated_tokens'], c['wall_ms']) for c in calls]}")

    out = {"label": args.label, "question": args.question, "model": s.local_model_file, "provider": llm.provider,
           "hardware": {"cpus": os.cpu_count(), "platform": platform.platform(), "gpu_offload_supported": bool(llama_cpp.llama_supports_gpu_offload()),
                        "llama_cpp": llama_cpp.__version__, "n_threads": s.local_threads, "n_ctx": s.local_n_ctx},
           "model_load_ms": load_ms, "runs": runs, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    path = PROJECT_ROOT / "data" / "manifests" / f"explanation_benchmark_{args.label}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"model load {load_ms} ms; wrote {path}")


if __name__ == "__main__":
    main()
