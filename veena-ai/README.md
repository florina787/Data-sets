<p align="center">
  <img src="apps/desktop/assets/icon-256.png" width="140" alt="VEENA.AI ginger Persian cat logo" />
</p>

<h1 align="center">veena.ai</h1>
<p align="center"><b>Your intelligent conversation companion.</b><br/>
A local-first desktop AI copilot that listens, reads the screen you choose, answers from your documents, and runs entirely on your own computer.</p>

<p align="center">
  <img alt="Cost: $0 per month" src="https://img.shields.io/badge/cost-%240%20%2F%20month-4A2C1C?style=flat-square" />
  <img alt="Runs locally" src="https://img.shields.io/badge/runs-100%25%20local-99613E?style=flat-square" />
  <img alt="Platforms" src="https://img.shields.io/badge/platforms-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-75462D?style=flat-square" />
  <img alt="License GPL-3.0" src="https://img.shields.io/badge/license-GPL--3.0-B87848?style=flat-square" />
  <img alt="Tests" src="https://img.shields.io/badge/tests-140%20passing-99613E?style=flat-square" />
</p>

<p align="center">
  <img src="docs/images/welcome.png" width="900" alt="VEENA.AI welcome screen" />
</p>

## Why it exists

Commercial AI conversation copilots charge per hour or per month; Parakeet AI,
for example, lists **$38 per hour of use or $149.90 per month** for unlimited use
([pricing sources](docs/MEDIUM_ARTICLE.md#the-bill-that-started-this)). Every
part of that pipeline (speech recognition, screen reading, language models,
document search) now has a free, open model that runs on a laptop. VEENA.AI puts
those together.

| | Typical paid copilot | VEENA.AI |
|---|---|---|
| Monthly cost | $149.90 per seat (list price example) | **$0** |
| Account or API key | Required | **None** |
| Where audio, screens and notes go | Vendor servers | **Your disk only** |
| Works offline after setup | No | **Yes** |
| Trade-off | Money | Speed on weak hardware (see [benchmarks](#measured-performance)) |

**Read the story on Medium:**
- [Parakeet AI Costs $149.90 a Month. I Built a $0 Replacement](https://medium.com/@florinaregius/parakeet-ai-costs-149-90-c94b8c0b4661)
- [Google Released an Offline AI Meeting Assistant. So I Built My Own — and It Does More](https://medium.com/@florinaregius/google-released-an-offline-ai-meeting-assistant-so-i-built-my-own-and-it-does-more-69ee5622b5a9)

## A tour

<table>
<tr>
<td width="50%"><b>Talk or type, get local answers</b><br/>Streaming answers with code, tables and diagrams. The model, speed and answer style are shown on every reply.<br/><img src="docs/images/conversation.png" alt="Conversation with a code answer" /></td>
<td width="50%"><b>Answers from your documents, with citations</b><br/>Click a citation to see the exact passage. If nothing matches, VEENA says so.<br/><img src="docs/images/citations.png" alt="Cited answer" /></td>
</tr>
<tr>
<td><b>You pick what it can see</b><br/>Capture only starts after you choose a screen or window in VEENA's own picker.<br/><img src="docs/images/screen-picker.png" alt="Screen and window picker" /></td>
<td><b>Screen Intelligence</b><br/>Explain code, find errors, explain architecture, or summarise. A permanent "Sharing" pill has a Stop button. <i>Shown: a real answer from the 3B vision model on CPU; small models give short, sometimes shallow answers.</i><br/><img src="docs/images/screen.png" alt="Screen analysis" /></td>
</tr>
<tr>
<td><b>Knowledge collections</b><br/>PDF, DOCX, TXT, Markdown, CSV and JSON, indexed locally with MiniLM and FAISS. Test retrieval scores directly.<br/><img src="docs/images/knowledge.png" alt="Knowledge collections" /></td>
<td><b>Meeting Copilot</b><br/>Summary, key points, decisions and action items from an authorised transcript.<br/><img src="docs/images/meeting.png" alt="Meeting notes" /></td>
</tr>
<tr>
<td><b>Interview Practice</b><br/>Generated questions for 8 roles, scored feedback, improvement tracking. For rehearsal only. <i>Shown: real feedback from the 1.5B model, which can be inconsistent.</i><br/><img src="docs/images/interview.png" alt="Interview practice feedback" /></td>
<td><b>Analytics from real measurements</b><br/>Pipeline latency, per-model speed, question categories, practice scores. Nothing is estimated.<br/><img src="docs/images/analytics.png" alt="Analytics" /></td>
</tr>
<tr>
<td><b>Hardware-aware setup</b><br/>Detects CPU, RAM, GPU and disk, recommends a profile, downloads free models, and benchmarks your machine.<br/><img src="docs/images/setup.png" alt="Setup wizard" /></td>
<td><b>Settings and privacy</b><br/>Choose models, speech model, retention period; clear all history in one click.<br/><img src="docs/images/settings.png" alt="Settings" /></td>
</tr>
</table>

All screenshots were captured from the real app with real local models by
[`apps/desktop/scripts/screenshots.mjs`](apps/desktop/scripts/screenshots.mjs).

## How it works

```mermaid
flowchart LR
  subgraph You["Your computer"]
    direction LR
    V["🎙️ Voice"] --> VAD["Silero VAD"] --> ASR["faster-whisper"] --> QD["Question detector"]
    S["🖥️ Screen you picked"] --> OCR["Tesseract OCR<br/>+ secret redaction"]
    D["📄 Your documents"] --> EMB["MiniLM embeddings<br/>+ FAISS"]
    QD --> G["LangGraph router<br/>specialist agents"]
    OCR --> G
    EMB --> G
    G --> LLM["Ollama<br/>Qwen2.5 / Qwen2.5-VL"]
    LLM --> GOV["Governance check<br/>citations · unsupported claims"]
    GOV --> UI["Streamed answer"]
    GOV --> DB[("SQLite")]
  end
```

No step leaves the machine. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

| Speech | Screen | Documents | Models | App |
|---|---|---|---|---|
| faster-whisper + Silero VAD | Electron capture + Tesseract + Qwen2.5-VL | sentence-transformers + FAISS | Ollama (Qwen2.5 family) | Electron + React + FastAPI |

## Measured performance

Measured on a 4-vCPU cloud VM with **no GPU** (roughly a budget laptop).
Reproduce with `python -m tests.performance.run_benchmarks`; charts by
`python -m tests.performance.make_charts`.

<p align="center"><img src="docs/images/chart-latency.png" width="860" alt="Median latency per pipeline stage" /></p>
<p align="center"><img src="docs/images/chart-speech.png" width="860" alt="Speech recognition latency, whisper tiny vs base" /></p>

Text answers start in about 0.2 s and stream at about 21 tokens/s; speech is
transcribed 2.6× faster than real time; analysing a full screenshot with the
vision model takes about a minute on CPU. Full table and caveats:
[docs/BENCHMARKS.md](docs/BENCHMARKS.md).

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

Last local run: 116 backend tests (110 deterministic + 6 real-model), 15 frontend
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
