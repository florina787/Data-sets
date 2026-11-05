"""Benchmark Qwen3 models on this machine through the same client the app uses.

    python scripts/benchmark_qwen.py qwen3:0.6b qwen3:1.7b qwen3:4b > ../docs/benchmark.json

Measures load time, resident memory of the inference server, CPU, TTFT, tokens/s and four task
accuracies on small fixed test sets (structured output, tool selection, resume skill extraction,
interview feedback relevance). Small sets: treat accuracy as indicative, not definitive.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import httpx
import psutil

os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/careerflo-bench.db")

from app.db import Base, get_engine  # noqa: E402
from app.llm import qwen  # noqa: E402

BASE = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:11434")

STRUCTURED = [
    ("Senior AI Engineer at Acme in Toronto, CAD 150,000-180,000, hybrid.",
     {"title": "Senior AI Engineer", "company": "Acme", "city": "Toronto", "salary_min": 150000, "salary_max": 180000}),
    ("Data Scientist role with Northwind in Vancouver paying 120000 to 140000 CAD, remote.",
     {"title": "Data Scientist", "company": "Northwind", "city": "Vancouver", "salary_min": 120000, "salary_max": 140000}),
    ("Globex is hiring a Backend Engineer in Montreal; salary 100,000 - 125,000.",
     {"title": "Backend Engineer", "company": "Globex", "city": "Montreal", "salary_min": 100000, "salary_max": 125000}),
    ("Machine Learning Engineer, Initech, Ottawa. Compensation: $130k-$160k.",
     {"title": "Machine Learning Engineer", "company": "Initech", "city": "Ottawa", "salary_min": 130000, "salary_max": 160000}),
]
TOOLS = ["search_jobs", "tailor_resume", "start_mock_interview", "company_research", "salary_report", "list_applications"]
TOOL_CASES = [("Find me ML jobs in Calgary", "search_jobs"), ("Make my resume fit this posting", "tailor_resume"),
              ("Quiz me with interview questions for a data role", "start_mock_interview"), ("What does Shopify do?", "company_research"),
              ("How much do AI engineers earn in Toronto?", "salary_report"), ("Show the status of my job applications", "list_applications"),
              ("Look for remote backend roles", "search_jobs"), ("Practice a behavioral interview with me", "start_mock_interview")]
RESUME = ("Built RAG pipelines with LangGraph and FastAPI; deployed on Kubernetes and AWS; wrote Python and SQL ETL; "
          "trained PyTorch models; set up GitHub Actions CI/CD.")
RESUME_SKILLS = {"rag", "langgraph", "fastapi", "kubernetes", "aws", "python", "sql", "pytorch", "ci/cd"}
INTERVIEW = [("Explain the bias-variance trade-off.", "Bias is error from simple models.", ["variance", "overfitting"]),
             ("How do you prevent unsafe agent actions?", "I write a good prompt.", ["approval", "allowlist"])]


def server_rss() -> float:
    total = 0
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if "ollama" in (p.info["name"] or "") or any("llama" in c for c in (p.info["cmdline"] or [])):
                total += p.memory_info().rss
        except psutil.Error:
            pass
    return round(total / 1e9, 2)


async def bench(model: str) -> dict:
    os.environ["LLM_MODEL"] = model
    from app.config import get_settings

    get_settings.cache_clear()
    qwen.reset_llm()
    llm = qwen.get_llm()
    async with httpx.AsyncClient(timeout=300) as c:
        await c.post(f"{BASE}/api/generate", json={"model": model, "keep_alive": 0})  # unload
        t0 = time.perf_counter()
        await c.post(f"{BASE}/api/generate", json={"model": model, "prompt": "", "keep_alive": "10m"})
        load_s = round(time.perf_counter() - t0, 2)
    psutil.cpu_percent(None)
    speed = []
    for prompt in ["Give three tips for a resume summary.", "Explain RAG in two sentences."]:
        r = await llm.complete([{"role": "system", "content": "Be concise."}, {"role": "user", "content": prompt}], purpose="bench", max_tokens=120)
        speed.append(r)
    cpu = psutil.cpu_percent(None)
    ok = 0
    for text, exp in STRUCTURED:
        r = await llm.complete([{"role": "system", "content": "Extract job fields. Reply with JSON only: {title, company, city, salary_min, salary_max} (numbers)."},
                                {"role": "user", "content": text}], purpose="bench", json_mode=True, max_tokens=120)
        try:
            got = r.json()
            ok += all(str(got.get(k)).replace(",", "").lower().strip() == str(v).lower() for k, v in exp.items())
        except Exception:  # noqa: BLE001
            pass
    tool_ok = 0
    for text, exp in TOOL_CASES:
        r = await llm.complete([{"role": "system", "content": f"Pick exactly one tool from {TOOLS}. Reply with JSON only: {{\"tool\": name}}."},
                                {"role": "user", "content": text}], purpose="bench", json_mode=True, max_tokens=40)
        try:
            tool_ok += r.json().get("tool") == exp
        except Exception:  # noqa: BLE001
            pass
    r = await llm.complete([{"role": "system", "content": "List the technical skills named in the text as a JSON array of short skill names (1-3 words each), e.g. [\"Python\", \"Docker\"]. Only skills present in the text."},
                            {"role": "user", "content": RESUME}], purpose="bench", json_mode=False, max_tokens=150)
    try:
        items = [str(x).lower() for x in r.json()]
    except Exception:  # noqa: BLE001
        items = []
    # An expected skill counts as found if any returned item mentions it; an item counts as precise
    # if it is a short skill name that matches an expected skill.
    recall = sum(any(k in it for it in items) for k in RESUME_SKILLS) / len(RESUME_SKILLS)
    precision = (sum(1 for it in items if len(it.split()) <= 3 and any(k in it for k in RESUME_SKILLS)) / len(items)) if items else 0.0
    iv_ok = 0
    for q, a, must in INTERVIEW:
        r = await llm.complete([{"role": "system", "content": "You are an interviewer. Give 2 sentences of feedback naming what is missing."},
                                {"role": "user", "content": f"Question: {q}\nAnswer: {a}"}], purpose="bench", max_tokens=120)
        iv_ok += any(m in r.text.lower() for m in must)
    return {"model": model, "load_seconds": load_s, "server_rss_gb": server_rss(), "cpu_percent_during_generation": cpu,
            "ttft_ms": round(sum(s.ttft_ms or 0 for s in speed) / len(speed)),
            "tokens_per_second": round(sum(s.tokens_per_second or 0 for s in speed) / len(speed), 1),
            "structured_output_accuracy": f"{ok}/{len(STRUCTURED)}", "tool_selection_accuracy": f"{tool_ok}/{len(TOOL_CASES)}",
            "resume_skill_recall": round(recall, 2), "resume_skill_precision": round(precision, 2),
            "interview_feedback_relevance": f"{iv_ok}/{len(INTERVIEW)}"}


async def main(models: list[str]) -> None:
    Base.metadata.create_all(get_engine())
    out = {"machine": {"cpus": psutil.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 1e9, 1)}, "results": []}
    for m in models:
        out["results"].append(await bench(m))
        print(json.dumps(out["results"][-1]), file=sys.stderr)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["qwen3:0.6b", "qwen3:1.7b", "qwen3:4b"]))
