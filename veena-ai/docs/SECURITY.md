# Security and privacy model

## What stays on the computer

| Data | Stored? | Where |
|---|---|---|
| Raw microphone / system audio | **Never.** Processed in memory, discarded | – |
| Screenshots and screen frames | **Never.** Kept in renderer memory only while shown | – |
| Transcripts, questions, answers, citations | Yes, until deleted or expired | SQLite in the app data folder |
| Uploaded documents | Extracted text chunks and vectors only (the original file is not kept) | SQLite + FAISS files |
| Settings and metrics | Yes | SQLite |

Delete one session, clear all history (Settings → Privacy), or set a retention
period (1 day to 1 year, or keep until deleted). SQLite `secure_delete` is on.

No telemetry is sent. The Electron main process sets `HF_HUB_DISABLE_TELEMETRY`,
`DO_NOT_TRACK` and `ANONYMIZED_TELEMETRY=False` for the backend, and cached
models load with `local_files_only=True`, so a configured app makes no network
requests. The only network traffic is model downloads that the user starts
(Ollama models, first-time Whisper and embedding weights from Hugging Face).

## Electron hardening

* `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, `webSecurity: true`.
* Preload exposes 11 methods; every IPC handler checks the sender frame is the
  app's own page and validates arguments (types, sizes, extensions, https-only links).
* Content Security Policy: scripts only from the app; network only to
  `127.0.0.1`; no frames, objects, forms or base URI.
* Navigation away from the app and new windows are blocked; https links open in
  the system browser.
* Permissions: only the app's own page may use the microphone (camera is never
  granted), display capture, and clipboard writes. Everything else is denied.
* Screen capture requires a source the user picked in VEENA's picker; the
  selection is single use and the display-media handler refuses otherwise.
  This is covered by an end-to-end test. No stealth capture, no capture of
  hidden windows, OS screen-recording permission is respected (macOS prompt).

## Backend hardening

* Binds to loopback only; a non-loopback `VEENA_HOST` or `OLLAMA_URL` is refused at startup.
* Every request except `/api/health` needs the per-launch bearer token
  (constant-time comparison). WebSockets take it as a subprotocol.
* Origin allowlist: the packaged app (`null` for fetch, `file://` for WebSocket)
  and the Vite dev server. Other origins get 403, so a web page in a browser
  cannot drive the backend even if it guesses the port.
* Uploads: extension allowlist, magic-byte checks, size limit, filename
  sanitising (directory parts, control characters, Windows reserved names),
  path containment checks for index files. Password-protected and binary-in-text
  files are rejected.
* Images: format allowlist (PNG/JPEG/WebP), 25 MB and 40-megapixel limits
  (decompression-bomb guard).
* Logs pass through a redaction filter (keys, tokens, passwords, card numbers, SSNs).
* Code found in screenshots or documents is never executed. VEENA has no code-execution feature.

## Prompt-injection defences

Screen OCR, documents, transcripts of other speakers, resumes and job
descriptions are treated as untrusted:

* They are placed inside `<untrusted kind="…">` blocks. Any text that would
  close a block or fake a system/assistant turn is neutralised.
* The system prompt says data blocks are never instructions and that the model
  must say when it ignored an embedded instruction.
* Known injection phrasing is detected and reported to the user as a note.
* The governance check flags citations to evidence that does not exist.

These reduce risk; a small local model can still be misled, so answers are
labelled with their sources and notes.

## Screen redaction

Before a frame reaches a model, OCR word boxes are scanned for secrets
(API-key prefixes, AWS keys, GitHub/Slack tokens, JWTs, long high-entropy
tokens, card numbers, values after labels such as "Password:"). Matches are
painted over in the image and replaced in the OCR text. This is best effort:
it cannot hide secrets OCR does not read (very small text, unusual fonts,
images). In continuous mode, a visible password field pauses analysis.

## Dependency scanning

Run `npm audit` in `apps/desktop` and `pip-audit` in the virtual environment.
At the time of writing `npm install` reported 0 known vulnerabilities.

## Reporting

Please report vulnerabilities privately to the repository owner rather than in a public issue.
