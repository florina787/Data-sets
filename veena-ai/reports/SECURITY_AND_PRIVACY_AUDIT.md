# Security and privacy audit

**Scope:** VEENA.AI desktop app (Electron, Python backend, managed Ollama runtime), its build and release pipeline, and the website. Performed on 9 November 2026 by code review, automated tests and live checks in this repository.

**This is an internal engineering review, not a certification.** No independent penetration test or formal audit has been done, and VEENA claims no security certification.

## Threat model

| Asset | Threat | Main controls |
|---|---|---|
| Conversations, transcripts, documents (local SQLite) | Other local apps or web pages reading them through the backend | Loopback-only bind, random per-launch token, origin allowlist |
| The customer's screen | Capture without consent; secrets reaching the model | Capture only after an explicit pick; visible Sharing pill; secret masking before analysis; screenshots never stored |
| Microphone | Silent recording | Capture only after **Listen**; recording indicator; audio never stored |
| The customer's computer | Malicious installer, tampered runtime download, unsafe archive, prompt injection leading to actions | SHA-256 checksums; pinned runtime hash; archive path checks; VEENA has no tools that act outside the app |
| Model output | Hallucination presented as fact | Citations, governance flags, semantic-spine "unbacked claims" check |
| Release pipeline | Accidental public release, overwritten release, secrets leakage | Draft-only on manual run, environment approval, published releases never overwritten, per-OS secrets |

## Controls verified

| Area | Control | Evidence |
|---|---|---|
| Local API authentication | 32-byte random token per launch (`crypto.randomBytes(32)`), so it rotates every launch; constant-time compare (`hmac.compare_digest`); required on every route except `/api/health` | `test_token_required`, `test_health_is_public`; E2E "backend is bound to loopback and rejects requests without the token" |
| Localhost binding | Backend refuses a non-loopback host; Ollama URL must be loopback; managed Ollama started with `OLLAMA_HOST=127.0.0.1:<port>` | `test_settings_refuse_non_loopback`; `config.py`; `ollama_runtime.ensure_running` |
| CORS / origins | Allowlist (`null` for the app's file:// pages); foreign origins rejected for HTTP and WebSocket | `test_foreign_origin_rejected`, `test_audio_ws_origin_rules` |
| WebSocket auth | Token as subprotocol; unknown sessions rejected | `test_audio_ws_requires_token`, `test_audio_ws_rejects_unknown_session` |
| Electron renderer | `contextIsolation`, `sandbox`, no `nodeIntegration`, `webSecurity`; navigation and new windows blocked; strict CSP (no remote scripts; network only to 127.0.0.1); IPC accepts only the app's own frame | E2E "renderer is isolated…" pins the exact list of 12 bridge functions |
| Prompt injection | Untrusted text (documents, OCR, transcripts) wrapped and neutralised; instructions in it reported and ignored | `test_injection_detection_and_wrapping`, `test_rag_injection_in_document_is_neutralised` |
| Malicious documents | Extension allowlist; content sniffing (a fake PDF is rejected); size limit; safe filenames | `test_upload_validation`, `test_extension_allowlist`, `test_sanitize_*` |
| Path traversal | `safe_join` blocks escapes; runtime archive members checked before extraction (zip) or extracted with tar `filter="data"` | `test_safe_join_blocks_traversal`, `test_unsafe_archive_paths_are_rejected` |
| Runtime download integrity | Fixed URL, pinned version, SHA-256 from the official release; a mismatch deletes the file and nothing runs | `test_checksum_mismatch_is_rejected_and_nothing_installed`; local end-to-end with the real Ollama binary |
| Consent for downloads | The runtime and models download only after the user presses Download in Setup | `Setup.tsx` RuntimeStep; no autostart download path in `app.py` |
| Screen capture | Refused without an explicit selection; single-use pick; redaction of detected secrets; pause on sensitive content in continuous mode; screenshots never persisted | E2E "screen capture is refused…"; `test_screen_redacts_password_before_model`, `test_continuous_mode_pauses_on_sensitive`, `test_screenshots_are_not_persisted` |
| Microphone | Requested only on Listen or in the Setup test (stream stopped immediately); OS permission flow on macOS | `Setup.tsx` PermissionsStep; `electron/main.ts` `media:access` |
| Secrets in logs | Log redaction filter for keys, tokens, card numbers | `test_log_filter_scrubs_records` |
| Deletion and retention | Delete session (with its traces), clear all history, 30-day retention by default, SQLite `secure_delete` | `test_delete_and_clear_history`, `test_settings_patch_and_retention`, `test_deleting_a_session_deletes_its_traces` |
| MCP tools / external actions | **Not applicable:** VEENA has no MCP tools and no feature that acts outside the app (no email, web, file writes beyond user-initiated exports). The only outbound actions are downloads the user starts, and the opt-out update check. | Code review of `backend/` and `electron/` |
| Updates | Notify only; never downloads or runs a binary; only links to `github.com/florina787/Data-sets/releases/` pages | `src/test/updates.test.ts` |
| Process cleanup | The runtime VEENA starts is stopped on quit, including on Windows, where Electron's kill skips cleanup | `backend.ts shutdown()` + `/api/runtime/stop`; `test_installed_runtime_starts_serves_and_stops`; CI first-run test asserts the runtime stops |

## Dependency and supply-chain checks

| Check | Result |
|---|---|
| `pip-audit` on VEENA's exact Python environment (117 packages) | **15 known vulnerabilities found** in transitive `filelock` 3.32.3 (12) and `setuptools` 78.1.0 (3). **Fixed** by pinning filelock 4.2.1 and setuptools 84.1.0. Re-audit: **no known vulnerabilities**. `torch` (CPU wheel) cannot be audited by pip-audit. |
| `npm audit --omit=dev` (shipped JavaScript) | **0 vulnerabilities**. Development-only tools have moderate findings (for example `minimatch` in the build toolchain); they are not shipped. |
| SBOM | CycloneDX for Python and npm, produced by CI (`security` job) |
| Licences | `pip-licenses` inventory in CI; model licences in [MODEL_LICENSE_AUDIT.md](MODEL_LICENSE_AUDIT.md); CI fails on a non-commercial default model |
| Installer integrity | SHA-256 per installer in the CI summary, release notes and `SHA256SUMS.txt` |
| Code signing / notarization | **Not done: no certificates.** Prepared in CI (`WIN_CSC_*`, `MAC_CSC_*`, `APPLE_*` secrets) and reported per build. |

## Network behaviour and offline test

**Connections VEENA makes:**
- **Setup, user-initiated:** the Ollama release on github.com (runtime), the Ollama model library (models), and Hugging Face (Whisper and MiniLM on first use).
- **Update check, opt-out:** api.github.com, at most once a day.
- **Nothing else:** no telemetry or analytics. Ollama itself may have its own outbound features (for example its cloud model option); VEENA does not use them.

**Disconnected test (real):** inside a Linux network namespace with only loopback, the check first confirmed the internet was unreachable (`Network is unreachable`). It then ran with real models, all passing ([offline_check.json](../docs/benchmarks/offline_check.json)): chat, cited document answers, meeting notes, interview practice, screen analysis with OCR and the vision model, and speech-to-text.

**Requires connectivity:**
- the runtime and model downloads;
- the first use of a speech size or of document search, if those models were not downloaded in Setup;
- the update check, which fails silently offline.

## Residual risks and recommendations

| Risk | Severity | Note / recommendation |
|---|---|---|
| Installers are unsigned | **High** for a public launch | SmartScreen and Gatekeeper warnings teach users to click through. Sign (Windows) and sign + notarize (macOS) before a broad public release. |
| Ollama's API on loopback is unauthenticated | Medium | Any local program can use the models (not VEENA's data). This is standard for Ollama. VEENA's own API stays token-protected. |
| No independent review | Medium | Commission a penetration test before selling to organisations. |
| `unbacked_claims` is lexical | Low | It can miss a correct-looking but wrong use of a backed entity, and flags harmless general terms on screen explanations. Documented in the UI and the reports. |
| Windows/macOS behaviour verified only on CI runners | Medium | Runners are not consumer machines; see [CLEAN_INSTALL_TEST_RESULTS.md](CLEAN_INSTALL_TEST_RESULTS.md). |

**VEENA is not "completely private" or "completely offline" in every respect.** The accurate claim, supported by the evidence above: after setup, its features work without internet, and VEENA itself sends no content or telemetry anywhere.
