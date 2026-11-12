# Known limitations — VEENA.AI 0.1.1 Free Public Beta

* **Unsigned installers.** Windows SmartScreen and macOS Gatekeeper warn on first launch. The macOS app is
  not signed with an Apple Developer ID and **not notarized**; open it via System Settings → Privacy &
  Security → Open Anyway (see `INSTALLATION.md`).
* **Platforms.** Built for Windows 10/11 x64, Macs with Apple Silicon, and Linux x86_64 only. Intel Macs,
  Windows on ARM and ARM Linux are not built yet.
* **Answers can be wrong.** Small local models make mistakes; VEENA shows sources and flags unbacked claims.
* **Speed depends on your computer.** On a 4-core computer without a GPU, a full-screen analysis can take
  several minutes.
* **System audio** capture works on Windows only; on macOS and Linux use the microphone.
* **Hiding VEENA from screen sharing** works on Windows 10 (2004) and later and on macOS; it is not available on Linux.
  On macOS 15 and later, some apps that capture with ScreenCaptureKit may still show VEENA: share a single window
  or use a second monitor to be sure. VEENA does not yet detect Teams or Zoom sharing automatically; switch it on yourself.
* **Unfamiliar terms.** Common technical terms are grounded by a built-in glossary; for other terms the answer depends on
  what the small local model knows and can be wrong (choose a larger model in Settings for better answers).
* **First-time downloads** (AI runtime and model, 1.5–5 GB) need internet and disk space.
* **Feedback and statistics need internet.** If the feedback service is unreachable, the website form says
  so and offers the email address florinaregius@yahoo.com instead.
* **Beta.** Features and wording may change; future versions may introduce paid plans. This beta is free.
