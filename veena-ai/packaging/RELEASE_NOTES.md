## Download

| Your computer | File |
| --- | --- |
| **Windows 10/11 (64-bit)** | `VEENA.AI-Windows-Setup.exe` |
| **Mac with Apple Silicon (M1–M4)** | `VEENA.AI-macOS-AppleSilicon.dmg` |
| **Linux x86_64** | `VEENA.AI-Linux-x86_64.AppImage` |

**You also need [Ollama](https://ollama.com/download)** (free). It runs the AI models on your computer. Install it first; VEENA's setup wizard then downloads a model for you.

## First launch

These builds are **not code-signed** yet, so your system will warn you once:

* **Windows:** SmartScreen says "Windows protected your PC". Click **More info → Run anyway**.
* **macOS:** open the `.dmg`, drag VEENA.AI to Applications, then **right-click the app → Open → Open**.
  If macOS still says the app is damaged, run `xattr -dr com.apple.quarantine /Applications/VEENA.AI.app` in Terminal.
* **Linux:** `chmod +x VEENA.AI-Linux-x86_64.AppImage`, then run it.

Check a download against `SHA256SUMS.txt` if you want to confirm it arrived intact.

## What has been tested

CI builds each installer and checks that the packaged app starts its bundled local service on Windows, macOS and Linux. Real AI answers through the packaged app have been tested on Linux only; Windows and macOS runners have no Ollama, and the Windows installer itself has not been clicked through by a person. No Intel Mac build yet. Please report problems as issues.
