# VEENA.AI user guide

## 1. Install

1. **Install Ollama** (free): <https://ollama.com/download>. Start it once; it runs in the background.
2. **Install VEENA.AI**: run `VEENA.AI-Setup-<version>.exe` (Windows), open the `.dmg`
   and drag VEENA to Applications (macOS), or run the `.AppImage` (Linux).
   Builds are unsigned for now, so Windows SmartScreen and macOS Gatekeeper will
   warn on first launch (Windows: *More info → Run anyway*; macOS: right-click →
   *Open*).
3. **Optional: Tesseract OCR** improves reading text on screen.
   Windows: [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki) (default folder is detected automatically).
   macOS: `brew install tesseract`. Linux: `sudo apt install tesseract-ocr`.

## 2. First-run setup

The wizard:

1. explains what runs locally and what it costs (downloads, disk, electricity);
2. detects your OS, CPU, RAM, GPU and free disk, and recommends a profile:

   | Profile | For | Text model | Vision model | Speech |
   |---|---|---|---|---|
   | Lite | 8 GB RAM, CPU | qwen2.5:1.5b | qwen2.5vl:3b (on demand) | whisper tiny |
   | Balanced | 16 GB RAM | qwen2.5:3b | qwen2.5vl:3b | whisper base |
   | Performance | 32 GB RAM or 8 GB+ GPU | qwen2.5:7b | qwen2.5vl:7b | whisper small |

3. downloads the models you choose through Ollama, with progress;
4. benchmarks your machine (tokens per second, first-token time, speech
   real-time factor). If speech runs slower than real time (factor above 1),
   pick a smaller speech model in Settings.

You can re-run setup from Settings at any time.

## 3. Conversation

* Type in the box and press **Enter** (Shift+Enter for a new line), or press
  **Listen** and speak. A dark "Microphone on" pill shows whenever VEENA is
  listening; **Pause** and **Stop** are next to it.
* Spoken questions appear under *Detected questions* in the right panel with
  their type (coding, architecture, behavioural, follow-up…). With
  *Auto-answer* on, VEENA answers them; otherwise press **Answer**.
* Choose an answer style per question (Quick, Detailed, Technical Deep Dive,
  Code, Architecture, Tutorial, Practice Interview Answer) or leave it on Auto.
* **Stop** halts an answer mid-stream; the partial answer is kept and marked.
* **Summary**, **Suggest follow-ups**, **Copy answer** and **Export** (Markdown)
  are in the header and under answers.

## 4. Screen Intelligence

1. Open *Screen Intelligence* and press **Choose screen or window**.
2. Pick an entire screen or one window, then **Share**. VEENA never picks for you.
   On Windows you can also capture system audio (what plays through your speakers).
3. While sharing, a "Sharing …" pill with **Stop** is always visible in the header.
4. Use **Explain Code**, **Find Errors**, **Explain Architecture**,
   **Summarize Screen**, or type any question ("Why is this failing?").
   **Select region** lets you drag a rectangle to analyse only part of the screen.
5. **Analyse changes automatically** samples the screen every few seconds and
   only analyses frames that changed. It pauses when VEENA is minimised and
   when a password field is visible.

Before analysis VEENA masks passwords, keys and tokens it can read. Frames are
never saved. On computers without a GPU, a screen answer takes about a minute
with the 3B vision model (see BENCHMARKS.md).

On macOS, allow VEENA under *System Settings → Privacy & Security → Screen
Recording* the first time.

## 5. Knowledge (documents)

1. Create a collection (Resume, Job descriptions, Projects, Technical
   documentation, Meeting notes, General).
2. Add PDF, DOCX, TXT, Markdown, CSV or JSON files (button or drag and drop, up to 50 MB each).
3. Tick **Use in answers** (or tick collections in the right panel of a conversation).
   Answers then cite passages as [1], [2]; click a citation to see the passage.
4. If nothing relevant is found, VEENA says so instead of guessing.

Scanned PDFs without a text layer cannot be indexed yet.

## 6. Interview Practice

Choose a role and focus, optionally a resume collection and a job description,
then **Start practice interview**. Answer by typing or with **Speak answer**,
then **Get feedback** for a 0–10 score, strengths, improvements, an outline of a
strong answer and a follow-up question. The right panel tracks your average and
per-category scores. Practice is for rehearsal; VEENA is not meant for covert
use in assessments that prohibit AI.

## 7. Meeting Copilot

Confirm you are authorised to transcribe, start a meeting session, and press
**Listen** (and on Windows optionally capture the meeting app's audio).
**Generate notes** produces a summary, key points, decisions, action items
(owner, task, due date where stated) and open questions. Only the transcript
text is kept.

## 8. Analytics and diagnostics

*Analytics* shows only measured values: latency of each pipeline stage,
response time per day, per-model speed, question categories, retrieval scores,
practice scores. *Settings → Developer diagnostics* shows CPU, RAM, GPU usage,
live metrics, and the backend log, and can restart the backend.

## 9. Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Ctrl/⌘ + Shift + Space | Bring VEENA to the front |
| Ctrl/⌘ + Shift + M | Start or stop the microphone |
| Ctrl/⌘ + Shift + S | Analyse the shared screen |
| Enter / Shift + Enter | Send / new line |

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| "Ollama offline" | Start Ollama, then Settings → Local models → Refresh. |
| "No local model is installed" | Run Setup again or `ollama pull qwen2.5:3b`. |
| Microphone does nothing | Check the OS microphone permission for VEENA and the device in Settings → Speech. |
| Speech lags behind | Choose a smaller speech model (tiny/base). |
| Screen list is empty (macOS) | Grant Screen Recording permission and restart VEENA. |
| Screen answers ignore the image | No vision model installed: VEENA uses OCR text only and says so. Download qwen2.5vl:3b. |
| Backend did not start | Press *Show log* on the error screen. |
