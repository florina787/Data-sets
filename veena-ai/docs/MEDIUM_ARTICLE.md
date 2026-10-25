# Parakeet AI Costs $149.90 a Month. I Built a $0 Replacement — Then Did the Math on a $1 Million Monthly Bill

### How I replaced a paid AI conversation copilot with VEENA.AI, a local-first desktop app built on free, open models. Every dollar figure is sourced and every speed figure is measured.

![VEENA.AI welcome screen](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/welcome.png)

---

## The bill that started this

AI "conversation copilots" are one of the fastest-growing software categories of
the last two years. You share your screen or let them listen to a call, and they
transcribe, spot the question, and draft an answer in real time. Parakeet AI is
one of the best known.

Then I looked at what it costs.

According to published pricing roundups from September and October 2026,
Parakeet AI sells **credits at $38.00 each**, where one credit buys one hour of
live calls or mock interviews. Bigger packs bring the per-hour price down ($59 for
3 credits, $118 for 6 + 2 free, $177 for 9 + 6 free). If you want it without a
meter running, the **Unlimited plan is $149.90 per month**, $78.00 per week, or
$599.90 per year billed annually. There is a free tier of 10 sessions capped at
10 minutes each.¹

Those are reasonable prices for a polished product. But I kept asking one
question:

> **Which part of this actually needs to cost money?**

Speech recognition? Free, open models run on a laptop. Reading a screenshot? Free
OCR exists, and so do free vision models. Answering questions? Free language
models run locally. Searching my own notes? Free embeddings and a free vector index.

So I built it. It's called **VEENA.AI** (the mascot is a ginger Persian cat), and
it runs entirely on my own computer. **It costs $0 a month.**

This article is about the money: what I was going to pay, what I paid instead
(spoiler: not quite zero), and what the same math looks like when a company
writes the cheque instead of one person. That last part is where a
**$1 million-per-month bill** comes from, and I'll show exactly how.

---

## Part 1 — The money, honestly

### What one person pays

| | Parakeet AI (list prices¹) | VEENA.AI |
|---|---|---|
| Monthly subscription | $149.90 / month (Unlimited) | **$0** |
| Pay-as-you-go | $38.00 per hour (1 credit) | **$0** |
| Per year | $1,798.80 (monthly) or $599.90 (annual plan) | **$0** |
| API keys | Not applicable (it's a service) | **None. No account, no card** |
| Where your audio and screen go | The vendor's service | **Nowhere. Stays on your computer** |

If you use a copilot a lot, say 20 hours a month of practice, calls and
meetings, the pay-as-you-go price is **20 × $38 = $760 a month**. The
Unlimited plan caps that at $149.90. Either way, the local version's monthly bill
is the same: zero.

**Personal savings: $149.90 a month, or $1,798.80 a year,** against the monthly
Unlimited plan. Against the annual plan it's $599.90 a year.

### What "free" actually cost me

I don't trust articles that say "free" and stop there. Here is everything I
actually spent:

| Cost | One-time or ongoing | Amount |
|---|---|---|
| Building it | One-time | I used a paid **Claude Code** subscription as my engineering assistant. The finished app does **not** need Claude or any paid service to run. |
| Model downloads | One-time | About **4.2 GB** for my setup (1 GB text model + 3.2 GB vision model), plus about 165 MB for speech and embedding models. Up to about 11 GB for the largest profile. |
| Disk space | Ongoing (no money) | The models above, plus about **1.5 GB** for the installed app (it bundles CPU PyTorch). |
| Electricity | Ongoing | Small, but not zero. Worked example below. |
| Hardware | Already owned | Runs on CPU only. A GPU or Apple Silicon makes it faster. |

**Electricity, worked example.** This is an estimate with stated assumptions, not
a measurement: suppose a laptop draws an extra **65 W** while the models
run, you use it **1 hour a day**, and power costs **$0.17 per kWh**.
That's 0.065 kW × 30 h × $0.17 ≈ **$0.33 a month**. Plug in your own wattage
and tariff; even if you triple every assumption, it stays around a dollar a month.

### Where a $1 million monthly bill comes from

At one seat, $149.90 is a nice dinner out. Copilots are increasingly bought by
**bootcamps, universities, recruiting teams and sales orgs**, though, and per-seat
pricing scales linearly.

Here is Parakeet's Unlimited list price multiplied out. This is a **hypothetical
scenario using public list prices**; enterprise contracts are often discounted.

| Seats | Monthly at $149.90 / seat | Yearly | VEENA.AI licence cost |
|---|---|---|---|
| 1 | $149.90 | $1,798.80 | $0 |
| 50 (a bootcamp cohort) | $7,495 | $89,940 | $0 |
| 500 (a university career centre) | $74,950 | $899,400 | $0 |
| 1,000 (a sales org) | $149,900 | $1,798,800 | $0 |
| **6,671** | **$999,983 ≈ $1 million / month** | **≈ $12 million / year** | **$0** |

**At about 6,700 seats, list-price subscriptions cost roughly $1 million a month.**
A locally running app on hardware the organisation already owns costs
nothing in licences. Its real costs are IT time to roll it out, disk space,
and the fact that slow laptops give slow answers (see Part 4).

To be clear: I'm one person, and I did not personally replace a $1 million bill.
What I replaced is $149.90 a month. The point of the table is that **the same
architecture removes the per-seat line item entirely, at any scale.**

---

## Part 2 — What I built

VEENA.AI is a desktop app (Windows first, then macOS and Linux) that does what I
wanted from a paid copilot, without the bill.

### It listens, and knows when you asked something

Press **Listen** and VEENA transcribes your speech live, on your machine. When it
hears a question, it classifies it (coding, architecture, behavioural, follow-up,
clarification…) and answers, citing your documents if you've given it any.

![A conversation answered by a local model](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/conversation.png)

Under the hood:
- **Silero VAD** decides when someone is speaking (7 ms of compute per second of audio).
- **faster-whisper** transcribes it (int8 on CPU).
- A rules-based **question detector** classifies each sentence in 0.014 ms, and
  asks the local model only when a sentence is genuinely ambiguous.
- **Ollama** runs **Qwen2.5** to write the answer, streamed word by word, and you can stop it mid-sentence.

### It reads the screen you choose, and only that screen

Pick a screen or a single window. VEENA shows a permanent "Sharing" indicator
with a Stop button. Ask "why is this failing?" or press *Explain Code*, *Find
Errors*, *Explain Architecture* or *Summarize Screen*.

![Choosing exactly what to share](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/screen-picker.png)

Before any pixel reaches a model, **Tesseract OCR** reads the frame and VEENA
paints over anything that looks like a password, API key, token or card number.
Then a local vision model, **Qwen2.5-VL 3B**, looks at the image. Frames are never
saved to disk.

There's one guarantee I cared about more than any feature: **VEENA cannot capture
your screen unless you picked a source in its own picker.** An automated test
calls the screen-capture API with no selection and checks that it's refused.

### It answers from your own documents, with receipts

Drop in PDFs, Word files, Markdown, CSV or JSON. VEENA chunks them, embeds them
with **sentence-transformers** (MiniLM), stores the vectors in **FAISS**, and answers
with numbered citations you can click to see the exact passage.

![A cited answer from my own documents](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/citations.png)

If nothing relevant is found, it says so instead of making something up. A
built-in "governance" check flags answers that cite sources that don't exist, or
that claim personal experience your résumé doesn't support.

![Testing retrieval directly](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/knowledge.png)

### It coaches interview practice, and writes meeting notes

**Interview Practice** generates questions for eight roles (from Software Engineer
to AI Architect), scores your typed or spoken answers 0–10, and tells you what to
improve. **Meeting Copilot** turns an authorised meeting transcript into a summary,
decisions, and action items with owners.

![Meeting notes written by a local model](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/meeting.png)

![Interview practice feedback from a 1.5B local model (small models can be inconsistent)](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/interview.png)

One deliberate difference from some commercial tools: **VEENA is built for
practice, not for covert help in real interviews or assessments that ban AI.**
Recording is always visible and always started by you.

### It sets itself up for your hardware

The first-run wizard detects your CPU, RAM, GPU and disk, recommends a profile
(Lite, Balanced or Performance), downloads the right free models, and
benchmarks your actual machine.

![The setup wizard detecting hardware](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/setup.png)

---

## Part 3 — The $0 stack

Every component is free and open, and runs locally:

| Job | What paid services typically use | What VEENA uses | Cost |
|---|---|---|---|
| Speech to text | Cloud speech API | faster-whisper + Silero VAD | $0 |
| Language model | Hosted LLM API | Ollama + Qwen2.5 (1.5B / 3B / 7B) | $0 |
| Screen understanding | Hosted vision API | Qwen2.5-VL via Ollama + Tesseract OCR | $0 |
| Document search | Hosted vector database | sentence-transformers + FAISS | $0 |
| Storage | Cloud database | SQLite on your disk | $0 |
| Orchestration | — | LangGraph | $0 |
| App shell | — | Electron + React + Tailwind | $0 |

**How a question flows through it:**

```
Your voice ─► Silero VAD ─► faster-whisper ─► question detector
                                                   │
Your screen ─► OCR + secret redaction ─────────────┤
                                                   ▼
Your documents ─► MiniLM + FAISS ─► LangGraph router ─► Qwen2.5 via Ollama
                                                   │
                                                   ▼
                     streamed answer + citations + governance check
                                                   │
                                                   ▼
                                       SQLite on your own disk
```

The Electron app starts a small Python service on `127.0.0.1` with a random
port and a random 256-bit token per launch. Other programs on your machine, and
web pages in your browser, can't talk to it.

---

## Part 4 — Free is not the same as fast: real benchmarks

Here's what "$0" gets you on a modest machine. These numbers were measured
on a **4-vCPU cloud VM with no GPU and 15.7 GB RAM**, which is roughly a budget
laptop. Nothing here is estimated.

![Where the time goes](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/chart-latency.png)

| What | Measured |
|---|---|
| First word of a text answer (model already loaded) | **187 ms** |
| Text generation speed (Qwen2.5 1.5B) | **21 tokens/s** (a token is roughly three-quarters of a word) |
| Transcribing a 4.3-second question (whisper base) | **1.6 s** (2.6× faster than speech) |
| OCR of a 1280×720 screenshot | **0.67 s** |
| Searching 100,000 document passages | **10 ms** |
| Analysing a full screenshot with the vision model | **48–81 s** (three end-to-end runs) |
| First answer right after starting Ollama (cold load) | **80 s** |

![Analytics inside the app, from real measurements](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/analytics.png)

![Local speech recognition](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/chart-speech.png)

The honest read:

- **Text and speech are fast enough** to feel live on CPU alone.
- **Screen analysis on CPU is slow, at about a minute per screenshot.** This is the
  biggest thing money buys you in a cloud product: someone else's GPU. On a
  machine with a GPU or Apple Silicon it's much faster (I didn't measure that,
  so I won't quote a number). Cropping to a region, or using the OCR-only path,
  helps a lot.
- **Live partial transcripts don't get cheaper for short clips.** Whisper
  processes audio in 30-second windows, so a 1.5-second partial costs about the
  same as a full sentence. On 4 cores, partials arrive every 2–3 seconds.

If your time is worth more than $149.90 a month and you don't have a decent GPU,
a paid service may genuinely be the better deal for screen analysis. For
everything else, the free stack holds up.

---

## Part 5 — What testing caught (that a demo never would)

I wanted a product, not a demo, so the test suite runs against **real models**.
There are 116 backend tests (110 deterministic, 6 against real Ollama, Whisper
and embedding models), 15 frontend tests, and 9 end-to-end tests that drive the
real desktop app. The microphone test even feeds synthesised speech through a
fake audio device into the real Whisper pipeline.

Those end-to-end tests caught bugs that unit tests never would have:

1. **Screen sharing was blocked by my own security rules.** My permission
   handler denied a permission type I hadn't known existed. Every unit test
   passed; the real app couldn't share a screen.
2. **The microphone was silently refused.** The desktop app identified itself to
   the audio socket differently from regular web requests, so my backend's
   allowlist rejected it.
3. **Linux sometimes listed no screens at all.** Window enumeration timed out
   and took the whole list down with it. The fix was to list screens and
   windows separately.
4. **"Offline" wasn't offline.** The speech and embedding libraries pinged the
   internet on every start. They now load from the local copy first.
5. **Retrieval missed obvious matches.** Chunking a short résumé as one block
   diluted the scores. I measured the real similarity numbers and recalibrated
   chunking and thresholds from data, not guesses.
6. **Feedback came out as single letters.** While capturing the screenshots for
   this article, the interview coach printed its "a strong answer would cover"
   list as "C", "a", "n"… The small model had returned one string where I
   expected a list, and my code iterated it character by character. A
   regression test now covers it.

Then CI built installers on real **Windows, macOS and Linux** machines and launched
each packaged app to confirm it starts its bundled backend and rejects requests
without its token.

---

## Part 6 — What $0 doesn't buy you

I'd rather you hear the trade-offs from me:

- **Speed on weak hardware.** Screen analysis on CPU takes about a minute.
- **Polish and support.** A paid product has a team, signed installers and a help desk. My builds are unsigned, so Windows and macOS warn on first launch.
- **Testing breadth.** Real-model answers were tested end to end on Linux. On Windows and macOS, CI confirmed the packaged app starts, but not model answers.
- **Model quality.** A 1.5–7B local model is not a frontier model. VEENA shows the model, sources and warnings on every answer so you can judge.
- **App size.** About 1.5 GB installed.
- **Some features.** System-audio capture is Windows-only, and I haven't built voice output (Piper) or Parakeet ASR yet.

---

## Part 7 — Try it

1. Install **Ollama** (free): ollama.com/download
2. Get VEENA.AI from the GitHub repository (link below): installers for Windows,
   macOS and Linux are built by CI, or run it from source in three commands.
3. The setup wizard does the rest.

```bash
git clone https://github.com/florina787/Data-sets
cd Data-sets/veena-ai && ./scripts/setup.sh
cd apps/desktop && npm run dev
```

---

## The bottom line

| | Paid copilot | VEENA.AI |
|---|---|---|
| One person, one year | $1,798.80 (monthly plan, list price) | $0 + about $4 of electricity |
| 6,700 seats, one month | ≈ $1,000,000 at list price | $0 in licences |
| Where your data goes | The vendor | Your disk |
| What you give up | Money | Some speed on weak hardware, and polish |

The biggest line on an AI copilot invoice isn't the AI. It's the convenience of
someone else running it. For a growing set of tasks, your own laptop can run it
instead, for free.

*VEENA.AI is open source under GPL-3.0. Built with free, open models: Qwen2.5,
Qwen2.5-VL, Whisper, Silero VAD, MiniLM, FAISS, Tesseract, Ollama, LangGraph,
Electron.*

---

**¹ Pricing sources** (third-party roundups; check parakeet-ai.com for the current official price):
[Copilot Interview — Parakeet AI Pricing 2026](https://copilotinterview.com/blog/parakeet-ai-pricing) ·
[Interview Sidekick — Parakeet AI Pricing 2026](https://interviewsidekick.com/blog/parakeet-ai-pricing) ·
[Final Round AI — Parakeet AI Review 2026](https://www.finalroundai.com/blog/parakeet-ai-review) ·
[Mock Interview Pro — Parakeet AI review](https://www.mockinterviewpro.com/reviews/parakeet-ai).
Some older 2026 sources list lower prices (for example $74.90 per month), so figures vary by date.

*Performance numbers: measured on a 4-vCPU, 15.7 GB, no-GPU Linux VM on 2026-10-24.
Raw data and the scripts to reproduce them are in the repository under `docs/benchmarks`.*
