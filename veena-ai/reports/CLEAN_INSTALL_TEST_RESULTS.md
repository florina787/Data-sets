# Clean-install test results

**Evidence run:** [VEENA.AI CI #18](https://github.com/florina787/Data-sets/actions/runs/42727331443), commit `a6babe8`, 10 November 2026. **All jobs passed.**
Each package job builds the installer, **installs it the way a customer does**, launches the installed app, runs the **first-run test**, uninstalls, and records checksum and signature status. The raw first-run JSON for each OS is in the run's `first-run-evidence-*` artifacts.

## What "clean" means here, honestly

| | GitHub runner | Customer PC |
|---|---|---|
| Ollama installed | **No** (verified: `runtime before: running false, system_binary null`) | Usually no |
| Python / Node installed | Yes, on the runner image, but **not used**: the app runs its own frozen backend and Electron | Usually no |
| GPU | None | Varies |
| Antivirus / SmartScreen / Gatekeeper prompts | Not exercised (silent install, CLI copy) | **Will appear** (installers unsigned) |
| A person clicking through the wizard | No (API-driven first run; the wizard UI itself is covered by the local E2E suite) | Yes |

So these results prove that the installers, packaged app, runtime download and model path work on fresh Windows, macOS and Linux machines. **They do not replace a test with a non-technical person on an everyday computer.** That test is still required; the script is below.

## Results

| Step | Windows (windows-latest) | macOS (macos-15, Apple Silicon) | Linux (ubuntu-latest) |
|---|---|---|---|
| Machine | Intel Xeon Platinum 8573C, 16 GB RAM | Apple M1 (virtual), 7 GB RAM | x86_64 |
| Installer | `VEENA.AI-Windows-Setup.exe` | `VEENA.AI-macOS-AppleSilicon.dmg` | `VEENA.AI-Linux-x86_64.AppImage` |
| Artifact size | 569,793,397 B | 626,490,297 B | 823,332,851 B |
| SHA-256 | `417672652678d2b13f2c1f0c91a88a5a21d9868903d688f83d344afbd722dd44` | `e6fe2bda29061963128ba1e8235b83e3ac8a46a5ae60b9fdd7cc59f33c7f899e` | `30528c9384cee34ca2baf95a198e54d23d848725e95488498a876af0024fea39` |
| Install method | NSIS `/S` (per-user, `%LOCALAPPDATA%\Programs\VEENA.AI`) | DMG mounted, app copied to `/Applications` | AppImage extracted |
| Desktop + Start-menu shortcuts | ✅ both found | n/a | n/a |
| Installed app launches, backend on loopback with token | ✅ backend ready in 3.8 s | ✅ (5.3 s in run #17) | ✅ |
| Renderer isolated, setup screen renders | ✅ | ✅ | ✅ |
| Hardware detection → profile | Balanced (16 GB) | Lite (7 GB) | ✅ |
| **First run:** no runtime present → download pinned Ollama, SHA-256 verified, unpacked, started | ✅ 1.59 GB `ollama-windows-amd64.zip` | ✅ 181 MB `ollama-darwin.tgz` | ✅ 1.51 GB `ollama-linux-amd64.tar.zst` |
| Model download (qwen2.5:0.5b) | ✅ | ✅ | ✅ |
| Real answer (health check) | ✅ "ready" in 1.65 s | ✅ "ready" in 4.0 s (run #17) | ✅ |
| Cited document answer (bundled MiniLM, no download) | ✅ "…p95 latency budget of 300 ms." | ✅ "Falcon's latency budget is 300 ms." | ✅ |
| Speech model downloaded and run | ✅ 0.11× real time | ✅ 0.15× real time | ✅ |
| Runtime stopped by VEENA, port closed | ✅ | ✅ | ✅ |
| Whole first-run step | 99 s | 114 s | 39 s |
| Uninstall | ✅ silent uninstaller removed `VEENA.AI.exe` | ✅ app removed | n/a (delete the file) |
| Signature | **Unsigned** (no certificate configured) | **Ad-hoc only; not notarized** ("does not have a ticket stapled") | n/a (SHA-256 only) |

The test model `qwen2.5:0.5b` answered "15" to "12 plus 30" on all three. It is used to prove the plumbing, not as a default (see [REAL_MODEL_EVALUATION.md](REAL_MODEL_EVALUATION.md)).

## Defects found by these tests

| Run | Finding | Cause | Fix |
|---|---|---|---|
| #13 and earlier | macOS job never started | `macos-latest` runner unavailable for 15 min | Pinned `macos-15` |
| #16 | macOS build failed: "not a file" | Unconfigured signing secrets arrive as empty strings; electron-builder treated empty `CSC_LINK` as a path | Empty signing variables are unset |
| #16, #17 | Windows first run stopped after the backend began printing download progress | **Test harness bug:** backend output captured in an unread pipe; Windows pipes hold a few KB, so the backend blocked on write. The real app (Electron) reads both streams continuously. Reproduced locally. | The test writes backend output to a file |
| #16 | (prompted by the above) a first-use download of the document-search model | – | MiniLM (Apache-2.0) is now bundled in the installer; document search needs no download, which also helps offline use |
| #14, #15 | Security job failed | lxml 5.4.0 (PYSEC-2026-87), pulled in by the SBOM tool into the audited environment | lxml pinned to 6.1.3; security tools run in their own environment |

## Measures not taken

Memory and CPU use during install and first run, and crash rate, were **not measured** on these runners. Time to first answer for a person (including reading the wizard and their own download speed) can only come from the manual test below.

## Manual acceptance test for the owner

Run once per platform with a person who has not seen VEENA, on their own everyday computer, and record the results here.

1. Send them only the website link. Do not help.
2. Record: minutes to download; whether they got past SmartScreen/Gatekeeper; minutes through Setup; whether "VEENA is ready." appeared; whether a question and a document question worked; anything they found confusing.
3. Afterwards: uninstall, and check the data folder can be deleted ([installation guide](../docs/CUSTOMER_INSTALLATION_GUIDE.md#uninstalling)).

| Date | OS / machine | Person | Installed unaided? | Ready in (min) | Answer OK? | Document OK? | Notes |
|---|---|---|---|---|---|---|---|
| | Windows | | | | | | |
| | macOS | | | | | | |
