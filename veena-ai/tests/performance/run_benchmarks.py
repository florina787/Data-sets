"""Measured performance of the local AI pipeline on THIS machine.

    python -m tests.performance.run_benchmarks [--out docs/benchmarks]

Every number is measured here; nothing is estimated. Components that are not
installed are reported as skipped. Speech input is synthesised with espeak-ng
(clearly synthetic audio) so runs are reproducible.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import time
from pathlib import Path

import numpy as np
import psutil

from backend.agents.question_detection import QuestionDetector
from backend.llm.ollama import GenerationStats, OllamaClient
from backend.models.hardware import detect
from backend.screen.frames import encode_png_b64
from tests.conftest import ollama_model_available, speech_wav
from tests.unit.test_screen_and_vision import text_image

TEXT_MODEL = "qwen2.5:1.5b"
VISION_MODEL = "qwen2.5vl:3b"


def stats(xs: list[float]) -> dict:
    xs = sorted(xs)
    return {"n": len(xs), "p50": statistics.median(xs), "min": xs[0], "max": xs[-1], "mean": statistics.fmean(xs)}


async def bench_llm(client: OllamaClient, runs: int) -> dict:
    out = []
    prompts = ["Explain what a hash map is in two sentences.", "Name three uses of a queue.", "What is a mutex? One sentence."]
    for i in range(runs):
        st = GenerationStats(model=TEXT_MODEL)
        async for _ in client.chat_stream(
            TEXT_MODEL, [{"role": "user", "content": prompts[i % 3]}], options={"num_predict": 128, "temperature": 0}, stats=st
        ):
            pass
        out.append(st)
    warm = out[1:] or out
    return {
        "model": TEXT_MODEL,
        "cold_first_token_ms": out[0].first_token_ms,
        "warm_first_token_ms": stats([s.first_token_ms for s in warm]),
        "tokens_per_second": stats([s.tokens_per_second for s in warm if s.tokens_per_second]),
        "total_ms": stats([s.total_ms for s in warm]),
    }


async def bench_vision(client: OllamaClient, runs: int) -> dict:
    img = encode_png_b64(
        text_image(["Traceback (most recent call last):", "  File 'app.py', line 12", "KeyError: 'user_id'"], size=(1280, 720))
    )
    res = []
    for _ in range(runs):
        st = GenerationStats(model=VISION_MODEL)
        async for _ in client.chat_stream(
            VISION_MODEL,
            [{"role": "user", "content": "What error is shown? One sentence.", "images": [img]}],
            options={"num_predict": 64, "temperature": 0},
            stats=st,
        ):
            pass
        res.append(st)
    return {
        "model": VISION_MODEL,
        "image": "1280x720 PNG",
        "first_token_ms": stats([s.first_token_ms for s in res]),
        "total_ms": stats([s.total_ms for s in res]),
    }


def bench_asr(sizes: list[str], runs: int, tmp: Path) -> dict:
    from backend.transcription.asr import WhisperTranscriber

    audio = speech_wav("How does a hash map handle collisions when two keys share a bucket?", tmp / "q.wav")
    if audio is None:
        return {"skipped": "espeak-ng/ffmpeg missing"}
    secs = audio.size / 16000
    out = {"audio_seconds": round(secs, 2), "models": {}}
    for size in sizes:
        asr = WhisperTranscriber(size)
        t0 = time.perf_counter()
        asr.load()
        load_ms = (time.perf_counter() - t0) * 1000
        times, text = [], ""
        for _ in range(runs):
            t0 = time.perf_counter()
            text = asr.transcribe(audio, beam_size=3, use_vad=False).text
            times.append((time.perf_counter() - t0) * 1000)
        partial = []
        for _ in range(runs):
            t0 = time.perf_counter()
            asr.transcribe(audio[: int(1.5 * 16000)], beam_size=1, use_vad=False)
            partial.append((time.perf_counter() - t0) * 1000)
        out["models"][size] = {
            "load_ms": load_ms,
            "final_ms": stats(times),
            "real_time_factor": statistics.median(times) / 1000 / secs,
            "partial_1_5s_ms": stats(partial),
            "transcript": text,
        }
    return out


def bench_vad(tmp: Path) -> dict:
    from backend.transcription.vad import make_vad

    vad = make_vad()
    audio = np.zeros(1024 * 156, np.float32)  # ~10 s, whole 512-sample windows
    t0 = time.perf_counter()
    for i in range(0, audio.size, 1024):
        vad.probabilities(audio[i : i + 1024])
    ms = (time.perf_counter() - t0) * 1000
    return {"vad": vad.name, "ms_per_second_of_audio": ms / (audio.size / 16000)}


def bench_embeddings_and_faiss() -> dict:
    import faiss

    from backend.rag.embed import Embedder

    emb = Embedder()
    emb.embed(["warm up"])
    texts = [f"Passage {i}: the service stores vectors with FAISS and serves {i} queries per second." for i in range(256)]
    emb._cache.clear()
    t0 = time.perf_counter()
    emb.embed(texts)
    embed_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    emb.embed(["what index stores vectors"])
    query_ms = (time.perf_counter() - t0) * 1000
    rng = np.random.default_rng(0)
    for n in (10_000, 100_000):
        vecs = rng.standard_normal((n, emb.dim)).astype(np.float32)
        faiss.normalize_L2(vecs)
        idx = faiss.IndexFlatIP(emb.dim)
        idx.add(vecs)
        q = vecs[:1]
        t0 = time.perf_counter()
        for _ in range(50):
            idx.search(q, 15)
        search = (time.perf_counter() - t0) * 1000 / 50
        if n == 10_000:
            s10k = search
        else:
            s100k = search
    return {
        "model": emb.model_name,
        "passages_per_second": len(texts) / embed_s,
        "query_embed_ms": query_ms,
        "faiss_flat_search_ms_10k": s10k,
        "faiss_flat_search_ms_100k": s100k,
    }


def bench_ocr(runs: int) -> dict:
    from backend.vision.ocr import run_ocr, tesseract_available

    if not tesseract_available():
        return {"skipped": "tesseract missing"}
    img = text_image([f"line {i}: def handler(event, context): return process(event['body'])" for i in range(12)], size=(1280, 720))
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        run_ocr(img)
        times.append((time.perf_counter() - t0) * 1000)
    return {"image": "1280x720, 12 lines of code", "ms": stats(times)}


async def bench_question_detection() -> dict:
    d = QuestionDetector()
    texts = ["How does a hash map handle collisions?", "Thanks, that makes sense.", "Design a scalable notification system"] * 100
    t0 = time.perf_counter()
    for t in texts:
        await d.detect(t, escalate=False, remember=False)
    return {"rules_ms_per_utterance": (time.perf_counter() - t0) * 1000 / len(texts)}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/benchmarks")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--asr", default="tiny,base,small")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(__import__("tempfile").mkdtemp())
    hw = detect()
    report: dict = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "machine": {
            "os": f"{hw['os']['system']} {hw['os']['release']}",
            "cpu": hw["cpu"]["name"],
            "cores": f"{hw['cpu']['physical_cores']} physical / {hw['cpu']['logical_cores']} logical",
            "ram_gb": hw["ram_gb"],
            "gpu": [g["name"] for g in hw["gpus"]] or "none",
            "python": platform.python_version(),
            "ollama": hw["runtimes"]["ollama"],
        },
    }
    client = OllamaClient("http://127.0.0.1:11434")
    report["question_detection"] = await bench_question_detection()
    report["vad"] = bench_vad(tmp)
    report["ocr"] = bench_ocr(args.runs)
    report["embeddings_faiss"] = bench_embeddings_and_faiss()
    report["asr"] = bench_asr(args.asr.split(","), args.runs, tmp)
    report["llm"] = await bench_llm(client, args.runs + 1) if ollama_model_available(TEXT_MODEL) else {"skipped": f"{TEXT_MODEL} missing"}
    report["vision"] = await bench_vision(client, 2) if ollama_model_available(VISION_MODEL) else {"skipped": f"{VISION_MODEL} missing"}
    report["backend_process_rss_mb_after_loading_models"] = psutil.Process().memory_info().rss / 1e6
    await client.aclose()
    (out_dir / "latest.json").write_text(json.dumps(report, indent=2, default=float))
    print(json.dumps(report, indent=2, default=float))


if __name__ == "__main__":
    asyncio.run(main())
