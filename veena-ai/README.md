<p align="center">
  <img src="apps/desktop/assets/icon-256.png" width="128" alt="VEENA.AI ginger Persian cat logo" />
</p>

<h1 align="center">veena.ai</h1>
<p align="center"><em>Your intelligent conversation companion.</em></p>

VEENA.AI is a local-first desktop AI copilot. It listens to your conversation,
detects questions, understands a screen or window you choose to share, answers
from your own documents with citations, coaches interview practice, and writes
meeting notes. **Everything runs on your computer with free, open models. No
account, no API key, no subscription.**

| Speech | Screen | Documents | Models |
|---|---|---|---|
| faster-whisper + Silero VAD | Electron capture + Tesseract + Qwen2.5-VL | sentence-transformers + FAISS | Ollama (Qwen2.5 family) |

## Status

What has been built and verified, and how:

| Capability | State | Verified by |
|---|---|---|
| Local chat with streaming, stop, answer styles, Markdown/code/tables/Mermaid | Done | E2E against qwen2.5:1.5b |
| Microphone transcription, partials, question detection, auto-answer | Done | E2E with synthetic speech through Chromium's fake mic → real Whisper |
| System-audio capture | Windows only (Electron loopback) | Not exercised in automated tests |
| User-selected screen/window sharing, region crop, screenshot analysis | Done | E2E: real capture → OCR → qwen2.5vl:3b |
| Refusal of screen capture without a user pick | Done | E2E |
| Continuous screen understanding with change detection and sensitive-content pause | Done | Integration tests (sensitive pause, redaction); the sampling loop itself is not covered by automated tests |
| Secret redaction in screenshots | Done, best effort | Integration test with real Tesseract |
| Documents (PDF, DOCX, TXT, MD, CSV, JSON) with citations and evidence checks | Done | E2E (real embeddings) + integration |
| LangGraph routing to specialist agents + governance checks | Done | Integration |
| Interview practice (8 roles, generated questions, scored feedback, analytics) | Done | Integration (simulated model); not yet run end to end with a real model |
| Meeting copilot (notes, decisions, action items) | Done | Integration (simulated model); not yet run end to end with a real model |
| History search, export, delete, clear-all, retention | Done | Unit + integration + E2E |
| Hardware detection, profiles, model downloads, measured benchmark | Done | E2E (real benchmark) |
| Analytics and developer diagnostics from real measurements | Done | Integration |
| Installers | Windows NSIS, macOS DMG (unsigned), Linux AppImage/deb | CI builds all three and smoke-tests the packaged app on each OS |
| Optional Piper TTS / Parakeet ASR / code sandbox | Not built | See limitations |

## Install (users)

1. Install [Ollama](https://ollama.com/download) (free) and start it.
2. Install VEENA.AI from the CI artifacts or a release: `VEENA.AI-Setup-x.y.z.exe`,
   the `.dmg`, or the `.AppImage`.
3. Launch it. The setup wizard checks your hardware, recommends a profile,
   downloads models through Ollama, and benchmarks your machine.

Full walkthrough: [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

### What it costs

No money is required. You do pay in resources:

* **Downloads:** about 1–11 GB of models depending on profile (one time).
* **Disk:** the same, plus about 1.5 GB for the app (it bundles CPU PyTorch for embeddings).
* **Hardware time and electricity:** models run on your CPU/GPU. On the 4-core
  CPU-only test machine a text answer starts in about 0.2 s and streams at about
  21 tokens/s; a screen analysis takes about a minute. See [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

## Develop

Requirements: Python 3.11+, Node 22+, Ollama. Optional: Tesseract, espeak-ng and
ffmpeg (for the speech tests).

```bash
cd veena-ai
./scripts/setup.sh            # Windows: .\scripts\setup.ps1
ollama pull qwen2.5:1.5b && ollama pull qwen2.5vl:3b
cd apps/desktop && npm run dev
```

`npm run dev` compiles the Electron main process, starts the Vite dev server,
and launches Electron, which starts the backend from the repo's `.venv`.

### Tests

```bash
# Backend: deterministic suite (simulated LLM/embedder/ASR; real OCR and VAD) - runs in CI
.venv/bin/pytest -m "not ollama and not asr and not embeddings"
# Backend: real local models (needs Ollama models, downloads Whisper/MiniLM once)
.venv/bin/pytest -m "ollama or asr or embeddings"
# Frontend: unit/component tests, palette guard, types, lint
cd apps/desktop && npm test && npm run typecheck && npm run lint
# End to end: the real app + real backend + real models (Linux: under xvfb-run)
npm run build && npm run test:e2e
# Measured benchmarks
cd ../.. && .venv/bin/python -m tests.performance.run_benchmarks --asr tiny,base
```

Last local run: 115 backend tests (109 deterministic + 6 real-model), 15 frontend
tests, 9 E2E tests, all passing. Simulated components exist only in tests and
are labelled as such (`ScriptedLLM`, `HashEmbedder`, `FakeASR`).

### Build installers

`./scripts/build-installer.sh` builds for the current OS (PyInstaller cannot
cross-compile). [`.github/workflows/veena-ai-ci.yml`](../.github/workflows/veena-ai-ci.yml)
builds Windows, macOS and Linux installers and smoke-tests each packaged app.

## Layout

```
veena-ai/
├── apps/desktop/        Electron main + preload, React renderer, brand assets
├── backend/             FastAPI service (api, agents, llm, transcription, audio,
│                        vision, screen, rag, memory, security, analytics, models)
├── tests/               unit, integration, e2e (Playwright + Electron), performance
├── packaging/           PyInstaller spec and frozen-backend smoke test
├── scripts/             setup and build scripts
└── docs/                architecture, security, user guide, benchmarks, versions
```

Read next: [ARCHITECTURE](docs/ARCHITECTURE.md) · [SECURITY](docs/SECURITY.md) ·
[USER GUIDE](docs/USER_GUIDE.md) · [BENCHMARKS](docs/BENCHMARKS.md) ·
[TESTED VERSIONS](docs/TESTED_VERSIONS.md)

## Design

White, ivory, cream and five browns only: `#FFFFFF #FCFAF7 #F7F1E9 #EFE2D2
#D6B79B #B87848 #99613E #75462D #4A2C1C #2C1A12`. Tailwind's default palette
is removed, and a test fails if any other colour appears in the UI source.
Status is shown with shape and text, never traffic-light colours. The ginger
Persian cat is original artwork generated from one SVG source
(`apps/desktop/src/brand/catSvg.mjs`) for the app icon, favicon, installer art
and the animated in-app mascot (blink, listening, thinking; reduced motion respected).

## Known limitations

* **Speed on CPU:** vision analysis takes about a minute per screenshot without
  a GPU; Whisper partials arrive every 2–3 s on a 4-core CPU.
* **Unsigned builds:** Windows SmartScreen and macOS Gatekeeper warn on first launch.
  Code signing needs certificates the project does not have.
* **Platform coverage:** the full E2E suite with real models ran on Linux only. On
  Windows and macOS, CI verified the packaged app starts its bundled backend and
  renders, but no model answers were tested there (no Ollama on the runners) and
  the NSIS installer was built but not run.
* **System audio** capture is Windows only.
* **Redaction is best effort:** it masks only what OCR can read.
* **Scanned PDFs** without a text layer are not OCR'd at upload.
* **Not built:** Piper voice output (practice questions use the OS's own local
  voices instead), Parakeet ASR, and a code-execution sandbox. VEENA never
  executes code from screens or documents.
* **App size:** about 1.5 GB installed because embeddings use CPU PyTorch; an
  ONNX embedding path would cut this substantially.
* **Mid-size model accuracy:** small local models make mistakes; answers show
  their model, sources and governance notes so you can judge them.

## Ethics

VEENA is a companion for your own conversations, learning and preparation. It
is not designed for, and must not be used for, covert assistance in interviews
or assessments that prohibit AI, or for recording people without the consent
the law requires. Capture is always visible and started by you.

## License

GPL-3.0-or-later, same as this repository.
