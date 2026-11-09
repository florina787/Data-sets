"""Hardware profiles and the free local models each one recommends.

These are starting points only. The wizard benchmarks the machine and the
user can pick any model Ollama has installed. Every default is Apache-2.0 and
was chosen from VEENA's own real-model evaluation (reports/REAL_MODEL_EVALUATION.md).
"""

from __future__ import annotations

from typing import Any

# Every model VEENA recommends or knows about, with its licence as stated on the
# official model card (checked 2026-11-09, see reports/MODEL_LICENSE_AUDIT.md).
# "commercial" is False for licences that forbid commercial use: VEENA never
# recommends those, and Setup warns before a user downloads one.
MODEL_CATALOG: dict[str, dict[str, Any]] = {
    "qwen2.5:1.5b": {
        "kind": "text",
        "bytes": 986_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct",
    },
    "qwen2.5:3b": {
        "kind": "text",
        "bytes": 1_900_000_000,
        "license": "Qwen Research License",
        "commercial": False,
        "card": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct",
    },
    "qwen2.5:7b": {
        "kind": "text",
        "bytes": 4_700_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
    },
    "qwen3:1.7b": {
        "kind": "text",
        "bytes": 1_400_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen3-1.7B",
    },
    "qwen3:4b": {
        "kind": "text",
        "bytes": 2_500_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen3-4B",
    },
    "qwen3:8b": {
        "kind": "text",
        "bytes": 5_200_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen3-8B",
    },
    "qwen2.5vl:3b": {
        "kind": "vision",
        "bytes": 3_200_000_000,
        "license": "Qwen Research License",
        "commercial": False,
        "card": "https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct",
    },
    "qwen2.5vl:7b": {
        "kind": "vision",
        "bytes": 6_000_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct",
    },
    "qwen3-vl:2b": {
        "kind": "vision",
        "bytes": 1_900_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct",
    },
    "qwen3-vl:2b-instruct": {
        "kind": "vision",
        "bytes": 1_900_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct",
    },
    "qwen3-vl:4b": {
        "kind": "vision",
        "bytes": 3_300_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct",
    },
    "qwen3-vl:8b": {
        "kind": "vision",
        "bytes": 6_200_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct",
    },
    "granite3.2-vision:2b": {
        "kind": "vision",
        "bytes": 2_400_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/ibm-granite/granite-vision-3.2-2b",
    },
    "gemma4:e2b": {
        "kind": "vision",
        "bytes": 4_600_000_000,
        "license": "Apache-2.0",
        "commercial": True,
        "card": "https://huggingface.co/google/gemma-4-E2B-it",
    },
}


def license_of(model: str) -> dict[str, Any] | None:
    """Catalog entry for an Ollama model name, ignoring a trailing ':latest'."""
    return MODEL_CATALOG.get(model) or MODEL_CATALOG.get(model.removesuffix(":latest"))


PROFILES: dict[str, dict[str, Any]] = {
    "lite": {
        "label": "Lite",
        "target": "8 GB RAM, CPU only",
        "text_model": "qwen2.5:1.5b",
        "vision_model": "qwen3-vl:2b-instruct",
        "asr_model": "tiny",
        "num_ctx": 2048,
        "continuous_interval_s": 10,
        "notes": "Fastest small text model, tiny Whisper, vision loaded on demand.",
        "download_gb": 1.0 + 1.9 + 0.08,
    },
    "balanced": {
        "label": "Balanced",
        "target": "16 GB RAM, CPU or entry GPU",
        "text_model": "qwen3:1.7b",
        "vision_model": "qwen3-vl:2b-instruct",
        "asr_model": "base",
        "num_ctx": 4096,
        "continuous_interval_s": 5,
        "notes": "Text model that declined to invent facts in VEENA's tests (slower), base Whisper, 2B vision model.",
        "download_gb": 1.4 + 1.9 + 0.15,
    },
    "performance": {
        "label": "Performance",
        "target": "32 GB+ RAM or GPU with 8 GB+ VRAM",
        "text_model": "qwen2.5:7b",
        "vision_model": "qwen2.5vl:7b",
        "asr_model": "small",
        "num_ctx": 8192,
        "continuous_interval_s": 3,
        "notes": "7B text and vision models, small Whisper.",
        "download_gb": 4.7 + 6.0 + 0.5,
    },
}


def recommend_profile(hw: dict[str, Any]) -> dict[str, Any]:
    ram = hw.get("ram_gb", 0)
    vram = max((g.get("vram_mb") or 0 for g in hw.get("gpus", []) if g.get("accelerated")), default=0) / 1024
    reasons = [f"{ram:.0f} GB RAM detected"]
    if vram:
        reasons.append(f"accelerated GPU with {vram:.0f} GB memory")
    else:
        reasons.append("no accelerated GPU detected; inference runs on the CPU")
    if ram >= 30 or vram >= 8:
        key = "performance"
    elif ram >= 14:
        key = "balanced"
    else:
        key = "lite"
    if key != "lite" and hw.get("disk_free_gb", 0) < PROFILES[key]["download_gb"] + 2:
        reasons.append("not enough free disk for the larger models")
        key = "lite"
    return {
        "profile": key,
        "reasons": reasons,
        "caveat": "Recommendation is from detected specs only. Run the benchmark to measure this machine.",
    }
