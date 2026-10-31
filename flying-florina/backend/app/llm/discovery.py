"""Find the user's EXISTING local Qwen model. Nothing is ever downloaded.

Search order (the first hit wins):
  1. FF_QWEN_MODEL_PATH   an explicit .gguf file          -> in-process llama.cpp (llama-cpp-python)
  2. FF_QWEN_BASE_URL     an explicit loopback server     -> Ollama or OpenAI-compatible (llama.cpp server, LM Studio)
  3. Ollama on LLM_URL (default http://127.0.0.1:11434) with a model whose name contains "qwen"
  4. an OpenAI-compatible server on 127.0.0.1:8080 / :1234 / :8000 advertising a qwen model
  5. Qwen *.gguf files in the usual places, including the Conversation Intelligence Copilot's
     data/models/ folder next to this repository (that is where the Copilot downloaded
     qwen2.5-1.5b-instruct-q4_k_m.gguf)

Only loopback servers are ever contacted (policy POL-008), so discovery works offline.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, get_settings

LOOPBACK = re.compile(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(/|$)")
QUANT = re.compile(r"(q\d(_[a-z0-9]+)*|f16|bf16|fp16|f32|iq\d[_a-z0-9]*)", re.I)
OPENAI_PORTS = (8080, 1234)  # 8000 is Flying_Florina's own API


@dataclass
class Discovery:
    found: bool
    runtime: str | None = None  # llama_cpp | ollama | openai_compatible
    model: str | None = None
    quantization: str | None = None
    path: str | None = None
    base_url: str | None = None
    size_bytes: int | None = None
    family: str | None = None
    parameter_size: str | None = None
    reason: str = ""
    searched: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    llama_cpp_installed: bool = False
    gpu_offload_supported: bool | None = None
    discovered_at: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_loopback(url: str) -> bool:
    return bool(LOOPBACK.match(url or ""))


def quantization_from_name(name: str) -> str | None:
    m = QUANT.search(Path(name).stem.split("-")[-1]) or QUANT.search(name)
    return m.group(1).upper() if m else None


def gguf_search_dirs() -> list[Path]:
    home = Path.home()
    dirs = [
        REPO_ROOT.parent / "conversation-intelligence-copilot" / "data" / "models",
        REPO_ROOT / "models",
        REPO_ROOT / "data" / "models",
        home / "models",
        home / "Models",
        home / ".cache" / "huggingface" / "hub",
        home / ".cache" / "lm-studio" / "models",
        home / ".lmstudio" / "models",
        home / "llama.cpp" / "models",
    ]
    extra = os.environ.get("FF_QWEN_SEARCH_DIRS", "")
    dirs += [Path(p).expanduser() for p in extra.split(os.pathsep) if p]
    return dirs


def _find_ggufs(searched: list[str]) -> list[Path]:
    found: list[Path] = []
    for d in gguf_search_dirs():
        searched.append(str(d))
        if not d.is_dir():
            continue
        try:
            for p in d.rglob("*.gguf"):
                if "qwen" in p.name.lower() and p.is_file() and p.stat().st_size > 1_000_000:
                    found.append(p)
        except OSError:
            continue
    # Prefer instruct models, then smaller files (faster on CPU).
    return sorted(set(found), key=lambda p: ("instruct" not in p.name.lower(), p.stat().st_size))


def _llama_cpp() -> tuple[bool, bool | None]:
    try:
        import llama_cpp  # noqa: F401

        try:
            gpu = bool(llama_cpp.llama_supports_gpu_offload())
        except Exception:  # noqa: BLE001
            gpu = None
        return True, gpu
    except Exception:  # noqa: BLE001
        return False, None


def _ollama_models(base: str, timeout: float) -> list[dict[str, Any]]:
    import httpx

    r = httpx.get(f"{base.rstrip('/')}/api/tags", timeout=timeout)
    r.raise_for_status()
    return r.json().get("models", []) or []


def _openai_models(base: str, timeout: float) -> list[str]:
    import httpx

    r = httpx.get(f"{base.rstrip('/')}/v1/models", timeout=timeout)
    r.raise_for_status()
    return [m.get("id", "") for m in r.json().get("data", [])]


def discover(timeout: float = 0.8) -> Discovery:
    s = get_settings()
    searched: list[str] = []
    installed, gpu = _llama_cpp()
    base = Discovery(found=False, searched=searched, llama_cpp_installed=installed, gpu_offload_supported=gpu)

    if s.llm_mode == "off":
        base.reason = "LLM_ENABLED=false: model calls are switched off; the deterministic engine answers."
        return base

    # 1. explicit file
    if s.qwen_model_path:
        p = Path(s.qwen_model_path).expanduser()
        searched.append(str(p))
        if not p.is_file():
            base.reason = f"FF_QWEN_MODEL_PATH points to {p}, which does not exist."
            return base
        if not installed:
            base.reason = (f"Found {p.name}, but llama-cpp-python is not installed in this Python environment. "
                           "Install it once (pip install -r requirements-llm.txt) or serve the model with Ollama / llama.cpp server.")
            base.candidates = [{"path": str(p), "runtime": "llama_cpp (not installed)"}]
            return base
        return Discovery(True, "llama_cpp", p.stem, quantization_from_name(p.name), str(p), None, p.stat().st_size, "qwen",
                         reason="FF_QWEN_MODEL_PATH", searched=searched, llama_cpp_installed=True, gpu_offload_supported=gpu)

    # 2. explicit server
    if s.qwen_base_url:
        url = s.qwen_base_url.rstrip("/")
        searched.append(url)
        if not is_loopback(url):
            base.reason = f"FF_QWEN_BASE_URL {url} is not a loopback address; refused (POL-008, no external inference)."
            return base
        hit = _probe_server(url, timeout, s.llm_model)
        if hit:
            hit.searched, hit.llama_cpp_installed, hit.gpu_offload_supported = searched, installed, gpu
            return hit
        base.reason = f"No Qwen model answered at FF_QWEN_BASE_URL {url}."
        return base

    # 3. Ollama
    url = (s.llm_url or "http://127.0.0.1:11434").rstrip("/")
    if is_loopback(url) and s.qwen_runtime in ("auto", "ollama"):
        searched.append(f"ollama {url}")
        hit = _probe_ollama(url, timeout, s.llm_model)
        if hit:
            hit.searched, hit.llama_cpp_installed, hit.gpu_offload_supported = searched, installed, gpu
            return hit

    # 4. OpenAI-compatible local servers
    if s.qwen_runtime in ("auto", "openai_compatible"):
        for port in OPENAI_PORTS:
            u = f"http://127.0.0.1:{port}"
            searched.append(f"openai-compatible {u}")
            hit = _probe_openai(u, timeout, s.llm_model)
            if hit:
                hit.searched, hit.llama_cpp_installed, hit.gpu_offload_supported = searched, installed, gpu
                return hit

    # 5. GGUF files on disk
    if s.qwen_runtime in ("auto", "llama_cpp"):
        files = _find_ggufs(searched)
        base.candidates = [{"path": str(p), "size_bytes": p.stat().st_size} for p in files]
        if files:
            p = files[0]
            if not installed:
                base.reason = (f"Found your Qwen model {p} but llama-cpp-python is not installed in this backend's Python. "
                               "Run: pip install -r backend/requirements-llm.txt (installs the runtime only; the model is reused).")
                return base
            return Discovery(True, "llama_cpp", p.stem, quantization_from_name(p.name), str(p), None, p.stat().st_size, "qwen",
                             reason="Found on disk", searched=searched, candidates=base.candidates, llama_cpp_installed=True,
                             gpu_offload_supported=gpu)

    base.reason = ("No local Qwen model was found. Set FF_QWEN_MODEL_PATH to your .gguf file, or start Ollama / llama.cpp server "
                   "with your Qwen model. Flying_Florina never downloads a model and never calls an external API.")
    return base


def _probe_server(url: str, timeout: float, prefer: str) -> Discovery | None:
    return _probe_ollama(url, timeout, prefer) or _probe_openai(url, timeout, prefer)


def _probe_ollama(url: str, timeout: float, prefer: str) -> Discovery | None:
    try:
        models = _ollama_models(url, timeout)
    except Exception:  # noqa: BLE001
        return None
    qwen = [m for m in models if "qwen" in (m.get("name") or m.get("model") or "").lower()]
    if prefer:
        qwen = [m for m in qwen if prefer in (m.get("name") or "")] or qwen
    if not qwen:
        return None
    m = qwen[0]
    d = m.get("details") or {}
    return Discovery(True, "ollama", m.get("name") or m.get("model"), d.get("quantization_level") or quantization_from_name(m.get("name", "")),
                     None, url, m.get("size"), d.get("family"), d.get("parameter_size"), reason="Ollama",
                     candidates=[{"name": x.get("name"), "size_bytes": x.get("size")} for x in qwen])


def _probe_openai(url: str, timeout: float, prefer: str) -> Discovery | None:
    try:
        ids = _openai_models(url, timeout)
    except Exception:  # noqa: BLE001
        return None
    qwen = [i for i in ids if "qwen" in i.lower()]
    if prefer:
        qwen = [i for i in qwen if prefer in i] or qwen
    if not qwen:
        return None
    return Discovery(True, "openai_compatible", qwen[0], quantization_from_name(qwen[0]), None, url, reason="OpenAI-compatible local server",
                     candidates=[{"name": i} for i in qwen])
