# Parakeet AI Costs $149.90 a Month. I Built a $0 Replacement — Then Did the Math on a $1 Million Monthly Bill

### The full story of VEENA.AI: a local-first desktop AI copilot that listens, reads the screen you choose, answers from your own documents, and never sends a byte to anyone's server. Every price is sourced, every speed is measured, and all of the code is on GitHub.

**GitHub repository:** [github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)

![The VEENA.AI ginger Persian cat logo](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/apps/desktop/build/background.png)

---

## TL;DR

- Paid AI conversation copilots charge by the hour or the month. Parakeet AI's
  list prices are **$38 per hour** or **$149.90 per month** for unlimited use.¹
- Every piece of what they do (speech recognition, screen reading, language
  models, document search) now has a **free, open model that runs on a laptop**.
- I put those pieces together in **VEENA.AI**, a desktop app for Windows, macOS
  and Linux. **Monthly cost: $0.** No account, no API key, no subscription.
- For one person that saves **$1,798.80 a year**. At company scale the same
  maths gets dramatic: at list price, **about 6,700 seats cost roughly
  $1 million a month**, and a local app's licence cost for those seats is $0.
- It isn't magic. On a CPU-only machine, text answers start in **0.19 s**, but
  analysing a screenshot takes **about a minute**. The trade-offs are in Part 7.
- The code, tests, installers, benchmarks and this article's screenshots are all
  in the [GitHub repository](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai).

---

## Part 1 — The bill that started this

AI "conversation copilots" became one of the fastest-growing software categories
of the last two years. The pitch is simple: share your screen or let the app hear
a call, and it transcribes, spots the question, and drafts an answer in real time.
Parakeet AI is one of the best-known names in the space.

Then I looked at the price list.

According to pricing roundups published in September and October 2026:¹

| Parakeet AI plan | Price | What it buys |
|---|---|---|
| 1 credit | $38.00 | 1 hour of live calls or mock interviews |
| 3 credits | $59.00 | 3 hours |
| 6 + 2 free credits | $118.00 | 8 hours |
| 9 + 6 free credits | $177.00 | 15 hours |
| Unlimited, weekly | $78.00 / week | Unlimited use |
| **Unlimited, monthly** | **$149.90 / month** | Unlimited use |
| Unlimited, yearly | $599.90 / year ($49.99 / month) | Unlimited use |
| Free tier | $0 | 10 sessions of up to 10 minutes |

Those are fair prices for a polished, supported product. But one question kept
bothering me:

> **Which part of this actually needs to cost money?**

- **Speech recognition?** OpenAI's Whisper is open, and faster-whisper runs it on a CPU.
- **Knowing when someone is talking?** Silero VAD is free and tiny.
- **Answering questions?** Qwen2.5 models run locally through Ollama.
- **Reading a screenshot?** Tesseract OCR is free, and Qwen2.5-VL is a free vision model.
- **Searching my own notes?** sentence-transformers and FAISS are free.

Every ingredient was free. What you pay a vendor for is assembling the pieces
and running them on someone else's GPU. So I assembled them myself. The result is
**VEENA.AI**: *"Your intelligent conversation companion."* Its mascot is a ginger
Persian cat, and it runs entirely on my own computer.

---

## Part 2 — The money, in detail

### 2.1 What one person pays

| | Parakeet AI (list prices¹) | VEENA.AI |
|---|---|---|
| Monthly subscription | $149.90 / month | **$0** |
| Pay-as-you-go | $38.00 / hour | **$0** |
| Per year | $1,798.80 (monthly plan) or $599.90 (annual plan) | **$0** |
| Account, credit card, API key | Required | **None** |
| Where your audio and screen go | The vendor's service | **Nowhere. They stay on your computer** |
| Works offline after setup | No | **Yes** |

**Heavy use is where metering hurts.** At 20 hours a month of practice, calls and
meetings, pay-as-you-go is **20 × $38 = $760 a month**. Unlimited caps it at
$149.90. The local app's monthly bill doesn't change with usage: it's zero at
1 hour and zero at 200 hours.

**My personal savings: $149.90 a month, or $1,798.80 a year** against the monthly
Unlimited plan. Against the annual plan, it's $599.90 a year.

### 2.2 What "free" actually cost me

Articles that say "free" and stop there aren't telling the whole truth. Here is
everything I actually spent:

| Cost | Type | Amount |
|---|---|---|
| Building it | One-time | I used a paid **Claude Code** subscription as my engineering assistant. The finished app does **not** need Claude or any paid service to run. |
| Ollama models | One-time download | **4.2 GB** for my setup: qwen2.5:1.5b (1 GB) + qwen2.5vl:3b (3.2 GB). The Performance profile is about 11 GB. |
| Speech + embedding models | One-time download | About **165 MB**: Whisper base (~150 MB) and MiniLM (~90 MB, shared cache). |
| Disk | Ongoing, no money | The models, plus about **1.5 GB** for the installed app (it bundles CPU PyTorch for embeddings). |
| Electricity | Ongoing | Small, but not zero. Worked example below. |
| Hardware | Already owned | Runs on CPU only. A GPU or Apple Silicon makes it faster. |

**Electricity, worked example.** This is an estimate with stated assumptions, not
a measurement. Suppose a laptop draws an extra **65 W** while the models run, you
use VEENA **1 hour a day**, and power costs **$0.17 per kWh**:

> 0.065 kW × 30 hours × $0.17 ≈ **$0.33 per month**, or about **$4 per year**.

Plug in your own wattage and tariff. Even if you triple every assumption, it
stays around a dollar a month.

### 2.3 Where a $1 million monthly bill comes from

At one seat, $149.90 a month is a nice dinner out. But copilots are increasingly
bought by organisations (bootcamps, university career centres, recruiting teams,
sales orgs), and per-seat pricing scales linearly.

Here is Parakeet's Unlimited list price multiplied out. This is a **hypothetical
scenario using public list prices**; enterprise contracts are often discounted.

| Seats | Monthly at $149.90 / seat | Yearly | VEENA.AI licence cost |
|---|---|---|---|
| 1 | $149.90 | $1,798.80 | $0 |
| 50 (a bootcamp cohort) | $7,495 | $89,940 | $0 |
| 500 (a university career centre) | $74,950 | $899,400 | $0 |
| 1,000 (a sales organisation) | $149,900 | $1,798,800 | $0 |
| **6,671** | **$999,983 ≈ $1 million / month** | **≈ $12 million / year** | **$0** |

**At about 6,700 seats, list-price subscriptions cost roughly $1 million a month.**
A local app on hardware the organisation already owns costs nothing in licences.
Its real costs are IT time to roll it out, disk space on each machine, and the
fact that slow laptops give slow answers (Part 5).

To be completely clear: **I'm one person, and I did not personally replace a
$1 million bill.** I replaced $149.90 a month. The table shows something more
interesting: the local architecture deletes the per-seat line item entirely,
whatever the scale.

---

## Part 3 — What I built: a tour

VEENA.AI is a desktop app (Windows first, then macOS and Linux) with six
workspaces. Every screenshot below was captured from the real app running real
local models, by a script that's in the repository
([`apps/desktop/scripts/screenshots.mjs`](https://github.com/florina787/Data-sets/blob/claude/amazing-babbage-qia83y/veena-ai/apps/desktop/scripts/screenshots.mjs)).

![The welcome screen](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/welcome.png)

### 3.1 Setup that respects your hardware

On first launch, a wizard explains what runs locally and what it costs you in
downloads, disk and electricity. It then detects your OS, CPU, RAM, GPU and free
disk space and recommends a profile:

| Profile | For | Text model | Vision model | Speech model |
|---|---|---|---|---|
| Lite | 8 GB RAM, CPU | qwen2.5:1.5b | qwen2.5vl:3b (on demand) | whisper tiny |
| Balanced | 16 GB RAM | qwen2.5:3b | qwen2.5vl:3b | whisper base |
| Performance | 32 GB RAM or 8 GB+ GPU | qwen2.5:7b | qwen2.5vl:7b | whisper small |

It downloads the models through Ollama with a progress bar, then **benchmarks
your actual machine** (tokens per second, time to first token, and the speech
model's real-time factor) instead of guessing from RAM size.

![The setup wizard detecting hardware](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/setup.png)

### 3.2 Conversation: it listens, and knows when you asked something

Type, or press **Listen** and talk. VEENA transcribes your speech live, on your
machine. When it hears a question it classifies it (coding, architecture,
behavioural, follow-up, clarification, command) and, if auto-answer is on,
answers it. Answers stream word by word with syntax-highlighted code, tables and
Mermaid diagrams. A **Stop** button halts generation mid-sentence and keeps what
was written.

You choose the answer style per question: Quick Answer, Detailed Answer,
Technical Deep Dive, Code Explanation, Architecture Explanation, Step-by-Step
Tutorial, or Practice Interview Answer. Every answer shows which model wrote it,
how long the first word took, and the generation speed.

![A conversation answered by a local model](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/conversation.png)

### 3.3 Screen Intelligence: it reads the screen you choose, and only that

Pick an entire screen or a single window in VEENA's own picker. While sharing,
a dark "Sharing …" pill with a **Stop** button stays visible in the header on
every page. Then press *Explain Code*, *Find Errors*, *Explain Architecture* or
*Summarize Screen*, ask anything ("why is this failing?"), or drag a rectangle to
analyse only part of the screen.

![Choosing exactly what to share](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/screen-picker.png)

Before any pixel reaches a model:

1. **Tesseract OCR** reads the frame (0.67 s for a 1280×720 screenshot).
2. VEENA **paints over anything that looks like a secret** (passwords, API keys,
   AWS keys, GitHub and Slack tokens, JWTs, card numbers, and values after labels
   like "Password:") in both the pixels and the OCR text.
3. The local vision model, **Qwen2.5-VL 3B**, sees the redacted image plus the OCR text.

Frames are never saved to disk. An optional **continuous mode** samples the
screen every few seconds, computes a perceptual hash, and only analyses frames
that actually changed. It pauses when VEENA is minimised or a password field
appears on screen.

![Screen analysis by a local vision model](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/screen.png)

*Honest caption: that's a real answer from a 3B vision model running on a CPU.
Small vision models give short, sometimes shallow answers. A bigger model on a
GPU does better.*

There's one guarantee I cared about more than any feature: **VEENA cannot capture
your screen unless you picked a source in its own picker.** The selection is
single-use, and an automated test calls the screen-capture API with no selection
and checks that it's refused.

### 3.4 Knowledge: answers from your own documents, with receipts

Create collections (Resume, Job descriptions, Projects, Technical documentation,
Meeting notes, General) and drop in PDF, Word, TXT, Markdown, CSV or JSON files.
VEENA extracts the text, splits it into paragraph-sized passages, embeds them
with **all-MiniLM-L6-v2**, and stores the vectors in a **FAISS** index on your disk.

![Knowledge collections and retrieval testing](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/knowledge.png)

Tick a collection and your answers cite numbered passages. Click a citation to
see the exact text it came from. Retrieval ranks passages by **75% semantic
similarity + 25% keyword overlap**, and drops anything below a relevance floor I
calibrated from measured scores. If nothing relevant is found, VEENA says so
instead of guessing.

![A cited answer from my own documents](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/citations.png)

A **governance check** reviews every finished answer. It flags citations to
passages that don't exist, retrieved evidence that the answer ignored, and (in
practice interviews) claims of personal experience or figures that your résumé
doesn't support.

### 3.5 Meeting Copilot

Confirm you're authorised to transcribe, start a meeting session, and press
Listen (on Windows you can also capture the meeting app's audio). **Generate
notes** produces a summary, key points, decisions, action items with owners and
due dates where stated, and open questions. Only the text transcript is kept;
audio is never stored.

![Meeting notes written by a local model](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/meeting.png)

### 3.6 Interview Practice

Choose one of eight roles (Senior AI Engineer, Principal AI Engineer, AI
Architect, Forward Deployed AI Engineer, Data Scientist, Machine Learning
Engineer, Software Engineer, Solutions Architect) and a focus (behavioural,
coding, architecture, leadership, or mixed). Optionally attach your résumé and a
job description. VEENA generates questions, can read them aloud with your OS's
own local voice, and scores typed or spoken answers 0–10 with strengths,
improvements, an outline of a strong answer, and a follow-up question.

![Interview practice feedback from a 1.5B local model](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/interview.png)

*Honest caption: real feedback from a 1.5-billion-parameter model. It's useful,
but small models can contradict themselves; here it lists a "clear example" as a
strength while saying the answer missed the question.*

One deliberate difference from some commercial tools: **VEENA is built for
practice, not for covert help in real interviews or assessments that ban AI.**
Recording is always visible and always started by you.

### 3.7 Analytics, from real measurements only

The Analytics page shows pipeline latency per stage, response time per day,
per-model speed, question categories, retrieval scores and practice scores.
Nothing on it is estimated: every number comes from an actual request on your
machine. If nothing has been measured yet, the chart says so instead of showing
placeholder data.

![Analytics inside the app](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/analytics.png)

### 3.8 Settings and privacy controls

Choose the text, vision and speech models; pick a microphone; set how long
history is kept (1 day to 1 year, or until you delete it); toggle screen
redaction; and clear all history in one click. A developer diagnostics panel
shows live CPU, RAM and GPU usage and the backend log.

![Settings](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/settings.png)

---

## Part 4 — The $0 stack, and how it fits together

### 4.1 Every component

| Job | What paid services typically use | What VEENA uses | Licence cost |
|---|---|---|---|
| Speech to text | Cloud speech API | faster-whisper (Whisper, int8 on CPU) | $0 |
| Detecting speech | — | Silero VAD v6 (ONNX) | $0 |
| Language model | Hosted LLM API | Ollama + Qwen2.5 (1.5B / 3B / 7B) | $0 |
| Screen understanding | Hosted vision API | Qwen2.5-VL via Ollama + Tesseract OCR | $0 |
| Document search | Hosted vector database | sentence-transformers (MiniLM) + FAISS | $0 |
| Storage | Cloud database | SQLite on your disk | $0 |
| Orchestration | — | LangGraph | $0 |
| Backend | — | Python, FastAPI, WebSockets | $0 |
| Desktop app | — | Electron, React, TypeScript, Tailwind, Zustand, Recharts | $0 |
| Installers | — | PyInstaller + electron-builder | $0 |

### 4.2 How a question flows through it

```
Your voice ──► Silero VAD ──► faster-whisper ──► question detector
                                                       │
Your screen ─► OCR + secret redaction ─────────────────┤
                                                       ▼
Your documents ─► MiniLM + FAISS ──► LangGraph router ──► Qwen2.5 via Ollama
                                                       │
                                                       ▼
                         streamed answer + citations + governance check
                                                       │
                                                       ▼
                                            SQLite on your own disk
```

### 4.3 The pieces, one level deeper

**Two local processes.** The Electron app starts a small Python service
(FastAPI) on `127.0.0.1`, with a random free port and a random 256-bit token
generated for each launch. Every request must present that token, and the
service checks the request's origin. Other programs on your machine, and web
pages in your browser, can't use it even if they guess the port. If the service
crashes, Electron restarts it up to three times.

**The audio pipeline.** The renderer captures your microphone with an
AudioWorklet at 16 kHz and streams 64 ms frames over a WebSocket. The backend
puts frames in a **bounded queue** (if speech recognition falls behind, the
oldest frames are dropped and counted, so memory never grows without limit),
runs Silero VAD on every 32 ms window, and cuts speech into utterances: 300 ms of
pre-roll before speech starts, and 700 ms of silence ends it. Partial transcripts
are produced only when the recogniser is idle; final transcripts are never
dropped. If your microphone is unplugged, capture falls back to the default
device; if the socket drops, it reconnects with backoff.

**Question detection.** A deterministic classifier scores each final sentence
(question marks, wh-words, auxiliary verbs, imperative verbs, keyword families
for coding, architecture and behavioural questions). That takes **0.014 ms**.
Only genuinely ambiguous sentences are escalated to the local model. Repeated
questions within 90 seconds are suppressed, so you don't get the same answer twice.

**Orchestration with LangGraph.** A supervisor routes each request
deterministically: meetings to the meeting agent, practice to the coaching agent,
screenshots to the screen agent (or the code or architecture agent, depending on
the question), document questions to the knowledge agent, and everything else to
the conversation agent. **A plain text question never touches the vision model or
retrieval**, so it costs exactly one model call.

**Vision is detected, not assumed.** VEENA asks Ollama which installed models
actually report the `vision` capability. If none does, screen questions fall
back to the OCR text, and the answer says so.

**Prompt-injection defences.** Screen text, documents and transcripts are
treated as untrusted. They're wrapped in clearly marked data blocks that can't
close themselves, the system prompt says data is never instructions, and known
injection phrasing ("ignore all previous instructions…") is detected and
reported to you.

**Desktop security.** The renderer runs sandboxed, with no Node.js access and a
strict Content Security Policy. It can talk only to `127.0.0.1`, and it reaches
the main process through 11 narrow, validated methods. The camera is never
granted. Navigation away from the app is blocked.

### 4.4 Design and the logo

The whole interface uses ten colours: white, warm white, ivory, cream and six
browns (from light brown to espresso). Tailwind's default palette is deleted,
and **a test fails if any other colour appears in the UI source.** Status is shown
with shapes and text, never red/amber/green.

![The VEENA.AI app icon](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/apps/desktop/assets/icon-256.png)

The ginger Persian cat is original artwork: a round, fluffy face with cream
cheeks, amber-brown eyes and soft rounded ears. It's drawn from **one SVG source
file**, which generates the app icon, favicon, Windows installer sidebar, macOS
installer background and the in-app mascot, so the cat looks identical
everywhere. Inside the app it blinks, leans in while listening, and "thinks"
while an answer is being generated, and it stops moving if you've asked your OS
for reduced motion.

---

## Part 5 — Free is not the same as fast: real benchmarks

Here's what "$0" gets you on a modest machine. These numbers were measured on a
**4-vCPU cloud VM with no GPU and 15.7 GB of RAM**, which is roughly a budget
laptop. Nothing below is estimated.

![Where the time goes](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/chart-latency.png)

| What | Measured |
|---|---|
| Question detection (rules) | **0.014 ms** per sentence |
| Voice activity detection | **7 ms** per second of audio |
| Embedding one question | **12 ms** |
| Searching 100,000 document passages | **10 ms** |
| First word of a text answer (model already loaded) | **187 ms** |
| Text generation speed (Qwen2.5 1.5B) | **21 tokens/s** (a token is roughly three-quarters of a word) |
| OCR of a 1280×720 screenshot | **0.67 s** |
| Transcribing a 4.3-second question (whisper base) | **1.6 s** (2.6× faster than speech) |
| Analysing a full screenshot with the vision model | **48–81 s** (three end-to-end runs) |
| First answer right after starting Ollama (cold load) | **80 s** |
| Backend memory with speech + embedding models loaded | **968 MB** (Ollama's models are separate) |

![Local speech recognition](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/chart-speech.png)

**What the numbers mean:**

- **Text and speech feel live on CPU alone.** The first word arrives in under a
  fifth of a second, and speech is transcribed faster than it's spoken (Whisper
  tiny at 0.22× real time, base at 0.38×).
- **Screen analysis on CPU is slow, at about a minute per screenshot.** This is
  the biggest thing money buys you in a cloud product: someone else's GPU. On a
  machine with a GPU or Apple Silicon it should be much faster, but I didn't
  measure that, so I won't quote a number. Cropping to a region, or using the
  OCR-only path for text-heavy screens, helps a lot.
- **Live partial transcripts don't get cheaper for short clips.** Whisper
  processes audio in 30-second windows, so a 1.5-second partial costs about the
  same as a whole sentence. On 4 cores, partials arrive every 2–3 seconds.
- **The very first answer is slow.** Loading a model from disk took 80 s right
  after Ollama restarted. VEENA keeps models loaded for 30 minutes afterwards.

**If your time is worth more than $149.90 a month and you don't have a decent
GPU, a paid service may genuinely be the better deal for screen analysis.** For
everything else, the free stack holds up.

You can reproduce every number with the benchmark script in the repo
([`tests/performance/run_benchmarks.py`](https://github.com/florina787/Data-sets/blob/claude/amazing-babbage-qia83y/veena-ai/tests/performance/run_benchmarks.py)).
The raw results are in
[`docs/benchmarks/latest.json`](https://github.com/florina787/Data-sets/blob/claude/amazing-babbage-qia83y/veena-ai/docs/benchmarks/latest.json).

---

## Part 6 — How I tested it, and what testing caught

I wanted a product, not a demo. So the tests run against **real models**, and
anything simulated is labelled as simulated.

| Suite | Tests | What it exercises |
|---|---|---|
| Backend, deterministic | 110 | Security, question detection, document extraction, chunking, retrieval, streaming speech pipeline, screen redaction with real Tesseract, the API end to end with clearly labelled stand-in models. Runs in CI on every push. |
| Backend, real models | 6 | Real Ollama answers, real vision on a real screenshot, real Whisper on synthesised speech, the full WebSocket → VAD → Whisper → question pipeline, real embeddings. |
| Frontend | 15 | Components, streaming, audio framing, frame hashing, and the palette guard. |
| End to end | 9 | The real desktop app with the real backend and real models (see below). |

The nine end-to-end tests start the actual Electron app and check that:

1. the renderer is isolated from Node.js;
2. the backend refuses requests without its token;
3. setup detects the hardware and runs a real benchmark;
4. a typed question gets a real streamed answer;
5. an uploaded document is indexed and the answer cites it;
6. screen capture is refused without a user selection;
7. a user-selected screen is shared, analysed by the vision model, and stopped;
8. speech is transcribed, detected as a question, and answered (synthesised
   speech is played through Chromium's fake microphone into the real Whisper pipeline);
9. a session can be deleted.

**Those end-to-end tests caught bugs that unit tests never would have:**

1. **Screen sharing was blocked by my own security rules.** My permission handler
   denied a permission type I didn't know existed. Every unit test passed; the
   real app couldn't share a screen.
2. **The microphone was silently refused.** The desktop app identifies itself to
   the audio socket differently from regular web requests, so my backend's
   allowlist rejected it. A regression test now covers both cases.
3. **Linux sometimes listed no screens at all.** Window enumeration timed out
   and took the screen list down with it. Listing screens and windows separately
   fixed it.
4. **"Offline" wasn't offline.** The speech and embedding libraries contacted the
   internet on every start. They now load from the local copy first, so a
   configured app makes no network requests.
5. **Retrieval missed obvious matches.** Packing a short résumé into one chunk
   diluted the similarity score from 0.27 to 0.17. I measured real scores and
   recalibrated chunking and thresholds from that data, not from guesses.
6. **A test flag nearly hid a security question.** A Chromium testing flag
   auto-approved screen capture. I confirmed that without it the app refuses
   capture the user didn't select, and removed the flag.
7. **Feedback came out as single letters.** While capturing screenshots for this
   article, the interview coach printed "a strong answer would cover" as "C",
   "a", "n"… The small model returned one string where I expected a list, and my
   code iterated it character by character. Fixed, with a regression test.

**Then CI took over.** A GitHub Actions workflow runs the backend and frontend
suites. It then builds installers on real **Windows, macOS and Linux** runners
and launches each packaged app to confirm that it starts its bundled backend,
renders the setup screen, and rejects requests without its token. On Windows,
the packaged app's backend was ready in 2.4 seconds.

---

## Part 7 — What $0 doesn't buy you

I'd rather you hear the trade-offs from me:

- **Speed on weak hardware.** Screen analysis on CPU takes about a minute.
- **Polish and support.** A paid product has a team, signed installers and a help
  desk. My builds are unsigned, so Windows SmartScreen and macOS Gatekeeper warn
  on first launch.
- **Testing breadth.** Real-model answers were tested end to end on Linux. On
  Windows and macOS, CI confirmed the packaged app starts, but no model answers
  were tested there, and the Windows installer was built but not run.
- **Model quality.** A 1.5–7B local model is not a frontier model. VEENA shows
  the model, sources and warnings on every answer so you can judge.
- **App size.** About 1.5 GB installed, mostly CPU PyTorch.
- **Missing features.** System-audio capture works on Windows only. Scanned PDFs
  without a text layer aren't OCR'd yet. I haven't built Piper voice output or
  Parakeet ASR, and there is deliberately no code-execution feature.
- **Redaction is best effort.** It can only hide secrets that OCR can read.

---

## Part 8 — Try it yourself

**GitHub:** [github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)

**To use it:**

1. Install **Ollama** (free) from [ollama.com/download](https://ollama.com/download) and start it.
2. Download the installer for your OS from the repository's CI build artifacts:
   `VEENA.AI-Setup-0.1.0.exe` (Windows), a `.dmg` (macOS) or an `.AppImage` (Linux).
3. Launch VEENA. The setup wizard checks your hardware, downloads the models and
   benchmarks your machine.
4. Optional: install Tesseract OCR for better screen text.

**To run it from source:**

```bash
git clone https://github.com/florina787/Data-sets
cd Data-sets
git checkout claude/amazing-babbage-qia83y
cd veena-ai
./scripts/setup.sh                 # Windows: .\scripts\setup.ps1
ollama pull qwen2.5:3b && ollama pull qwen2.5vl:3b
cd apps/desktop && npm run dev
```

**Useful docs in the repo:**

- [README](https://github.com/florina787/Data-sets/blob/claude/amazing-babbage-qia83y/veena-ai/README.md): overview, status table, screenshots
- [User guide](https://github.com/florina787/Data-sets/blob/claude/amazing-babbage-qia83y/veena-ai/docs/USER_GUIDE.md): every feature, shortcuts, troubleshooting
- [Architecture](https://github.com/florina787/Data-sets/blob/claude/amazing-babbage-qia83y/veena-ai/docs/ARCHITECTURE.md): processes, request flow, audio pipeline, data model
- [Security and privacy](https://github.com/florina787/Data-sets/blob/claude/amazing-babbage-qia83y/veena-ai/docs/SECURITY.md): what's stored, what isn't, and how the app is hardened
- [Benchmarks](https://github.com/florina787/Data-sets/blob/claude/amazing-babbage-qia83y/veena-ai/docs/BENCHMARKS.md): full measurements and caveats

---

## The bottom line

| | Paid copilot (Parakeet AI list price) | VEENA.AI |
|---|---|---|
| One person, one month | $149.90 | $0 + about $0.33 of electricity |
| One person, one year | $1,798.80 | $0 + about $4 of electricity |
| 6,700 seats, one month | ≈ $1,000,000 | $0 in licences |
| Account or API key | Required | None |
| Where your data goes | The vendor | Your disk |
| What you give up | Money | Speed on weak hardware, and polish |

The biggest line on an AI copilot invoice isn't the AI. It's the convenience of
someone else running it. For a growing set of tasks, your own laptop can do that
part for free.

*VEENA.AI is open source under GPL-3.0. It's built with free, open tools:
Qwen2.5, Qwen2.5-VL, Whisper (faster-whisper), Silero VAD, MiniLM
(sentence-transformers), FAISS, Tesseract, Ollama, LangGraph, FastAPI, Electron
and React.*

**Code, tests, installers and benchmarks:**
[github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)

---

**¹ Pricing sources** (third-party roundups; check parakeet-ai.com for the current official price):
[Copilot Interview — Parakeet AI Pricing 2026](https://copilotinterview.com/blog/parakeet-ai-pricing) ·
[Interview Sidekick — Parakeet AI Pricing 2026](https://interviewsidekick.com/blog/parakeet-ai-pricing) ·
[Final Round AI — Parakeet AI Review 2026](https://www.finalroundai.com/blog/parakeet-ai-review) ·
[Mock Interview Pro — Parakeet AI review](https://www.mockinterviewpro.com/reviews/parakeet-ai).
Some older 2026 sources list lower prices (for example $74.90 per month), so figures vary by date.

*Performance numbers were measured on a 4-vCPU, 15.7 GB, no-GPU Linux VM on
2026-10-24. Electricity cost is a worked estimate with the stated assumptions,
not a measurement.*
