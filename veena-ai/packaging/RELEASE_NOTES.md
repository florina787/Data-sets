## VEENA.AI 0.1.0 · Beta

**Your AI. Your computer. Your control.** A private, open-source AI companion for conversations, meetings, interview practice, documents and your screen. It runs on your own computer, with no subscription, account or API key.

### Download

| Your computer | File |
| --- | --- |
| **Windows 10/11 (64-bit)** | `VEENA.AI-Windows-Setup.exe` (about 570 MB) |
| **Mac with Apple Silicon (M1–M4)** | `VEENA.AI-macOS-AppleSilicon.dmg` (about 626 MB) |
| **Linux x86_64** | `VEENA.AI-Linux-x86_64.AppImage` (about 823 MB) |

You do **not** need to install anything else. On first launch VEENA's setup checks your computer and, with your permission, downloads the free local AI runtime (Ollama, MIT licence; about 1.6 GB on Windows and Linux, 0.2 GB on macOS, verified against its official SHA-256). It then downloads an Apache-2.0 AI model (1–4 GB). Setup says **"VEENA is ready."** only after the model has answered on your computer.

**Needs:** 8 GB RAM (16 GB recommended), about 8 GB free disk, and internet for the first-time downloads. After setup, chat, documents, meeting notes, interview practice, screen analysis and speech-to-text work without internet.

### This is a beta: installers are not code-signed yet

Your system will warn you once. Only continue for a file downloaded from this page:

* **Windows:** SmartScreen shows "Windows protected your PC". Choose **More info**, check the file name is `VEENA.AI-Windows-Setup.exe`, then **Run anyway**.
* **macOS:** open the `.dmg`, drag VEENA.AI to Applications, open it once, then go to **System Settings → Privacy & Security** and choose **Open Anyway**.
* **Linux:** make the AppImage executable (`chmod +x`), then run it.

Confirm a download is intact by comparing it with `SHA256SUMS.txt` below.

### What's in this release

* Guided 7-step setup with automatic local AI runtime, model download, privacy and permission steps, and a real first answer.
* Conversation with streaming answers, voice input and question detection.
* Documents (PDF, Word, text, Markdown, CSV, JSON) with clickable citations; the document-search model is built in.
* Screen intelligence on a screen or window you choose, with secret masking.
* Meeting notes from speech (summary, decisions, action items, open questions).
* Interview practice with generated questions and scored feedback.
* Agents page: each answer's facts are checked against what VEENA was given, and invented names and figures are flagged.
* Licensed defaults: every recommended model is Apache-2.0.

### How it was tested

Before this release, CI installed each installer on fresh Windows, macOS (Apple Silicon) and Linux machines with no AI runtime. On each one it launched the installed app, downloaded and verified the runtime, got a real model answer, a cited document answer and speech-to-text, then uninstalled. Full results: `veena-ai/reports/CLEAN_INSTALL_TEST_RESULTS.md`. Known limitations are listed in `veena-ai/reports/RELEASE_READINESS.md`.

Please report problems on GitHub Issues.

© 2026 Florina Regius · Released under the GNU General Public License v3.0
