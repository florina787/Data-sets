# Installing VEENA.AI

No terminal, no account, no API key and no payment are needed. Allow 5 to 20 minutes, mostly for downloads.

## 1. Download

Open the VEENA.AI website and press the button for your computer:

| Your computer | File |
|---|---|
| Windows 10 or 11 (64-bit) | `VEENA.AI-Windows-Setup.exe` |
| Mac with Apple Silicon (M1, M2, M3, M4) | `VEENA.AI-macOS-AppleSilicon.dmg` |
| Linux x86_64 | `VEENA.AI-Linux-x86_64.AppImage` |

Not sure which Mac you have? Apple menu → **About This Mac**. "Chip: Apple M…" means Apple Silicon. Intel Macs are not supported yet.

Optional check: each release lists a SHA-256 checksum for every file. Windows: `Get-FileHash VEENA.AI-Windows-Setup.exe` in PowerShell. macOS/Linux: `shasum -a 256 <file>`. The result should match the release page.

## 2. Install

**Windows**
1. Double-click `VEENA.AI-Windows-Setup.exe`.
2. This beta is not yet code-signed, so Windows may show **"Windows protected your PC"**. Choose **More info**, check that the app is `VEENA.AI-Windows-Setup.exe`, then **Run anyway**. Only do this for a file you downloaded from the official VEENA.AI release page.
3. Choose where to install, or keep the default, which installs for your account only with no administrator rights. Press **Install**.
4. VEENA appears on your desktop and in the Start menu.

**macOS**
1. Open `VEENA.AI-macOS-AppleSilicon.dmg` and drag **VEENA.AI** into **Applications**.
2. The first time, open it from Applications. If macOS says it cannot verify the developer, open **System Settings → Privacy & Security**, scroll to the VEENA.AI message and choose **Open Anyway**. This happens because the beta is not yet notarised by Apple.

**Linux**
1. Make the file executable: right-click → Properties → Permissions → *Allow executing as program* (or `chmod +x VEENA.AI-Linux-x86_64.AppImage`).
2. Double-click it.

## 3. First-time setup (inside VEENA)

VEENA opens a guided setup. Each step can be resumed if you close VEENA.

1. **Welcome**: what setup will do.
2. **Your computer**: VEENA checks memory, disk and graphics, and recommends a profile (Lite, Balanced or Performance).
3. **AI runtime**: VEENA uses Ollama, a free local AI runtime. If you already have Ollama, it is used. Otherwise press **Download and set up**:
   - about 1.6 GB on Windows and Linux, 0.2 GB on macOS;
   - checked against the official SHA-256 before anything runs;
   - installed for your account inside VEENA's folder.
4. **Models**: press **Download** next to the recommended text model (and, optionally, the vision model for screen analysis). You can cancel and retry; downloads resume.
5. **Privacy**: how your data is stored, and whether VEENA may check for updates.
6. **Permissions**: optionally allow and test the microphone. Screen sharing is asked for only when you first share a screen.
7. **First answer**: VEENA asks the model a question on your computer. **"VEENA is ready."** appears only after it really answers. Press **Finish setup**.

## 4. Use it

- **Conversation:** type, or press **Listen** and speak.
- **Knowledge:** add documents, then tick the collection to get cited answers.
- **Meeting Copilot:** start a session you are authorised to capture; a recording indicator stays visible.
- **Screen Intelligence:** pick a screen or window; a Sharing pill with **Stop** stays visible.
- **Library:** reopen earlier conversations. **Agents** and **Analytics** show how answers were checked and how fast they were.

## Updating

If update checks are on, VEENA shows a notice when a new version is published. Download the new installer from the release page and install it over the old one. Your conversations, documents and settings are kept.

## Uninstalling

- **Windows:** Settings → Apps → VEENA.AI → Uninstall.
- **macOS:** drag VEENA.AI from Applications to the Bin.
- **Linux:** delete the AppImage.

Uninstalling keeps your data so a reinstall picks it up. To remove everything, including downloaded models (several GB), delete the data folder:

| | Folder |
|---|---|
| Windows | `%APPDATA%\VEENA.AI` |
| macOS | `~/Library/Application Support/VEENA.AI` |
| Linux | `~/.config/VEENA.AI` |

If you installed Ollama yourself, its models are in its own folder (`~/.ollama`) and are not touched.
