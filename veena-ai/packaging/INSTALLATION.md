# Installing VEENA.AI 0.1.0 — Free Public Beta

Download only from the official release page: https://github.com/florina787/Data-sets/releases

| Your computer | File |
| --- | --- |
| Windows 10/11, 64-bit | `VEENA.AI-Windows-Setup.exe` |
| Mac with Apple Silicon (M1–M4) | `VEENA.AI-macOS-AppleSilicon.dmg` |
| Linux x86_64 | `VEENA.AI-Linux-x86_64.AppImage` |

**Needs:** 8 GB RAM (16 GB recommended), about 8 GB free disk, internet for the first-time downloads.
No account, credit card, subscription or API key is needed.

## 1. Check the download (optional, recommended)

Compare the file's SHA-256 with the line for that file in `SHA256SUMS`:

* **Windows (PowerShell):** `Get-FileHash .\VEENA.AI-Windows-Setup.exe -Algorithm SHA256`
* **macOS:** `shasum -a 256 VEENA.AI-macOS-AppleSilicon.dmg`
* **Linux:** `sha256sum -c SHA256SUMS --ignore-missing`

## 2. Install

The beta installers are **not code-signed** yet, so your system warns you once.

* **Windows:** run `VEENA.AI-Windows-Setup.exe`. If SmartScreen says "Windows protected your PC", choose
  **More info**, check the file name, then **Run anyway**. VEENA.AI appears in the Start menu.
* **macOS:** open the `.dmg` and drag **VEENA.AI** to **Applications**. The app is not signed or notarized by
  Apple: the first time you open it, macOS blocks it. Go to **System Settings → Privacy & Security**, scroll
  down and choose **Open Anyway**, then confirm.
* **Linux:** `chmod +x VEENA.AI-Linux-x86_64.AppImage` then `./VEENA.AI-Linux-x86_64.AppImage`.
  Some distributions need FUSE 2 (`libfuse2`) to run AppImages.

## 3. First launch

VEENA's setup checks your computer and, with your permission, downloads the free local AI runtime (Ollama,
MIT licence, verified against its official SHA-256) and an Apache-2.0 model (1–4 GB). Setup says
**"VEENA is ready."** only after the model has answered on your computer. Afterwards the AI features work
without internet.

## Privacy

* Your questions, documents, screens and recordings are processed and stored on your computer.
* Anonymous usage statistics are **off** by default. If you turn them on (Settings → Usage statistics), VEENA
  sends only a random installation ID, OS, app version and which features were used — never content. Turning
  it off deletes that installation's statistics from the server.
* Feedback is sent only when you submit the feedback form; the email field is optional.

## Uninstall

* **Windows:** Settings → Apps → VEENA.AI → Uninstall.
* **macOS:** drag VEENA.AI from Applications to the Trash.
* **Linux:** delete the AppImage.

Uninstalling keeps your local VEENA data (conversations, documents index, settings); delete it yourself if you no longer need it.

## Help

Share feedback or report a bug: https://florina787.github.io/Data-sets/feedback.html ·
Email: florinaregius@yahoo.com
