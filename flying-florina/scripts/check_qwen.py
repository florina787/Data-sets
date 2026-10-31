"""Discover and verify YOUR existing local Qwen model, then run one real inference.

Usage: backend/.venv/bin/python scripts/check_qwen.py
Prints model, version/quantization, path or server, runtime, CPU/GPU offload, and the measured
latency / time to first token / tokens per second of a short prompt. Never downloads anything.
Exit code 0 = Qwen verified, 1 = not found or not runnable (the reason is printed).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.llm.discovery import discover  # noqa: E402
from app.llm.gateway import LLMError, LLMUnavailable, LocalLLMGateway  # noqa: E402
from app.llm.telemetry import system_stats  # noqa: E402

d = discover(timeout=2.0)
print("Discovery:", json.dumps({k: v for k, v in d.as_dict().items() if k not in ("searched",)}, indent=1, default=str))
print("Searched:", *d.searched, sep="\n  ")
if not d.found:
    print("\nQWEN NOT VERIFIED:", d.reason)
    sys.exit(1)
g = LocalLLMGateway(discovery=d)
try:
    r = g.generate(agent="check_qwen", task="health_check", system="Answer in one short sentence.",
                   user="What does an engine vibration monitoring system measure?", max_tokens=48, use_cache=False)
except (LLMError, LLMUnavailable) as err:
    print("\nQWEN FOUND BUT INFERENCE FAILED:", err)
    sys.exit(1)
print("\nAnswer:", r.text)
print(json.dumps({"model": r.model, "runtime": r.runtime, "latency_ms": r.latency_ms, "first_token_ms": r.first_token_ms, "tokens_per_s": r.tokens_per_s,
                  "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens, "runtime_info": g.runtime().info(), "system": system_stats()}, indent=1, default=str))
print("\nQWEN VERIFIED: Flying_Florina will use this model for every AI workflow.")
