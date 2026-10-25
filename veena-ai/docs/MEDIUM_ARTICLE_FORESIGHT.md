# Google Released an Offline AI Meeting Assistant. So I Built My Own — and It Does More

### Google AI Edge Foresight runs on Apple Silicon Macs only. VEENA.AI runs on Windows, macOS and Linux, reads your screen, coaches interviews, cites its sources, and is fully open source. Here's an honest head-to-head, including where Google still wins.

**GitHub repository:** [github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)

![VEENA.AI](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/apps/desktop/build/background.png)

---

## The news

In early October 2026, Google quietly released **Google AI Edge Foresight**, an
experimental macOS app that listens to your meetings and does everything on your
own computer.¹ It turns shorthand bullet points into full notes, detects
questions during the meeting and answers them, and searches your local files
(PDFs, Office documents, Google Docs, Markdown, web bookmarks). It's powered by
Google DeepMind's **Gemma 4** and the new **EmbeddingGemma 2**.

Its most important feature is what it *doesn't* do: it doesn't send your
audio or transcript anywhere. Google says all processing happens on the device,
with no cloud subscription required, and that it works without an internet
connection.¹

When Google ships a free, offline AI assistant, it says something loudly: **the
era of paying $150 a month for cloud AI copilots is ending.** (Parakeet AI, for
comparison, lists $149.90 a month for unlimited use.²)

There was a catch, though. Foresight is **experimental**, runs **only on Apple
Silicon Macs**, and Google hasn't said whether its source code will be released.¹

So I built my own. It's called **VEENA.AI**.

---

## What VEENA.AI is

VEENA.AI is a local-first desktop AI companion. Like Foresight, it runs entirely on
your computer, costs $0, and needs no account. It goes further in a few
directions that mattered to me.

![The VEENA.AI welcome screen](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/welcome.png)

It's built from free, open components:

| Job | What VEENA uses |
|---|---|
| Speech to text | faster-whisper (Whisper) + Silero VAD |
| Language model | Any Ollama model; tested with Qwen2.5 |
| Vision | Qwen2.5-VL via Ollama + Tesseract OCR |
| Document search | sentence-transformers (MiniLM) + FAISS |
| Orchestration | LangGraph |
| App | Electron + React (desktop), Python + FastAPI (local backend) |
| Storage | SQLite on your disk |

---

## Head to head

Here's the comparison, with Foresight's details taken from Google's announcement
and press coverage.¹ **I haven't run both apps side by side yet**, so this compares
features, not measured quality.

| | Google AI Edge Foresight | VEENA.AI |
|---|---|---|
| Runs fully on your device | ✅ | ✅ |
| Cost | Free | Free |
| Platforms | **macOS on Apple Silicon only** | **Windows, macOS, Linux** |
| Meeting transcription | ✅ mic + system audio | ✅ mic; system audio on Windows |
| Detects questions and answers them live | ✅ | ✅ |
| Searches your local documents | ✅ | ✅ |
| Shows the exact source passage for each claim | Not mentioned in coverage | ✅ clickable citations |
| Flags answers that cite sources that don't exist | Not mentioned | ✅ |
| **Understands your screen** | Not mentioned | ✅ explain code, find errors, summarise |
| Masks passwords and keys before analysis | Not applicable | ✅ |
| **Interview practice with scores** | Not mentioned | ✅ 8 roles |
| Turns shorthand bullets into full notes | ✅ | ❌ (writes notes from the transcript instead) |
| Choose your own model | Gemma 4 | Any Ollama model |
| **Source code** | Not announced | ✅ GPL-3.0 |
| Status | Experimental | v0.1, unsigned builds |

---

## Where VEENA does more

### 1. It runs on the computer you actually have

Foresight needs an Apple Silicon Mac. VEENA runs on **Windows, macOS and Linux**.
CI builds installers on all three platforms and launches each packaged app to
check it starts. On Windows, the packaged app's local backend was ready in
2.4 seconds.

![Hardware-aware setup](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/setup.png)

A setup wizard detects your CPU, RAM, GPU and disk, recommends a profile, downloads
free models, and benchmarks your actual machine.

### 2. It understands your screen, safely

Pick a screen or a single window, and VEENA can explain code, find errors, explain
an architecture diagram or summarise a slide. Before any pixel reaches a model,
OCR finds passwords, API keys, tokens and card numbers and **paints over them**.
VEENA can't capture anything you didn't pick: an automated test calls the
capture API without a selection and checks that it's refused. A "Sharing" pill
with a Stop button stays visible the whole time, and frames are never saved.

![Choosing exactly what to share](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/screen-picker.png)

### 3. It shows its sources

Ask a question about your documents and VEENA answers with numbered citations.
Click one to see the exact passage it came from. A governance check flags
answers that cite passages that don't exist, or that ignore evidence that was found.
If nothing relevant exists, VEENA says so instead of guessing.

![A cited answer from my own documents](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/citations.png)

### 4. It does more than meetings

VEENA has a meeting copilot (summary, decisions, action items with owners)…

![Meeting notes written by a local model](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/meeting.png)

…and an interview practice coach for eight roles, which scores your answers 0–10
with improvements and a follow-up question. It's for rehearsal, not covert use in
real interviews.

![Interview practice](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/interview.png)

### 5. It's open source

Every line is on GitHub under GPL-3.0: the app, 140 tests, the benchmark
scripts, and the script that captured every screenshot in this article. You can
read exactly what happens to your audio and screen, and change it.

---

## Where Google is ahead, honestly

A one-person build doesn't beat a Google DeepMind team on everything:

- **Model quality.** Foresight uses Gemma 4. I tested VEENA with Qwen2.5 1.5B, a
  small model chosen to run on modest hardware. It's useful, but it sometimes
  contradicts itself (you can see that in the interview screenshot above).
- **Speed.** Foresight is built for Apple Silicon's GPU. My measurements come from
  a 4-core machine with **no GPU**: answers start in 0.19 s and speech transcribes
  2.6× faster than real time, but analysing a screenshot takes about a minute.
- **Shorthand-to-notes.** Foresight's signature feature, turning your rough bullet
  points into polished notes, is something VEENA doesn't have yet.
- **Polish.** Google's design and engineering team, versus my unsigned v0.1 builds
  that trigger a security warning on first launch.

![Measured performance on a CPU-only machine](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/chart-latency.png)

---

## What it cost to build

| Item | Cost |
|---|---|
| AI-assisted engineering (Claude Code) | My existing Claude subscription |
| Every library and model | $0 |
| GitHub hosting and Windows/macOS/Linux CI builds | $0 (public repository) |
| Build time | About 6 hours of AI-assisted work |

The tests caught seven real bugs that a demo would have hidden. Among them, my own
security rules were blocking screen sharing, and "offline" mode quietly contacted
the internet on startup. Both are fixed.

---

## What Google's launch really tells us

I don't see Foresight as competition so much as confirmation. When Google
ships a free, offline AI assistant and says your meetings never need to leave your
laptop, it validates the whole idea:

1. **Local models are now good enough** for real-time meeting help.
2. **Privacy is a feature people want**, not an afterthought.
3. **A per-seat monthly bill for this category is getting harder to justify.**

Google's version is polished and Mac-only. Mine is cross-platform, open source and
broader in scope. The next step is the one that matters: putting both on the same
Mac, running the same meeting through each, and publishing the results.

---

## Try VEENA.AI

1. Install [Ollama](https://ollama.com/download) (free).
2. Get VEENA from GitHub:
   [github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)
3. Run it from source:

```bash
git clone https://github.com/florina787/Data-sets
cd Data-sets && git checkout claude/amazing-babbage-qia83y
cd veena-ai && ./scripts/setup.sh        # Windows: .\scripts\setup.ps1
cd apps/desktop && npm run dev
```

The setup wizard downloads the models and benchmarks your machine.

*Previously: [Parakeet AI Costs $149.90 a Month. I Built a $0 Replacement](https://medium.com/@florinaregius/parakeet-ai-costs-149-90-c94b8c0b4661)*

---

**Sources**

¹ Google AI Edge Foresight:
[Google Gemma on X (announcement)](https://x.com/googlegemma/status/2112657975789949376) ·
[Android Authority](https://www.androidauthority.com/google-ai-edge-foresight-embedding-gemma-2-3719906/) ·
[How-To Geek](https://www.howtogeek.com/googles-new-ai-note-taker-doesnt-need-the-cloud/) ·
[Notebookcheck](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html) ·
[GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/).
Official page: developers.google.com/edge/foresight.

² Parakeet AI pricing (third-party roundups):
[Copilot Interview](https://copilotinterview.com/blog/parakeet-ai-pricing) ·
[Interview Sidekick](https://interviewsidekick.com/blog/parakeet-ai-pricing).

*VEENA.AI performance figures were measured on a 4-vCPU, 15.7 GB, no-GPU Linux VM on
2026-10-24. Foresight's features are as reported by Google and the press; I haven't
benchmarked Foresight.*
