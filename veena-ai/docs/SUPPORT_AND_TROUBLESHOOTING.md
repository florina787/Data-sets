# Support and troubleshooting

Report problems on [GitHub Issues](https://github.com/florina787/Data-sets/issues). Include your operating system, VEENA version (About page) and what you saw. **Settings → Diagnostics → Show log** (or the **Show log** button on the error screen) gives a log with secrets redacted.

| Problem | What to do |
|---|---|
| Windows: "Windows protected your PC" | The beta is not yet code-signed. **More info → Run anyway**, only for a file from the official release page. |
| macOS: "cannot be opened because the developer cannot be verified" | **System Settings → Privacy & Security → Open Anyway** (beta is not notarised yet). |
| "VEENA's local service did not start" | Press **Try again**. If it persists, restart the computer; then send the log from **Show log**. |
| AI runtime download fails or stops | Press **Retry**: it resumes. Check the internet connection and that the disk has the free space shown. |
| "The downloaded runtime failed its integrity check" | The file was corrupted or altered and was deleted. Press **Retry**. If it keeps happening, report it: VEENA will not run an unverified file. |
| "Not enough free disk space" | Free the space shown, then **Retry**. Models and the runtime need several GB. |
| Model download fails | **Retry** resumes. Behind a company proxy, downloads may be blocked; ask IT to allow `ollama.com` and `github.com`. |
| "The model did not answer" in Setup | Press **Try again**: the first answer loads the model and can take a minute. On 8 GB computers close other apps. |
| Answers are slow | Use the Lite profile (Settings → Models), close other heavy apps, or plug in the laptop. |
| Microphone does not work | Windows: Settings → Privacy & security → Microphone → allow desktop apps. macOS: System Settings → Privacy & Security → Microphone → VEENA.AI. |
| Screen sharing shows a black image (macOS) | System Settings → Privacy & Security → Screen Recording → enable VEENA.AI, then restart VEENA. |
| Screen text is not read (Windows) | Install Tesseract OCR (optional); VEENA still analyses the image with the vision model. |
| An answer says "not found in what VEENA was given" | That is VEENA's fact check: a name or figure in the answer was not in your documents. Treat it with care. |
| Remove all data | Settings → **Clear all history** (knowledge collections are kept; delete them in Knowledge), or delete the data folder listed in the installation guide. |

## Works without internet?

After setup: chat, document answers, meeting notes, interview practice, screen analysis and speech-to-text were tested with the network disconnected; see [`reports/SECURITY_AND_PRIVACY_AUDIT.md`](../reports/SECURITY_AND_PRIVACY_AUDIT.md). Setup downloads and update checks need internet.
