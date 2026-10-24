# Benchmarks

Measured, not estimated. Raw output: [`benchmarks/latest.json`](benchmarks/latest.json).
Reproduce with:

```bash
python -m tests.performance.run_benchmarks --out docs/benchmarks --asr tiny,base
```

The in-app Setup wizard runs a shorter benchmark on the user's own machine, and
Analytics shows live measurements from real use.

## Test machine

| | |
|---|---|
| CPU | Intel Xeon @ 2.80 GHz, 4 vCPU (cloud VM) |
| RAM | 15.7 GB |
| GPU | none (all inference on CPU) |
| OS | Linux 6.18 |
| Ollama | 0.40.11 |
| Date | 2026-10-24 |

This is a modest CPU-only machine, roughly the "Balanced" profile without a GPU.
A laptop with a recent GPU or Apple Silicon will be considerably faster for the
language and vision models; nothing here was measured on such hardware.

## Results

| Stage | Model / method | Measured |
|---|---|---|
| Question detection | rules | 0.014 ms per utterance |
| Voice activity detection | Silero VAD v6 (ONNX) | 7.2 ms per second of audio |
| Speech, final transcript (4.3 s clip) | whisper tiny, int8 | p50 927 ms, real-time factor 0.22 |
| Speech, final transcript (4.3 s clip) | whisper base, int8 | p50 1650 ms, real-time factor 0.38 |
| Speech, partial (1.5 s of audio) | whisper tiny / base | p50 2387 / 2417 ms |
| Speech model load | tiny / base | 6.3 s / 10.7 s (first use per launch) |
| OCR, 1280×720 screenshot with 12 lines of code | Tesseract 5.3.4 | p50 671 ms |
| Embedding passages | all-MiniLM-L6-v2, CPU | 71 passages/s |
| Embedding one query | all-MiniLM-L6-v2 | 12 ms |
| Vector search, flat inner product | FAISS, 10k / 100k vectors | 3.4 ms / 9.5 ms |
| Text answer, first token (warm) | qwen2.5:1.5b Q4_K_M | p50 187 ms |
| Text answer, generation speed | qwen2.5:1.5b Q4_K_M | p50 21.2 tokens/s |
| Text answer, first token (cold) | qwen2.5:1.5b | 80 s: model loaded from disk right after an Ollama restart |
| Screen analysis, new 1440×900 screenshot, full app | qwen2.5vl:3b Q4_K_M | 48–81 s end to end (three E2E runs; the 81 s run had to reload the vision model after the text model ran) |
| Screen analysis, cold | qwen2.5vl:3b | 290 s including loading the 3.2 GB model |
| Backend memory after loading Whisper base + embeddings | process RSS | 968 MB (Ollama models are separate) |

### What the numbers mean

* **Speech is faster than real time** with tiny and base (factor 0.22 and 0.38),
  so finals keep up with continuous speech on this CPU.
* **Partials are not cheaper than finals.** Whisper processes audio in 30-second
  windows, so a 1.5-second partial costs about as much as a full utterance. On a
  4-core CPU partials arrive every 2–3 s rather than the configured 0.9 s
  (the pipeline skips partials while the ASR worker is busy, so it never falls
  behind). A GPU, or the tiny model, makes live partials smoother.
* **Text answers are interactive** once the model is loaded: the first word in
  under 0.2 s, then about 21 words per second with the 1.5B model. The first
  answer after starting Ollama waits for the model to load from disk. VEENA keeps
  models loaded for 30 minutes and offers a warm-up.
* **Screen analysis on CPU is slow.** Encoding a full screenshot with a 3B vision
  model takes about a minute here. Use region selection to send less, run on a
  machine with a GPU or Apple Silicon, or use the OCR-only path (no vision model)
  for text-heavy screens. A second run on an identical image returned in 3 s
  because Ollama reused its prompt cache; that figure is not representative and
  is excluded above.
* **Retrieval is not a bottleneck**: under 25 ms for query embedding plus search
  at the collection sizes a desktop user has.

## Optimisations in place

Model keep-alive and warm-up, streaming and cancellable generation, bounded
audio queues with drop-oldest backpressure, single-flight partial ASR, VAD-gated
transcription, frame change detection (dHash) in continuous screen mode,
image downscaling (1024 px on Lite, 1280 px otherwise), conversation context
trimmed to N turns, an LRU embedding cache, and modality routing so text
questions never touch vision or retrieval.
