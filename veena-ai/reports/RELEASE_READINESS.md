# Release readiness: go / no-go

Date: 10 November 2026 · Branch `claude/amazing-babbage-qia83y` · Evidence CI run: [#18](https://github.com/florina787/Data-sets/actions/runs/42727331443) (all jobs green)

## Recommendation

| Release type | Decision |
|---|---|
| **Private beta** (installers shared directly with a few people who are told to expect a security warning) | **GO**, once the owner has run the manual acceptance test on one Windows PC and one Mac |
| **Public beta via a LinkedIn link** ("a customer clicks, installs and uses it without my help") | **NO-GO until code signing is done.** Unsigned installers trigger SmartScreen ("Windows protected your PC") and Gatekeeper ("cannot verify the developer"). Many non-technical people stop there, or learn to click through warnings, which is the wrong habit to teach. Everything else needed for that experience is built and verified in CI. |

## Definition of done, item by item

| Requirement | Status | Evidence |
|---|---|---|
| Windows user installs and runs on a clean supported machine | ✅ in CI (fresh runner, no Ollama); ⏳ manual person test | [CLEAN_INSTALL_TEST_RESULTS.md](CLEAN_INSTALL_TEST_RESULTS.md) |
| macOS user installs and runs on a clean supported machine | ✅ in CI (Apple Silicon); ⏳ manual person test | same |
| Linux installs and runs | ✅ in CI | same |
| No Python or Node.js installation required | ✅ frozen backend + Electron; the app never calls the runner's Python/Node | packaged-app and first-run steps |
| Local AI setup guided and reliable | ✅ 7-step wizard; runtime auto-download with SHA-256; disk checks; resume; retry | E2E + CI first run on 3 OSes |
| Default model has verified commercial-use rights | ✅ all defaults Apache-2.0; test and CI gate | [MODEL_LICENSE_AUDIT.md](MODEL_LICENSE_AUDIT.md) |
| Real AI response after installation | ✅ on all 3 OSes in CI; locally E2E with real models | CI #18; E2E 9/9 |
| Document retrieval and citations work | ✅ CI first run on 3 OSes; E2E; offline check | same |
| Local data persistence and deletion | ✅ tests; secure_delete | [SECURITY_AND_PRIVACY_AUDIT.md](SECURITY_AND_PRIVACY_AUDIT.md) |
| Critical security findings resolved | ✅ 15 + 1 dependency vulnerabilities fixed; pip-audit and npm audit clean in CI | CI security job |
| Supported offline features pass offline testing | ✅ 6/6 with the network disconnected | `docs/benchmarks/offline_check.json` |
| Installer integrity verified | ✅ SHA-256 per installer; SBOM | CI #18 |
| **Signing / notarization for the public platforms** | ❌ **not done**: no certificates | **Release held** for public beta |
| Real-model tests cover advertised features | ✅ chat, RAG, citations, hallucination flags, meeting notes, interview, screen, speech, model switching (wizard selection) | [REAL_MODEL_EVALUATION.md](REAL_MODEL_EVALUATION.md) |
| Documentation accurate | ✅ updated to what was verified | README, docs/, reports/ |
| Public download links verified | ⏳ no release exists yet; site buttons stay disabled until files exist | site build check in CI |
| Release explicitly approved | ⏳ **owner's decision** | – |

## Test counts (actual)

| Suite | Count | Result | Where |
|---|---|---|---|
| Backend deterministic | 145 | pass | local + CI |
| Backend real-model (Ollama, Whisper, MiniLM) | 7 | pass | local |
| Frontend (vitest) | 18 | pass | local + CI |
| End-to-end, real Electron + real models | 9 | pass | local (Linux) |
| Installer + first run on Windows, macOS, Linux | 3 jobs | pass | CI #18 |
| Security (pip-audit, npm audit, SBOM, licences) | 1 job | pass | CI #18 |
| Real-model evaluation tasks | 7 tasks × 5 models | see report | local |
| Network-disconnected check | 6 features | pass | local |

## Artifacts (CI #18, not yet released)

| File | SHA-256 |
|---|---|
| `VEENA.AI-Windows-Setup.exe` | `417672652678d2b13f2c1f0c91a88a5a21d9868903d688f83d344afbd722dd44` |
| `VEENA.AI-macOS-AppleSilicon.dmg` | `e6fe2bda29061963128ba1e8235b83e3ac8a46a5ae60b9fdd7cc59f33c7f899e` |
| `VEENA.AI-Linux-x86_64.AppImage` | `30528c9384cee34ca2baf95a198e54d23d848725e95488498a876af0024fea39` |

Release builds are produced fresh by the draft-release job, so their checksums will differ from these CI artifacts and will be listed in the release itself.

## Known defects and risks

| | Severity | Customer impact |
|---|---|---|
| Installers unsigned / not notarized | **High** (public launch) | Security warnings on first launch |
| Not yet tested by a non-technical person on their own computer | **High** | Unknown friction |
| Full-screen analysis about 2.4 min on a 4-vCPU CPU with the licensed 2B vision model | Medium | Slow screen feature on low-end PCs |
| Small models misfile meeting action items; qwen2.5:1.5b invented facts in 3 of 4 trap runs (flagged in the UI) | Medium | Notes and answers need checking |
| No Intel Mac build | Medium | Intel Mac users excluded |
| Fact check is lexical | Low | Cannot judge correct use of a backed term |
| macOS system audio, speaker labels, translation not built | Low | Feature gaps, documented |

## Owner's next actions, in order

1. **Run the manual acceptance test** ([script](CLEAN_INSTALL_TEST_RESULTS.md#manual-acceptance-test-for-the-owner)) on one Windows PC and one Mac, using the CI #18 artifacts.
2. **Get signing certificates.**
   - Apple Developer Program (US$99/year) → Developer ID Application certificate.
   - A Windows code-signing certificate.
   - Add them as repository secrets (`MAC_CSC_LINK`, `MAC_CSC_KEY_PASSWORD`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`, `WIN_CSC_LINK`, `WIN_CSC_KEY_PASSWORD`).
   - CI then signs and notarizes, and its "signature status" step will show it.
3. **Merge** the branch into the default branch.
4. **Create a draft release:** Actions → VEENA.AI CI → Run workflow → tick *create_draft_release*. Review the draft, then press **Publish release** yourself.
5. **Turn on the website:** Settings → Pages → Source: GitHub Actions. Then Actions → VEENA.AI website → Run workflow → tick *deploy*. The download buttons enable themselves once the release exists.
6. Post the website link (`https://florina787.github.io/Data-sets/`) on LinkedIn.

**Nothing has been published.** No release, deployment, purchase or account was created during this work.
