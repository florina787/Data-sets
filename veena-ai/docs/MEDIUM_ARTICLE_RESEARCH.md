# Google Is Spending $205 Billion on AI This Year. I Built a Rival App With a Claude Subscription. Here's the Honest Scorecard.

### Google AI Edge Foresight and my weekend project VEENA.AI both run private AI meeting assistants on your own laptop, for $0. I researched them source by source. The money gap is absurd. The quality gap is real. And three things I'd already published were wrong.

**GitHub repository:** [github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)

![VEENA.AI](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/apps/desktop/build/background.png)

---

## The money, first

Let's start with the numbers, because they're the story.

**Google:** Alphabet's 2026 capital spending guidance is **$195–205 billion**. It
raised that figure in July 2026 from $180–190 billion.¹ That money goes mostly on
servers, data centres and networking for *all* of Google's AI, not on any single
app.

**What Google spent on Foresight specifically:** not disclosed. No one outside
Google knows, and I won't guess. What we do know is that Foresight sits on top of
Google DeepMind's **Gemma 4** and **EmbeddingGemma 2** models, Google's **LiteRT**
on-device AI engine, and the work of the Google AI Edge and Android ML teams.²

**Me:** VEENA.AI cost my existing **Claude subscription** and about **6 hours** of
AI-assisted building over one weekend. Every model and library in it is free.

**What either one costs you to use:** **$0**. Both run on your own computer, with no
subscription.

**What they both replace:** paid cloud copilots such as Parakeet AI, which lists
**$149.90 a month** per seat.³ At that list price, about 6,700 seats would cost
roughly **$1 million a month**.

| | Google AI Edge Foresight | VEENA.AI |
|---|---|---|
| Backer's AI spending | Part of Alphabet's $195–205B 2026 AI capex | One Claude subscription |
| Cost to build this app | Not disclosed | ~6 hours of AI-assisted work |
| Team | Google AI Edge + Android ML teams, Google DeepMind models | One person + an AI assistant |
| Price to you | $0 | $0 |

So I asked the obvious question: **with a gap that big in resources, how close is the
weekend project to Google's?**

---

## How I researched it

Opinions are cheap, so I graded evidence instead. I went through:

- Google's official [announcement](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/) and [product page](https://developers.google.com/edge/foresight);
- Foresight's public installer, to see what's actually inside;
- every hands-on review and press article I could find;
- VEENA's own tests, measurements and documentation.

Every claim got a grade: tested with real models, tested with simulated models,
independently observed, vendor-claimed only, or unverified.

---

## The verdict

**VEENA wins on breadth. Foresight wins on depth.**

VEENA is open source, runs on Windows, macOS and Linux, can read your screen, and
gives you control over every model and every byte of data. Foresight is better at
the job both apps share, the live meeting. It captures audio from any meeting app on
a Mac, turns your rough bullet points into polished notes, connects to Google Drive
and Calendar, and runs much stronger models.

Nobody, including me, has run the two side by side on the same Mac yet. The honest
answer is **"different strengths, unproven head to head"**, not "way better".

For one person, one weekend and one subscription against a Google team, I'll take that.

---

## What Google shipped

Foresight launched on **6 October 2026** as "an experimental app that brings a
context-aware meeting companion directly to your device."² According to Google and
the press⁴:

- **Notes:** you type shorthand bullets and it expands them into full notes using the transcript.
- **Live Assistance:** it hears questions in the meeting and answers them with "proactive context cards with exact citations".
- **Knowledge:** it searches your local folders, Google Drive and Calendar, including PDFs, Docs, Office files, Markdown and bookmarks, and images too.
- **Meetings:** Google Meet, Zoom, any meeting app, or in-person, using the Mac's microphone and system audio.
- **Models:** Gemma 4 and EmbeddingGemma 2, both Apache 2.0.
- **Requirements:** Apple Silicon only, macOS 14.2 or later; a roughly 160 MB installer.
- **Licence:** the app itself is "© 2026 Google LLC. All rights reserved". No source code released.

---

## Where the $0 weekend project wins

### 1. You can read every line of it

VEENA is **GPL-3.0 open source**. Foresight is a closed Google binary. For a tool
that listens to your meetings, being able to audit exactly what happens to your audio
and screen is worth a lot.

### 2. It runs on the computer you actually have

VEENA builds for **Windows, macOS and Linux**, and CI builds and launches the installer
on all three. Foresight needs an **Apple Silicon Mac on macOS 14.2+**. If you're on
Windows or Linux, Google's app isn't an option.

### 3. It can see your screen

Pick a screen or a window and VEENA explains code, finds errors or summarises a slide,
masking passwords and keys before any model sees the image. I found **no screen
feature in Foresight**, not in Google's pages, the press or the installer.

![Screen picker](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/screen-picker.png)

### 4. You control the data, and the tests prove the controls work

VEENA has tested controls for deleting sessions, clearing all history, automatic
expiry, masking secrets on screen, and refusing to capture any screen you didn't pick.
Its backend accepts connections only from your own machine, with a fresh token each
launch.

Google says Foresight's AI runs "100% locally" and files and transcripts are "never
transmitted to external cloud servers". But one hands-on log analysis, by
[talat](https://talat.app/blog/google-ai-edge-foresight), found de-identified usage
data sent with no opt-out, starting before sign-in, plus a background job that
relaunches the app every four hours. **Caveat:** talat sells a competing product, and
nobody has confirmed this with an independent network capture. No audio or transcript
content was seen leaving the machine.

### 5. It does more than meetings

VEENA adds **interview practice** for eight roles, a **check that flags made-up
sources**, and lets you **swap in any model** Ollama runs.

---

## Where Google's money shows

### 1. Meetings on a Mac

Foresight captures **system audio from any meeting app on a Mac**. VEENA does that
**only on Windows**, and no automated test covers it. For a Zoom call on a MacBook,
Foresight simply does more today.

### 2. Shorthand to full notes

Turning rough bullets into polished notes is Foresight's signature feature. **VEENA
doesn't have it.**

### 3. Drive, Calendar and image search

Foresight plugs into Google Drive and Calendar and searches images. VEENA searches
local text documents only.

### 4. Much stronger models

This is where billions in AI research pay off. Foresight's default **Gemma 4 E4B**
scores **69.4** on MMLU-Pro and **58.6** on GPQA Diamond
([Google's figures](https://huggingface.co/google/gemma-4-E4B-it)). VEENA's mid-tier
default, **Qwen2.5-3B**, scores **43.7** and **30.3**
([Qwen's figures](https://qwenlm.github.io/blog/qwen2.5-llm/)). The test versions
differ, so treat it as directional, but the gap is large. Google's search model,
[EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2), is also far
stronger: 100+ languages, 8,192-token inputs, and image search.

### 5. Real use and polish

Testers used Foresight in real meetings, including a 90-minute one, where the summary
finished about two minutes after the meeting on an M3 MacBook
([talat](https://talat.app/blog/google-ai-edge-foresight),
[Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)).
It updates itself. VEENA's installers are unsigned and don't.

---

## Google's money didn't buy perfection

Early testers, mostly competitors, found real problems:

- **English only in practice.** Accented letters are stripped and Arabic failed. Community add-ons already patch in Chinese and Persian.
- **No speaker labels**, and no automatic detection of when a call starts.
- **Duplicated, garbled text** when remote audio plays through laptop speakers.
- **Inconsistent features:** a chat that apologised instead of summarising, Live Enhance staying silent, a solo recording summarised as a "team discussion", failed YouTube and web imports, and one crash.

Google itself frames Foresight as an experiment and a developer showcase.

---

## Three things I got wrong

Good research should change your mind. Mine corrected three claims I'd already published.

**1. "Foresight doesn't show citations."** Wrong. Google officially promises "exact
citations". It's on their own page.

**2. "Every model in VEENA is free to use."** Not quite. VEENA's mid-tier default,
**Qwen2.5-3B, is under the Qwen Research License, not Apache 2.0**, which limits
commercial use. The vision model Qwen2.5-VL-3B probably has the same licence; I
haven't confirmed it. Google's Gemma 4 and EmbeddingGemma 2 are **Apache 2.0**.
So VEENA's *code* is more open than Foresight's, but its default *models* are less
open. That also weakens the "$1 million a month saved" scenario for businesses, until
the defaults change.

**3. "VEENA works offline."** It's *designed* to: every model runs locally, and I fixed
startup code that used to contact the internet. But I've **never tested it with the
network actually switched off**, and an earlier build broke this promise once. Until
that test exists, "designed to work offline" is the honest wording.

Also worth saying plainly: VEENA's **meeting notes and interview practice have only
been tested with a simulated model**, and its real-model tests ran on one 4-core
Linux machine with no GPU.

---

## The scorecard

| | VEENA.AI | Google AI Edge Foresight |
|---|---|---|
| Price to you | $0 | $0 |
| What it took to build | 1 person, a Claude subscription, ~6 hours | Google teams; cost not disclosed |
| Source code | ✅ GPL-3.0 | ❌ closed |
| Windows / Linux | ✅ | ❌ |
| Mac | ✅ (Apple Silicon build) | ✅ Apple Silicon, macOS 14.2+ |
| Meeting audio from any app on a Mac | ❌ (Windows only, untested) | ✅ |
| Shorthand → full notes | ❌ | ✅ |
| Live question answering | ✅ | ✅ |
| Citations | ✅ | ✅ (official) |
| Flags made-up citations | ✅ | Not mentioned |
| Screen understanding | ✅ | ❌ not found |
| Interview practice | ✅ | ❌ |
| Google Drive / Calendar | ❌ | ✅ |
| Image search | ❌ | ✅ |
| Default model quality | Smaller Qwen2.5 | Stronger Gemma 4 |
| Default model licence | Mixed (3B is research-only) | Apache 2.0 |
| Usage data sent | None known | De-identified, no opt-out (one competitor's analysis) |
| Offline tested with network off | ❌ not yet | Claimed by Google; not independently tested |
| Auto-update | ❌ | ✅ |
| Side-by-side speed and accuracy test | **Nobody has run one** | **Nobody has run one** |

---

## Closing the gap costs almost nothing

Here's the irony. The biggest fix for VEENA is free, and it comes from Google:

1. **Switch the defaults to Gemma 4 and EmbeddingGemma 2.** They're Apache 2.0 and
   free to download, and they fix model quality and licensing in one move. Google
   paid for the research; open weights let a weekend project use it.
2. **Add an automated offline test** that runs VEENA with the network switched off
   and fails if it tries to connect anywhere.
3. **Test meetings and interviews with real models**, using noisy, multi-speaker and
   non-English recordings.
4. **Add meeting-audio capture on macOS.**
5. **Run both apps on the same Apple Silicon Mac** and publish the measurements.

Not one of those steps needs a budget.

---

## What the money really buys

When I set out to prove my project was "way better" than Google's, the evidence
didn't cooperate. VEENA's real strengths are openness, cross-platform support, screen
understanding and control over your data. Google's strengths are the ones money buys
directly: stronger models, polish and integration.

The bigger story is this. **A company spending up to $205 billion a year on AI and
one person with a Claude subscription now ship the same kind of product, at the same
$0 price, running on the same laptop.** Google's billions build the models. Open
weights put them in everyone's hands. What's left to build on top is small enough for
one person to do in a weekend.

That's good news for everyone except the companies charging $149.90 a month for it.

**Code:** [github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)

*Earlier in this series:*
[Parakeet AI Costs $149.90 a Month. I Built a $0 Replacement](https://medium.com/@florinaregius/parakeet-ai-costs-149-90-c94b8c0b4661) ·
[Google Released an Offline AI Meeting Assistant. So I Built My Own](https://medium.com/@florinaregius/google-released-an-offline-ai-meeting-assistant-so-i-built-my-own-and-it-does-more-69ee5622b5a9)

---

**Sources**

¹ Alphabet 2026 capital spending guidance:
[w.media](https://w.media/ai-infrastructure-demand-pushes-alphabets-2026-capex-guidance-to-us-205-billion/) ·
[The National](https://www.thenationalnews.com/business/2026/07/22/alphabet-increases-spending-outlook-as-it-races-to-build-ai-data-centres/) ·
[Yahoo Finance](https://finance.yahoo.com/news/google-parent-alphabet-forecasts-sharp-210559455.html).
Figures are from July 2026 and may be updated with later earnings.

² Google AI Edge Foresight, official:
[Google Developers Blog announcement](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/) ·
[Product page](https://developers.google.com/edge/foresight) ·
[Gemma 4 E4B model card](https://huggingface.co/google/gemma-4-E4B-it) ·
[EmbeddingGemma 2 model card](https://huggingface.co/google/embeddinggemma-2)

³ Parakeet AI pricing (third-party roundups):
[Copilot Interview](https://copilotinterview.com/blog/parakeet-ai-pricing) ·
[Interview Sidekick](https://interviewsidekick.com/blog/parakeet-ai-pricing)

⁴ Press:
[9to5Google](https://9to5google.com/2026/10/08/google-ai-edge-foresight/) ·
[TechCrunch](https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/) ·
[Android Authority](https://www.androidauthority.com/google-ai-edge-foresight-embedding-gemma-2-3719906/) ·
[heise](https://www.heise.de/en/news/Google-s-macOS-app-Local-AI-to-capture-notes-and-work-with-files-11479591.html) ·
[Notebookcheck](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html) ·
[eWeek](https://www.eweek.com/news/google-ai-edge-foresight-mac/) ·
[The Decoder on Gemma 4's Apache 2.0 licence](https://the-decoder.com/googles-gemma-4-is-now-available-with-apache-2-0-licensing-for-the-first-time/)

*Hands-on reports (both by competing products):*
[talat](https://talat.app/blog/google-ai-edge-foresight) ·
[Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)

*Benchmark scores come from each model's own developer on different test versions,
so treat the comparison as directional. VEENA's performance was measured on a
4-vCPU, no-GPU Linux machine; Foresight has no published speed figures. The full
research report with evidence grades is in the GitHub repository under `reports/`.*
