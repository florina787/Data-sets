# VEENA.AI: verified capabilities, limitations and evidence (local repository audit)

Scope: what VEENA.AI actually does and how each claim is backed, drawn from the local repository at `/home/user/Data-sets/veena-ai` (docs, tests, CI workflow, backend/app code). I read only local files and changed nothing. "Source" links are absolute local file paths. The public repository is referenced in the docs as github.com/florina787/Data-sets ([MEDIUM_ARTICLE_FORESIGHT.md](file:///home/user/Data-sets/veena-ai/docs/MEDIUM_ARTICLE_FORESIGHT.md)).

Evidence grades used throughout:
- **Verified by automated test (E2E, real models)**: Playwright + Electron test against the real backend, Ollama (qwen2.5:1.5b, qwen2.5vl:3b), faster-whisper and Tesseract. Per the docs it ran **locally on Linux only** and is **not run in CI**.
- **Verified by automated test (integration/unit, simulated models)**: pytest with `ScriptedLLM`, `HashEmbedder` and `FakeASR` doubles, real Tesseract OCR and real Silero VAD. This suite runs in CI on ubuntu-latest.
- **Verified by automated test (real-model pytest)**: `tests/integration/test_real_models.py`, marked `ollama`/`asr`/`embeddings`. Local only, not in CI.
- **CI smoke test**: the packaged app starts, its bundled backend comes up, security basics are checked. No model answers.
- **Measured**: from `docs/benchmarks/latest.json` / BENCHMARKS.md on a 4-vCPU, no-GPU Linux VM.
- **Documented only**: stated in the docs; I found no test that asserts it.
- **Not verified**: the docs say it was not tested, or I found no evidence.

Important caveat: the repo contains no CI run logs or result artefacts. That CI *passes* is a claim in the README (badge "tests-140 passing"; "Last local run: 116 backend tests (110 deterministic + 6 real-model), 15 frontend tests, 9 E2E tests, all passing"). I confirmed what CI is *configured* to run, not that it went green.

---

## Features: what exists and how each is verified

### Takeaway
All the listed features are implemented. Typed chat, live mic transcription with question detection and auto-answer, user-picked screen capture with vision analysis, and document RAG with citations are E2E-tested against real local models, but only on Linux and only on a 4-vCPU CPU-only machine. Meeting Copilot and Interview Practice were tested only with a simulated LLM. The continuous-screen sampling loop and system-audio capture have no automated tests. The vision E2E test only checks that an answer is non-empty and labelled with the vision model; it does not check answer quality.

### Cited Findings

**Test suite inventory**
- There are 9 E2E tests in `tests/e2e/app.spec.ts`: renderer isolation, loopback + token auth, first-run setup with a real benchmark, a streamed typed answer, document indexing + citation, refusal of screen capture without a pick, user-selected screen analysis with the vision model, mic speech → transcription → question detection → answer, and session deletion. The file header says "Nothing here is mocked"; the mic input is synthesised speech (espeak-ng) played through Chromium's fake capture device — [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)
- The frontend has 15 Vitest tests across components (7), services (3), palette guard (3) and store (2) — [apps/desktop/src/test/](file:///home/user/Data-sets/veena-ai/apps/desktop/src/test/)
- The integration suite header reads: "API integration tests with SIMULATED models (ScriptedLLM, HashEmbedder, FakeASR). Real OCR (Tesseract) and the real Silero VAD run here" — [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py)

**Conversation (typed chat, streaming, stop, answer styles)**
- E2E: a typed question ("What is 12 plus 30") is answered by qwen2.5:1.5b, the answer contains "42" and the model name is shown → *verified by E2E (real model, Linux)* — [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)
- Integration (simulated LLM): streaming + persistence, coding intent routed to the code agent, history sent as context, recovery from model failure, a clear error when Ollama is down, a cancel endpoint, and cancellation actually stopping generation → *verified (simulated)* — [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py)
- Seven answer styles (Quick, Detailed, Technical Deep Dive, Code, Architecture, Tutorial, Practice Interview Answer), Summary, Suggest follow-ups, Markdown export → *documented*; export is integration-tested, but I found no test for each answer style — [USER_GUIDE.md](file:///home/user/Data-sets/veena-ai/docs/USER_GUIDE.md), [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py)
- The README status table says Markdown/code/tables/Mermaid rendering was verified by "E2E against qwen2.5:1.5b". The E2E test only asserts "42" in the answer, so rich rendering is not specifically asserted there → *partly documented only* — [README.md](file:///home/user/Data-sets/veena-ai/README.md), [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)

**Live transcription and question detection**
- E2E: synthetic speech ("What is the difference between a list and a tuple in Python?") goes through the fake mic to real Whisper. The test asserts the transcript shows "tuple", an "Answer" button appears in the detected-questions panel, and the answer mentions "tuple" → *verified by E2E (real Whisper + real LLM, Linux, synthetic TTS voice, single English sentence)* — [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)
- Pipeline design: AudioWorklet at 16 kHz → WebSocket → bounded drop-oldest queue → Silero VAD (32 ms windows, 300 ms pre-roll, 700 ms silence ends an utterance) → faster-whisper (int8 on CPU / float16 on CUDA). Partials come about every 0.9 s when the ASR worker is idle. Duplicate questions (≥85% similar within 90 s) are suppressed — [ARCHITECTURE.md](file:///home/user/Data-sets/veena-ai/docs/ARCHITECTURE.md)
- Unit tests cover: two utterances finalised, short blips discarded, partials then final with no stale partials, backpressure dropping the oldest frames, pause ignoring audio, and Silero separating speech from silence → *verified (unit)* — [test_streaming_transcriber.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_streaming_transcriber.py)
- Question detection is rules-first, escalating to the local LLM for ambiguous text. Unit tests cover intents, statements, pronoun follow-ups, duplicate suppression and escalation. A real-model test `test_real_question_escalation` exists (local only) — [test_question_detection.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_question_detection.py), [test_real_models.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_real_models.py)
- Real-model pytest: `test_real_whisper_transcribes_speech` and `test_real_audio_pipeline_end_to_end` (marked `asr`, local only) — [test_real_models.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_real_models.py)
- The benchmark transcripts contain real errors: tiny produced "two keen share a market", base produced "Hashmab … share a market" for a hash-map collision question → *measured; accuracy is imperfect, and there is no WER benchmark* — [latest.json](file:///home/user/Data-sets/veena-ai/docs/benchmarks/latest.json)
- **System-audio capture is Windows only** (Electron loopback; the code sets `streams.audio = "loopback"` only when `process.platform === "win32"`) and is "Not exercised in automated tests" → *not verified* — [README.md](file:///home/user/Data-sets/veena-ai/README.md), [main.ts](file:///home/user/Data-sets/veena-ai/apps/desktop/electron/main.ts)

**Screen intelligence (consent, analysis, redaction, continuous mode)**
- E2E: `getDisplayMedia` called without a user pick is refused (the test asserts the result is not "granted") → *verified by E2E* — [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)
- E2E: the user opens the picker, picks a source and shares; a "Stop sharing" control and a live preview are visible; "Summarize Screen" runs qwen2.5vl:3b; the answer bubble is non-empty and labelled with the vision model; stopping removes the share. **The test does not check what the answer says** → *verified by E2E (pipeline works; quality not asserted)* — [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)
- Real-model pytest `test_real_vision_reads_error_on_screen` checks that qwen2.5vl:3b's answer mentions "KeyError" or "user_id" for a synthetic traceback image → *verified (real model, local only; one synthetic image)* — [test_real_models.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_real_models.py)
- Integration (simulated LLM, real Tesseract): screen analysis uses the vision model plus OCR; a password is redacted before reaching the model (the asserted text is absent from the model input); with no vision model it falls back to OCR text only and says so; bad images are rejected; screenshots are not persisted (no png/jpg/webp in the data dir) → *verified (integration)* — [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py)
- Continuous mode: the integration test `test_continuous_mode_pauses_on_sensitive` asserts a `paused_sensitive` event and that nothing is sent to the model. The README says "the sampling loop itself is not covered by automated tests" (dHash change detection ≥12 bits, pause when hidden). A unit test checks that the change detector skips identical frames → *sensitive-pause verified; the live sampling loop is not verified* — [README.md](file:///home/user/Data-sets/veena-ai/README.md), [test_screen_and_vision.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_screen_and_vision.py)
- Redaction covers API-key prefixes, AWS keys, GitHub/Slack tokens, JWTs, high-entropy tokens, Luhn-valid card numbers and values after labels like "Password:". It is "best effort" and "cannot hide secrets OCR does not read" — [SECURITY.md](file:///home/user/Data-sets/veena-ai/docs/SECURITY.md), [test_security.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_security.py)
- Region crop and keyboard shortcuts (Ctrl/⌘+Shift+S etc.) → *documented only* (no specific test found) — [USER_GUIDE.md](file:///home/user/Data-sets/veena-ai/docs/USER_GUIDE.md)

**Knowledge / RAG with citations**
- Supported formats: PDF, DOCX, TXT, MD, CSV, JSON, up to 50 MB each. Indexing uses all-MiniLM-L6-v2 + FAISS. Reranking is 0.75 × cosine + 0.25 × keyword score, with a relevance floor — [USER_GUIDE.md](file:///home/user/Data-sets/veena-ai/docs/USER_GUIDE.md), [ARCHITECTURE.md](file:///home/user/Data-sets/veena-ai/docs/ARCHITECTURE.md)
- E2E: `falcon.md` is indexed with real embeddings; the answer shows a "[1] falcon.md" citation button and mentions "HNSW" → *verified by E2E (real embeddings + real LLM, one small doc)* — [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)
- Integration: upload → duplicate detection → search → cited answer, routed to the knowledge agent, documents wrapped in `<untrusted kind="documents">`, `governance.grounded == True`. Also covered: a no-evidence flag, neutralising injection embedded in a document, upload validation (.exe, a fake PDF and empty files rejected) and collection deletion — [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py)
- Unit tests cover PDF page numbering, DOCX tables, CSV/JSON flattening, magic-byte checks, chunk overlap and lexical scoring. Real-model `test_real_embeddings_rank_and_threshold` runs locally only — [test_rag_units.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_rag_units.py), [test_real_models.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_real_models.py)
- There is no retrieval-quality benchmark (recall/precision) over a realistic corpus → *not measured*.

**Governance checks**
- Governance flags citations to passages that don't exist, retrieved evidence that wasn't cited, knowledge questions with no evidence, and (in practice interviews) first-person experience or figures without a resume to back them — [ARCHITECTURE.md](file:///home/user/Data-sets/veena-ai/docs/ARCHITECTURE.md)
- `test_governance_flags` (unit), plus integration checks of `grounded` and `no_evidence` → *verified (unit/integration, simulated LLM)*. It is a rule-based post-check. It does not fact-check claims that aren't tied to citations — [test_models_and_governance.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_models_and_governance.py)

**Meeting Copilot**
- It produces a summary, key points, decisions, action items (owner/task/due) and open questions, and requires the user to confirm they are authorised to transcribe — [USER_GUIDE.md](file:///home/user/Data-sets/veena-ai/docs/USER_GUIDE.md)
- `test_meeting_summary` uses a scripted JSON reply and checks the Markdown action-item table. README: "Integration (simulated model); not yet run end to end with a real model" → *verified only with a simulated model; real-model quality not verified* — [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py), [README.md](file:///home/user/Data-sets/veena-ai/README.md)
- There is no shorthand-bullets-to-notes feature; the author says this is something Foresight has and VEENA lacks — [MEDIUM_ARTICLE_FORESIGHT.md](file:///home/user/Data-sets/veena-ai/docs/MEDIUM_ARTICLE_FORESIGHT.md)

**Interview Practice**
- There are 8 roles (Senior AI Engineer, Principal AI Engineer, AI Architect, Forward Deployed AI Engineer, Data Scientist, ML Engineer, Software Engineer, Solutions Architect) and 5 categories. Feedback gives a 0–10 score, strengths, improvements, an outline of a strong answer and a follow-up question — [interview.py](file:///home/user/Data-sets/veena-ai/backend/agents/interview.py), [USER_GUIDE.md](file:///home/user/Data-sets/veena-ai/docs/USER_GUIDE.md)
- `test_interview_flow` (scripted LLM) and `test_interview_bank_fallback_when_no_model` (falls back to a static question bank when no model is available). README: "not yet run end to end with a real model". The README screenshot caption says the real 1.5B feedback "can be inconsistent" → *simulated only* — [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py), [README.md](file:///home/user/Data-sets/veena-ai/README.md)

**Analytics and diagnostics**
- `test_metrics_are_real_measurements` asserts live `llm.total_ms` counts, backend RSS > 0 and message counts → *verified (integration)*. The dashboard UI itself is documented only — [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py), [USER_GUIDE.md](file:///home/user/Data-sets/veena-ai/docs/USER_GUIDE.md)

**Setup wizard (hardware detection, profiles, downloads, benchmark)**
- E2E: the welcome screen shows Memory and Recommended, "Ollama … is running", and a real benchmark result ("tokens/s · first token", "× real time") → *verified by E2E*. Model download progress is not specifically asserted — [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)
- Profiles: Lite (8 GB, qwen2.5:1.5b, whisper tiny), Balanced (16 GB, qwen2.5:3b, base), Performance (32 GB or 8 GB+ GPU, qwen2.5:7b, qwen2.5vl:7b, small). Profile recommendation is unit-tested (parametrised) — [USER_GUIDE.md](file:///home/user/Data-sets/veena-ai/docs/USER_GUIDE.md), [test_models_and_governance.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_models_and_governance.py)

**Privacy and retention controls**
- Raw audio and screenshots are never stored; transcripts, answers and citations go to SQLite; for documents only chunks and vectors are kept. `secure_delete` is on. Retention ranges from 1 day to 1 year or keep-until-deleted (default `retention_days: 30` in code) — [SECURITY.md](file:///home/user/Data-sets/veena-ai/docs/SECURITY.md), [store.py](file:///home/user/Data-sets/veena-ai/backend/memory/store.py)
- Tests: `test_retention_purge`, `test_search_export_delete` (unit); `test_delete_and_clear_history` (clear-all needs `confirm=True`), `test_settings_patch_and_retention`, `test_screenshots_are_not_persisted` (integration); E2E session deletion → *verified*. That raw audio is never written to disk has no dedicated test I found → *documented only* — [test_store.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_store.py), [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py)

**Security hardening**
- Electron runs with `contextIsolation`, no `nodeIntegration`, `sandbox`, a CSP, and an 11-method preload. E2E asserts that `require`/`process` are undefined in the renderer and that the bridge exposes only the expected methods → *verified by E2E* — [SECURITY.md](file:///home/user/Data-sets/veena-ai/docs/SECURITY.md), [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)
- The backend binds only to loopback with a per-launch 256-bit bearer token and an origin allowlist. Covered by E2E (127.0.0.1 URL, 401 without token), integration (`test_token_required`, `test_foreign_origin_rejected`, WS token/origin tests), unit `test_settings_refuse_non_loopback`, and the CI smoke tests → *verified* — [test_api.py](file:///home/user/Data-sets/veena-ai/tests/integration/test_api.py), [test_security.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_security.py)
- Upload hardening (path traversal, Windows reserved names, extension allowlist, magic bytes) and log redaction are unit/integration tested. Prompt-injection wrapping in `<untrusted>` blocks with neutralisation is tested. SECURITY.md admits that "a small local model can still be misled" — [test_security.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_security.py), [SECURITY.md](file:///home/user/Data-sets/veena-ai/docs/SECURITY.md)
- Dependency scanning is manual (`npm audit` / `pip-audit`): "At the time of writing npm install reported 0 known vulnerabilities". It is not in CI → *documented only* — [SECURITY.md](file:///home/user/Data-sets/veena-ai/docs/SECURITY.md), [veena-ai-ci.yml](file:///home/user/Data-sets/.github/workflows/veena-ai-ci.yml)

### Inferences
- The strongest evidence is Linux-only E2E against real but small models (1.5B text, 3B vision). It proves the pipelines connect end to end. It does not prove answer quality, because each E2E test checks a single keyword or just a non-empty answer.
- Meeting Copilot (the feature most comparable to Foresight's core use case) has the weakest evidence: simulated-model tests only.

### Gaps
- No evaluation set for answer, meeting-notes or interview-feedback quality, no ASR word-error rate, and no RAG retrieval benchmark.
- No test of multi-speaker, noisy, accented or non-English audio. The E2E uses one espeak-ng English sentence.
- No CI logs in the repo to confirm that the configured CI jobs actually passed.

---

## Platforms and packaging

### Takeaway
CI builds Windows (NSIS), macOS arm64 (DMG, unsigned) and Linux (AppImage). On each OS it smoke-tests the frozen backend and the packaged app: startup, loopback, token, renderer isolation and the setup screen. No model answers are tested on Windows or macOS. The full real-model E2E suite ran only locally on Linux, and the NSIS installer was built but never run.

### Cited Findings
- The CI `package` job matrix covers windows-latest (`--win`, `*.exe`), ubuntu-latest (`--linux`, `*.AppImage`) and macos-latest (`--mac`, `release/mac-arm64/…`, `*.dmg`). Signing is off (`CSC_IDENTITY_AUTO_DISCOVERY: "false"`). It runs `smoke_backend.py` and then `smoke-packaged.mjs` without `--ask` (so no model question). Linux runs under xvfb — [veena-ai-ci.yml](file:///home/user/Data-sets/.github/workflows/veena-ai-ci.yml)
- `smoke_backend.py` checks that `/api/health` returns 200, that `/api/sessions` without a token returns 401, and that `/api/status` and `/api/system/hardware` return 200. It needs no Ollama — [smoke_backend.py](file:///home/user/Data-sets/veena-ai/packaging/smoke_backend.py)
- `smoke-packaged.mjs` checks that the backend is ready within 180 s, the URL is loopback, a tokenless request gets 401, the renderer has no Node globals, and the "Welcome to VEENA" heading renders. It asks a real question ("2 plus 2", expects "4") only with `--ask` — [smoke-packaged.mjs](file:///home/user/Data-sets/veena-ai/apps/desktop/scripts/smoke-packaged.mjs)
- TESTED_VERSIONS: "Linux x64 (Ubuntu 24.04, Xvfb) … Full E2E suite against real models locally; packaged-app smoke test with a real model answer". For Windows x64 and macOS arm64: "Frozen-backend and packaged-app smoke tests in CI (no Ollama on the runner)". CI does not pass `--ask`, so the Linux real-answer packaged smoke was a local run — [TESTED_VERSIONS.md](file:///home/user/Data-sets/veena-ai/docs/TESTED_VERSIONS.md), [veena-ai-ci.yml](file:///home/user/Data-sets/.github/workflows/veena-ai-ci.yml)
- README limitation: "the full E2E suite with real models ran on Linux only … no model answers were tested there (no Ollama on the runners) and the NSIS installer was built but not run." Builds are unsigned, so SmartScreen and Gatekeeper warn on first launch — [README.md](file:///home/user/Data-sets/veena-ai/README.md)
- The README mentions a Linux `deb` in the status table, but CI uploads only the `.AppImage`, and TESTED_VERSIONS lists "AppImage + unpacked" → the deb is *not verified* — [README.md](file:///home/user/Data-sets/veena-ai/README.md), [TESTED_VERSIONS.md](file:///home/user/Data-sets/veena-ai/docs/TESTED_VERSIONS.md)
- Only macOS arm64 is built; there is no Intel macOS build — [TESTED_VERSIONS.md](file:///home/user/Data-sets/veena-ai/docs/TESTED_VERSIONS.md)
- CI backend job (ubuntu): ruff lint/format, then `pytest -m "not ollama and not asr and not embeddings"` with real Tesseract. Frontend job: typecheck, lint, Vitest, build. **E2E and real-model tests are not in CI** — [veena-ai-ci.yml](file:///home/user/Data-sets/.github/workflows/veena-ai-ci.yml)
- macOS needs the Screen Recording permission. The user must install Ollama separately — [USER_GUIDE.md](file:///home/user/Data-sets/veena-ai/docs/USER_GUIDE.md)

### Inferences
- "Runs on Windows, macOS and Linux" is accurate as "builds and launches on all three". Feature-level behaviour on Windows and macOS (mic, screen capture, macOS permission prompt, Windows loopback audio, model answers) has not been verified.

### Gaps
- No test on Intel Macs, ARM Linux, Windows ARM, or GPU or Apple Silicon inference.

---

## Models, swappability and measured performance

### Takeaway
The default models are Qwen2.5 (1.5B/3B/7B) for text and Qwen2.5-VL (3B/7B) for vision via Ollama, faster-whisper tiny/base/small for speech, Silero VAD and all-MiniLM-L6-v2 embeddings. All were measured on one 4-vCPU Intel Xeon VM with 15.7 GB RAM and no GPU. Only qwen2.5:1.5b, qwen2.5vl:3b and whisper tiny/base were tested. Text answers start in about 0.19 s when warm and stream at about 21 tokens/s. A full screenshot takes roughly 48–81 s warm (from E2E console timings not stored in latest.json); the raw benchmark file's vision numbers are a 290 s cold run and a 3 s prompt-cache hit.

### Cited Findings
- Models: Text is qwen2.5:1.5b (tests), with 3b/7b for profiles. Vision is qwen2.5vl:3b (tested) and 7b (profile). Speech is faster-whisper tiny/base (tested) and small+. VAD is Silero v6. Embeddings are all-MiniLM-L6-v2. "Vision support is detected from the capabilities Ollama reports … so other vision models (for example gemma3 or llava) also work" — the gemma3/llava claim is *documented only* — [TESTED_VERSIONS.md](file:///home/user/Data-sets/veena-ai/docs/TESTED_VERSIONS.md)
- Swappability: users choose models in Settings. Unit tests `test_text_model_prefers_setting_then_qwen` and `test_vision_model_only_from_capabilities` check the selection logic → *selection logic verified; non-Qwen models not tested* — [test_models_and_governance.py](file:///home/user/Data-sets/veena-ai/tests/unit/test_models_and_governance.py)
- The embedding model and ASR are not routed through Ollama (sentence-transformers and faster-whisper are loaded directly), so "any Ollama model" applies to the text and vision LLMs only — [ARCHITECTURE.md](file:///home/user/Data-sets/veena-ai/docs/ARCHITECTURE.md), [embed.py](file:///home/user/Data-sets/veena-ai/backend/rag/embed.py)
- Test machine: Intel Xeon @ 2.80 GHz, 4 vCPU cloud VM, 15.7 GB RAM, no GPU, Linux 6.18, Ollama 0.40.11, 2026-10-24. "nothing here was measured on such hardware [GPU / Apple Silicon]" — [BENCHMARKS.md](file:///home/user/Data-sets/veena-ai/docs/BENCHMARKS.md)
- Measured (n = 3 unless noted):
  - Question detection: 0.014 ms per utterance.
  - Silero VAD: 7.2 ms per second of audio.
  - Whisper tiny final on a 4.3 s clip: p50 927 ms, RTF 0.22.
  - Whisper base: p50 1650 ms, RTF 0.38, which is about 2.6× faster than real time.
  - Partials on 1.5 s of audio: p50 about 2.4 s for both models.
  - Model load: 6.3 s (tiny) / 10.7 s (base).
  - Tesseract OCR on a 1280×720 image: p50 671 ms.
  - MiniLM embeddings: 71 passages/s; one query takes 12 ms.
  - FAISS flat search: 3.4 ms at 10k vectors / 9.5 ms at 100k.
  - qwen2.5:1.5b warm first token: p50 187 ms; generation: p50 21.2 tok/s; cold first token: 80 s.
  - Backend RSS: 968 MB.
  
  Sources: [BENCHMARKS.md](file:///home/user/Data-sets/veena-ai/docs/BENCHMARKS.md), [latest.json](file:///home/user/Data-sets/veena-ai/docs/benchmarks/latest.json)
- Vision: BENCHMARKS.md reports "48–81 s end to end (three E2E runs…)" warm and 290 s cold. In latest.json, `vision.total_ms` has n = 2 with min 3,122 ms (a prompt-cache hit, which BENCHMARKS says is "not representative and is excluded") and max 290,366 ms (cold); its p50 of 146,744 ms is just the mean of those two. **The 48–81 s figures come from the E2E test's console log and are not stored in latest.json** — [BENCHMARKS.md](file:///home/user/Data-sets/veena-ai/docs/BENCHMARKS.md), [latest.json](file:///home/user/Data-sets/veena-ai/docs/benchmarks/latest.json), [app.spec.ts](file:///home/user/Data-sets/veena-ai/tests/e2e/app.spec.ts)
- On a 4-core CPU, partials arrive every 2–3 s instead of the configured 0.9 s — [BENCHMARKS.md](file:///home/user/Data-sets/veena-ai/docs/BENCHMARKS.md)
- Optimisations: 30-minute keep-alive (`"keep_alive": "30m"` in the Ollama client), warm-up, dHash change detection, image downscaling (1024/1280 px), an LRU embedding cache, and modality routing — [BENCHMARKS.md](file:///home/user/Data-sets/veena-ai/docs/BENCHMARKS.md), [ollama.py](file:///home/user/Data-sets/veena-ai/backend/llm/ollama.py)
- Download size is about 1–11 GB of models depending on profile; the app is about 1.5 GB installed because it bundles CPU PyTorch — [README.md](file:///home/user/Data-sets/veena-ai/README.md)

### Inferences
- These numbers describe small models on weak hardware. They cannot be compared directly with Foresight on Apple Silicon. In the comparison article the author says they have not benchmarked Foresight and have not run both apps side by side — [MEDIUM_ARTICLE_FORESIGHT.md](file:///home/user/Data-sets/veena-ai/docs/MEDIUM_ARTICLE_FORESIGHT.md)
- Sample sizes are tiny (n = 2–3), so p50 values are indicative only.

### Gaps
- No measurements of the 3B/7B text models, qwen2.5vl:7b, whisper small, GPU, or Apple Silicon.
- No sustained-session measurements: memory over an hour-long meeting, CPU load, battery or thermals.

---

## Licensing, source availability and cost

### Takeaway
VEENA.AI is GPL-3.0-or-later and the full source is in the repository. There is no license fee, account or API key. The user pays in downloads (about 1–11 GB), disk (+1.5 GB for the app) and local compute/electricity.

### Cited Findings
- The LICENSE file is the GNU GPL v3. README: "GPL-3.0-or-later, same as this repository" — [LICENSE](file:///home/user/Data-sets/veena-ai/LICENSE), [README.md](file:///home/user/Data-sets/veena-ai/README.md)
- "$0 per month", "Account or API key: None". Ollama is a separate free install. Commercial comparison: Parakeet AI lists $38/hour or $149.90/month (the author's cited pricing) — [README.md](file:///home/user/Data-sets/veena-ai/README.md)
- The project describes itself as "v0.1, unsigned builds"; the author is one person, building with AI assistance in "About 6 hours" — [MEDIUM_ARTICLE_FORESIGHT.md](file:///home/user/Data-sets/veena-ai/docs/MEDIUM_ARTICLE_FORESIGHT.md)
- Third-party model licenses (Qwen2.5, Whisper, MiniLM) are not documented in the repo → gap.

### Inferences
- GPL-3.0 copyleft affects anyone who redistributes modified versions. That matters for any organisation that wants to embed VEENA in proprietary software.

### Gaps
- No licence review of the bundled or downloaded models. No support, maintenance or update channel is described, and there is no auto-updater.

---

## Documented limitations and things not verified

### Takeaway
The project is unusually candid about its limits. The main unverified areas are: real-model behaviour on Windows and macOS; system audio (Windows only, untested); meeting and interview features with a real model; the continuous-screen sampling loop; and the "works offline" claim, which rests on code settings (telemetry env vars, `local_files_only=True`) rather than a test with the network disabled.

### Cited Findings
- Limitations stated in the README:
  - Vision takes about a minute per screenshot on CPU, and Whisper partials arrive every 2–3 s.
  - Builds are unsigned.
  - Real-model E2E ran on Linux only.
  - System audio is Windows only.
  - Redaction is best effort.
  - Scanned PDFs without a text layer are not OCR'd.
  - Piper TTS, Parakeet ASR and a code sandbox were not built ("VEENA never executes code from screens or documents").
  - The app is about 1.5 GB installed.
  - Small models make mistakes.
  
  Source: [README.md](file:///home/user/Data-sets/veena-ai/README.md)
- **Offline claim**: README says "Works offline after setup: Yes". SECURITY.md says the main process sets `HF_HUB_DISABLE_TELEMETRY`, `DO_NOT_TRACK` and `ANONYMIZED_TELEMETRY=False`, and cached models load with `local_files_only=True`, "so a configured app makes no network requests". The code confirms these settings in `backend.ts`, `embed.py` and `asr.py`. **I found no test that runs the app with networking disabled or monitors outbound traffic.** The integration suite "runs offline in CI" only in the sense that its models are simulated → *documented and supported by code, not verified by test* — [SECURITY.md](file:///home/user/Data-sets/veena-ai/docs/SECURITY.md), [backend.ts](file:///home/user/Data-sets/veena-ai/apps/desktop/electron/backend.ts), [embed.py](file:///home/user/Data-sets/veena-ai/backend/rag/embed.py), [asr.py](file:///home/user/Data-sets/veena-ai/backend/transcription/asr.py)
- The author says testing found that "'offline' mode quietly contacted the internet on startup", and that this is now fixed. That shows offline behaviour has regressed before, with no regression test guarding it — [MEDIUM_ARTICLE_FORESIGHT.md](file:///home/user/Data-sets/veena-ai/docs/MEDIUM_ARTICLE_FORESIGHT.md)
- Other items not verified according to the README status table:
  - System audio: "Not exercised in automated tests".
  - Continuous sampling loop: "not covered by automated tests".
  - Interview and Meeting Copilot: "not yet run end to end with a real model".
  
  Source: [README.md](file:///home/user/Data-sets/veena-ai/README.md)
- Prompt-injection defences "reduce risk; a small local model can still be misled" — [SECURITY.md](file:///home/user/Data-sets/veena-ai/docs/SECURITY.md)
- Ethics: the project says VEENA must not be used for covert help in AI-prohibited interviews or for recording people without legal consent. Capture is always visible and started by the user — [README.md](file:///home/user/Data-sets/veena-ai/README.md)
- The comparison article in the repo is self-published by the VEENA author. It compares features only ("I haven't run both apps side by side yet"), and its Foresight details come from Google's announcement and press coverage — [MEDIUM_ARTICLE_FORESIGHT.md](file:///home/user/Data-sets/veena-ai/docs/MEDIUM_ARTICLE_FORESIGHT.md)

### Inferences
- For a fair comparison with Foresight, VEENA's wider feature list (screen intelligence, citations, interview practice, three operating systems) should be weighed against its evidence: Linux-only real-model testing, small CPU-run models, and a v0.1 one-person project. Foresight's claims need the same evidence grading from its own sources.

### Gaps
- No evidence of real-world use by anyone other than the author: no user studies or issue tracker data in the repo.
- No accessibility audit, apart from a reduced-motion note in the README.
- No test with a network-disabled sandbox and no outbound-traffic capture.
