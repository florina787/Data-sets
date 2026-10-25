# I Said My Free AI Beat Google's. Then I Researched It Properly.

### My weekend project VEENA.AI and Google AI Edge Foresight both run AI meetings entirely on your laptop, for $0. I ran a deep, source-by-source comparison. VEENA isn't "way better", and three things I'd already published turned out to be wrong.

**GitHub repository:** [github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)

![VEENA.AI](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/apps/desktop/build/background.png)

---

## How we got here

Two weeks ago I wrote that Parakeet AI costs
[$149.90 a month and I built a $0 replacement](https://medium.com/@florinaregius/parakeet-ai-costs-149-90-c94b8c0b4661).
Then Google released **Google AI Edge Foresight**, a free, on-device meeting
assistant for Mac, and I wrote that
[I built my own and it does more](https://medium.com/@florinaregius/google-released-an-offline-ai-meeting-assistant-so-i-built-my-own-and-it-does-more-69ee5622b5a9).

Readers asked the obvious question: *is it actually better?*

So I stopped writing opinions and ran a proper research pass. I read Google's
official announcement and product page, opened Foresight's public installer to see
what's inside, read every hands-on review I could find, and compared all of it
against VEENA's own tests and measurements. I graded every claim by how strong its
evidence is.

Here's what I found, including the parts that don't flatter my project.

---

## The verdict in one paragraph

**VEENA wins on breadth. Foresight wins on depth.** VEENA is open source, runs on
Windows, macOS and Linux, can read your screen, and gives you control over every
model and every byte of data. Foresight is better at the job both apps share, the
live meeting: it captures audio from any meeting app on a Mac, turns your rough
bullet points into polished notes, connects to Google Drive and Calendar, and runs
much stronger models. Nobody, including me, has put the two side by side on the
same Mac yet. So the honest answer is **"different strengths, unproven head to
head"**, not "way better".

---

## What Google actually shipped

Foresight was announced on **6 October 2026** in Google's Developers Blog post
[*Bring multimodal semantic search to the edge with EmbeddingGemma 2*](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/).
Google calls it "an experimental app that brings a context-aware meeting companion
directly to your device."

According to Google's [product page](https://developers.google.com/edge/foresight)
and press coverage ([9to5Google](https://9to5google.com/2026/10/08/google-ai-edge-foresight/),
[TechCrunch](https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/),
[Android Authority](https://www.androidauthority.com/google-ai-edge-foresight-embedding-gemma-2-3719906/),
[heise](https://www.heise.de/en/news/Google-s-macOS-app-Local-AI-to-capture-notes-and-work-with-files-11479591.html),
[Notebookcheck](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html)):

- **Notes:** you type shorthand bullets and it expands them into full notes using the meeting transcript.
- **Live Assistance:** it hears questions during the meeting and answers them, with "proactive context cards with exact citations".
- **Knowledge:** it searches your local folders, Google Drive and Calendar, including PDFs, Google Docs, Office files, Markdown and bookmarks. It searches images too, not just text.
- **Meetings:** Google Meet, Zoom, any meeting app, or in-person conversations, using the Mac's microphone and system audio.
- **Models:** Gemma 4 for writing and EmbeddingGemma 2 for search, both under the Apache 2.0 licence.
- **Requirements:** Apple Silicon only, macOS 14.2 or later. The installer is about 160 MB, and the models download on first launch.
- **Licence:** the app itself is "© 2026 Google LLC. All rights reserved". No source code has been released.

---

## Where VEENA is genuinely better

These advantages hold up against the evidence.

### 1. You can read every line of it

VEENA is **GPL-3.0 open source**. You can audit exactly what happens to your audio,
screen and documents, change it, and run your own build. Foresight is a closed
Google binary. For a tool that listens to your meetings, that difference matters.

### 2. It runs on the computer you actually have

VEENA builds for **Windows, macOS and Linux**. CI builds installers on all three and
checks that each packaged app starts its local backend correctly. Foresight
requires an **Apple Silicon Mac on macOS 14.2 or later**, so if you use Windows or
Linux, it isn't an option at all.

### 3. It can see your screen

Pick a screen or a window and VEENA explains code, finds errors, or summarises a
slide. It masks passwords and keys before any model sees the image. I found **no
screen feature in Foresight**, in Google's pages, the press coverage or the
installer itself.

![Screen picker](https://raw.githubusercontent.com/florina787/Data-sets/claude/amazing-babbage-qia83y/veena-ai/docs/images/screen-picker.png)

### 4. You control the data, and the tests prove the controls work

VEENA has tested controls for:
- deleting a session or clearing all history;
- automatic history expiry;
- masking secrets on screen;
- refusing to capture any screen you didn't pick.

Its backend only accepts connections from your own machine, with a token generated
for each launch.

Foresight's privacy story is good on paper. Google says "all AI inference runs
100% locally" and files and transcripts are "never transmitted to external cloud
servers". But one hands-on log analysis, by
[talat](https://talat.app/blog/google-ai-edge-foresight), found de-identified usage
data sent with no opt-out, starting before sign-in, plus a background job that
relaunches the app every four hours. **Important caveat:** talat makes a competing
product, and nobody has independently confirmed this with a network capture. No
audio or transcript content was seen leaving the machine.

### 5. It does more than meetings

VEENA also does **interview practice** for eight roles, a **check that flags
made-up sources** in answers, and lets you **swap in any model** that Ollama runs.

---

## Where Foresight is better

### 1. Meetings on a Mac

Foresight captures **system audio from any meeting app on a Mac**. VEENA's
system-audio capture works **only on Windows**, and no automated test covers it.
For the most common use case, a Zoom call on a MacBook, Foresight simply does more
today.

### 2. Shorthand to full notes

Its signature feature, turning rough bullet points into polished notes using the
transcript, **doesn't exist in VEENA**.

### 3. Google Drive, Calendar and image search

Foresight connects to your Drive and Calendar and searches images as well as text.
VEENA searches local text documents only.

### 4. Much stronger models

This is the big one. Foresight's default model, **Gemma 4 E4B**, scores **69.4** on
MMLU-Pro and **58.6** on GPQA Diamond by
[Google's own figures](https://huggingface.co/google/gemma-4-E4B-it).
**Qwen2.5-3B**, VEENA's mid-tier default, scores **43.7** and **30.3** by
[Qwen's own figures](https://qwenlm.github.io/blog/qwen2.5-llm/). The test versions
differ, so it isn't a perfectly fair comparison, but a gap that size is real. Foresight's
search model, [EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2),
is also far more capable than VEENA's: it covers 100+ languages, reads 8,192
tokens at a time, and searches images.

### 5. Real meetings, real use

Testers used Foresight in actual meetings, including a 90-minute one, where the
summary finished about two minutes after the meeting on an M3 MacBook
([talat](https://talat.app/blog/google-ai-edge-foresight),
[Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)).
Foresight also updates itself automatically. VEENA's installers are unsigned and
don't update themselves.

---

## Foresight isn't perfect either

Early testers, again mostly competitors, found real problems:

- **English only in practice.** Accented letters disappear and Arabic failed.
  Community add-ons already patch in Chinese and Persian.
- **No speaker labels**, and no automatic detection of when a call starts.
- **Duplicated, garbled text** when the remote side plays through laptop speakers.
- **Inconsistent features:** a chat that apologised instead of summarising, Live
  Enhance staying silent, a solo recording summarised as a "team discussion",
  failed YouTube and web imports, and one crash.

It's an experimental app, and Google frames it mainly as a developer showcase.

---

## Three things I got wrong

Good research should change your mind. Mine changed three claims I'd already published.

**1. "VEENA shows citations; Foresight doesn't."** Wrong. Google officially says
Foresight shows "proactive context cards with **exact citations**". In my previous
article I said citations weren't mentioned in the coverage. They are on Google's own page.

**2. "Every model in VEENA is free to use."** Not quite. VEENA's mid-tier default
text model, **Qwen2.5-3B, is under the Qwen Research License, not Apache 2.0**, and
that licence limits commercial use. The vision model Qwen2.5-VL-3B probably has the
same licence; I haven't confirmed it yet. Google's Gemma 4 and EmbeddingGemma 2 are
both **Apache 2.0**. So VEENA's *code* is more open than Foresight's, but its
default *models* are less open. That weakens the "6,700 seats for $0" scenario in my
Parakeet article for business use.

**3. "VEENA works offline."** It's *designed* to: all the AI runs locally, and I
fixed the startup code that used to contact the internet. But I have **never tested
it with the network actually switched off**, and an earlier build already broke this
promise once. Until that test exists, "designed to work offline" is the honest wording.

One more limit worth stating plainly: VEENA's **meeting notes and interview
practice have only been tested with a simulated model**, never end to end with a
real one. Its real-model tests ran on a single 4-core Linux machine with no GPU.

---

## The full scorecard

| | VEENA.AI | Google AI Edge Foresight |
|---|---|---|
| Price | $0 | $0 |
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

## What VEENA needs to earn "better"

The research turned into a to-do list:

1. **Switch to Apache-licensed default models.** Ironically, the best choice is
   Google's own: Gemma 4 and EmbeddingGemma 2. That fixes model quality and
   licensing in one move.
2. **Add an automated offline test** that runs VEENA with the network switched off
   and fails if it tries to connect anywhere.
3. **Test meetings and interviews with real models**, using noisy, multi-speaker and
   non-English recordings.
4. **Add meeting-audio capture on macOS.**
5. **Run both apps on the same Apple Silicon Mac**, recording the same meetings,
   with at least five runs per measurement, and publish the results.

---

## What this taught me

Calling your project "way better" than Google's is easy. Showing it is harder.

When I checked the evidence, VEENA's real strengths were different from the ones I'd
been shouting about. It's open, it's cross-platform, it sees your screen, and it
hands you control. Google's strengths are the ones a big lab is good at: stronger
models, polish and integration.

The good news is that both products prove the same point. **Private, offline,
$0 AI meeting assistants are real now.** Google built one with a DeepMind team
behind it. I built one with a Claude subscription in a weekend. The gap between
them is a short, concrete to-do list, and the whole thing is open source if you
want to help close it.

**Code:** [github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)

---

**Sources**

*Google AI Edge Foresight, official:*
[Google Developers Blog announcement](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/) ·
[Product page](https://developers.google.com/edge/foresight) ·
[Gemma 4 E4B model card](https://huggingface.co/google/gemma-4-E4B-it) ·
[EmbeddingGemma 2 model card](https://huggingface.co/google/embeddinggemma-2)

*Press:*
[9to5Google](https://9to5google.com/2026/10/08/google-ai-edge-foresight/) ·
[TechCrunch](https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/) ·
[Android Authority](https://www.androidauthority.com/google-ai-edge-foresight-embedding-gemma-2-3719906/) ·
[heise](https://www.heise.de/en/news/Google-s-macOS-app-Local-AI-to-capture-notes-and-work-with-files-11479591.html) ·
[Notebookcheck](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html) ·
[eWeek](https://www.eweek.com/news/google-ai-edge-foresight-mac/) ·
[GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/) ·
[The Decoder on Gemma 4's Apache 2.0 licence](https://the-decoder.com/googles-gemma-4-is-now-available-with-apache-2-0-licensing-for-the-first-time/)

*Hands-on reports (both by competing products):*
[talat](https://talat.app/blog/google-ai-edge-foresight) ·
[Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)

*Qwen2.5 benchmarks and licences:* [Qwen2.5 announcement](https://qwenlm.github.io/blog/qwen2.5-llm/)

*VEENA.AI:* tests, benchmarks and documentation in the
[GitHub repository](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai).
The full research report with evidence grades is in the repository under
`reports/`.

*Benchmark scores come from each model's own developer and use different test
versions, so treat the comparison as directional. VEENA's performance was measured
on a 4-vCPU, no-GPU Linux machine. Foresight has no published speed figures.*
