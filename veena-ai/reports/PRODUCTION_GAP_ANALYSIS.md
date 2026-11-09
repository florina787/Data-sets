# Production gap analysis

Audit date: 9 November 2026, branch `claude/amazing-babbage-qia83y`.
Severity: **P0** blocks a public release; **P1** must fix before a broad launch; **P2** should fix soon; **P3** nice to have.
Status: **Fixed** (implemented and verified here), **Prepared** (implemented, needs the owner's action or resource), **Open**.

## Baseline, re-verified independently (not taken from earlier reports)

| Suite | Result on 9 Nov, before changes |
|---|---|
| Backend deterministic (pytest) | 129 passed |
| Backend real-model (Ollama, Whisper, MiniLM) | 3 passed, 3 **skipped**: Ollama was not running after a container restart. After starting it: 6 passed |
| Frontend (vitest) | 15 passed |
| End-to-end, real Electron + real models | 9 passed (after starting Ollama) |
| CI on GitHub | Last 3 runs: Windows and Linux built and smoke-tested; **macOS never got a runner** (cancelled after 15 minutes) |

After this work: 141 backend, 7 real-model, 18 frontend, 9 end-to-end, all passing locally (see [RELEASE_READINESS.md](RELEASE_READINESS.md)).

## Findings

| # | Area | Current implementation (before) | Evidence | Sev | Customer impact | Correction | Cx | Depends on | Verification | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Model licensing | Lite/Balanced defaulted to qwen2.5vl:3b; Balanced text qwen2.5:3b | Both "Qwen Research License … NON-COMMERCIAL PURPOSES ONLY" (model cards) | **P0** | Commercial distribution would breach the licence | Apache-2.0 defaults chosen by real-task evaluation; licence catalogue; test + CI gate | M | – | `test_every_recommended_model_allows_commercial_use`; CI security job | **Fixed** |
| 2 | AI runtime | Customer had to install Ollama by hand from a link | Old Setup step: "Install it from ollama.com/download" | **P0** | Non-technical users stop at step 2 | Managed runtime: reuse existing, or download the pinned official release with consent, SHA-256 check, safe extract, start/stop | L | GitHub release availability | 9 unit tests; local end-to-end with the real binary and model; CI first-run test on 3 OSes | **Fixed** (CI result pending) |
| 3 | First-run proof | Setup could finish without any model answering | Setup had no inference check | **P0** | "Ready" could be shown on a broken install | "VEENA is ready." only after a real answer; Finish disabled until then | S | #2 | E2E asserts Finish disabled until the real answer | **Fixed** |
| 4 | Public download | No release existed; README buttons pointed at missing files | `releases` empty | **P0** | Link from LinkedIn leads to 404 | Draft-release job (manual, approval-gated, never overwrites); website enables buttons only for files that exist | M | **Owner approval to publish** | Site test shows "Coming soon" with no release; CI builds artifacts | **Prepared** |
| 5 | Code signing / notarization | None | Signature status step in CI | **P0** for a broad public launch | SmartScreen / Gatekeeper warnings; many users stop or learn to click through | Signing wired to secrets per OS; status reported each build | M | **Certificates** (Apple Developer ID US$99/yr; Windows Authenticode) | CI "Report installer signature status" | **Prepared** |
| 6 | macOS build | Last 3 CI runs: macOS job never started | Jobs cancelled at 15 min with no runner | **P0** for macOS | No macOS installer | Runner pinned to `macos-15` | S | GitHub runner availability | Next CI run | **Open** until CI confirms |
| 7 | Clean-install testing | Only "packaged app starts" smoke tests | CI steps | **P1** | Installer, shortcuts and uninstall unverified | CI installs the real installer (NSIS /S, DMG copy, AppImage), checks shortcuts, launches the installed app, first-run test, uninstall | M | – | CI | **Fixed** (CI result pending); consumer-PC test **Open** |
| 8 | Runaway screen analysis | 5 min 20 s for one full-screen analysis | Ollama log: 4,095-token prompt (busy-screen OCR + image), no answer cap | **P1** | Screen feature appears hung | OCR capped with images; answers capped at 1,024 tokens | S | – | Regression tests; E2E 327 s → 141 s | **Fixed** |
| 9 | Speech language | Short questions transcribed in the wrong language | "What is a hash map?" → Japanese, p = 0.33 | **P1** | Wrong questions detected and answered | Low-confidence fallback to the user's language | S | – | Real-model regression test; offline check | **Fixed** |
| 10 | Vulnerable dependencies | filelock 3.32.3, setuptools 78.1.0 | pip-audit: 15 known vulnerabilities | **P1** | Exploitable libraries shipped | Pinned fixed versions; pip-audit and npm audit in CI | S | – | Re-audit: none; CI security job | **Fixed** |
| 11 | Orphaned runtime on Windows quit | Electron kills the backend with TerminateProcess, skipping cleanup | Code review of `backend.ts stop()` | **P1** | Ollama keeps running after VEENA closes | Graceful `/api/runtime/stop` before kill | S | – | Runtime tests; CI first-run asserts stop | **Fixed** |
| 12 | Model download robustness | No disk check, no cancel, generic errors | Setup code | **P1** | Fails midway on full disks | 507 with a clear message when space is short; cancel; retry (Ollama resumes and verifies layer digests) | S | – | Code; manual | **Fixed** (no automated test for the 507 path) |
| 13 | Setup resume, privacy, permissions | 4-step wizard; no privacy or permission steps; restart lost progress | Old Setup | **P1** | Users confused or stuck | 7-step wizard, persisted step, privacy and permissions screens | M | – | E2E walks all steps | **Fixed** |
| 14 | Updates | None | – | **P1** | Users stay on old versions | Notify-only daily check (opt-out); never installs unverified binaries | S | Published releases | Unit tests | **Fixed**; signed auto-update **Open** (needs signing) |
| 15 | Website | None | – | **P1** | The LinkedIn link would land on the source code | Static site + privacy policy + Pages workflow (manual deploy) | M | Owner enables Pages | Built and checked in CI (phone width, no overflow) | **Prepared** |
| 16 | SBOM / licences | None | – | **P2** | Enterprise buyers ask | CycloneDX + pip-licenses in CI | S | – | CI artifact | **Fixed** (CI pending) |
| 17 | Offline claim | "Offline" stated but untested with the network off | Earlier reports | **P1** | Claim could be false | Network-namespace test with real models | S | – | `offline_check.json`: 6/6 | **Fixed** |
| 18 | `unbacked_claims` false positives on screen answers | Every vision model's code explanation flagged | Evaluation run 2 | **P2** | Unnecessary warnings | When a screen is the only material, only unbacked figures raise the flag | S | – | `test_screen_only_answers_are_flagged_for_figures_not_general_names`; real-model recheck: no flag | **Fixed** |
| 19 | Meeting notes quality | Small models file action items under decisions | Evaluation: both text models fail the strict rule | **P2** | Notes need editing | Prompt and schema tuning; bigger model on capable machines | M | – | Strict meeting rule in `model_eval` | **Open** |
| 20 | Screen analysis speed | About 2.4 min full-screen on 4-vCPU CPU with the licensed 2B model | E2E 141 s | **P2** | Slow on low-end machines | Set expectations (done in docs); try smaller images or Gemma 4 E2B on a GPU or Apple Silicon | M | Test hardware | – | **Open** |
| 21 | Intel Mac build | arm64 only | electron-builder config | **P2** | Intel Mac users excluded | Add an x64 (or universal) DMG target and an Intel runner | M | Runner | CI | **Open** |
| 22 | macOS system audio | Not supported | Status table | **P3** | Meeting capture on macOS limited to the microphone | ScreenCaptureKit audio (macOS 13+) | L | – | – | **Open** |
| 23 | Speaker identification | Not implemented | – | **P3** | Transcripts not attributed | Local diarization model (licence review needed) | L | – | – | **Open** |
| 24 | Translation | Not implemented | – | **P3** | – | Whisper translate-to-English is available locally; kept off the launch path | M | – | – | **Open** (deferred by design) |
| 25 | Consumer clean machines | Only CI runners tested | – | **P1** | Unknown issues on real PCs and Macs | Run the [manual acceptance script](CLEAN_INSTALL_TEST_RESULTS.md#manual-acceptance-test-for-the-owner) with one non-technical person per OS | S | People and machines | Recorded results | **Open** |
| 26 | Gemma 4 evaluation | Not tested | Disk too small here | **P3** | Possibly better model left unused | Evaluate on a machine with 10+ GB free | S | – | `model_eval` | **Open** |
