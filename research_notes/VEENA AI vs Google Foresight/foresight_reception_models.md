# Google AI Edge Foresight: Real-World Reception, Performance, Limitations, and Underlying Models (as of 25 Oct 2026)

Context: Foresight is a free, experimental macOS meeting note-taker announced by Google on 6 Oct 2026 ([Notebookcheck](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html); [GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/)). It is less than three weeks old, so the evidence base is **thin**. There are only two hands-on write-ups with any specifics, and **both come from competitors** (talat and Recall). Most other coverage rewrites Google's announcement. The official page (developers.google.com/edge/foresight) did not render when fetched, so the official claims below come from press quotes.

## Hands-on reviews: transcription accuracy, latency, note quality, resource use, bugs, missing features

### Takeaway
Both hands-on testers rate English transcription as accurate and fast. They also found slow summaries, a buggy "Live Enhance" feature, chat that failed to retrieve answers, echo or duplication with laptop speakers, no speaker labels, and no auto-detection of calls. Nobody has published measurements of RAM, CPU, GPU or battery use.

### Cited Findings
**Measured or observed results (single tester, small sample; both testers are competitors):**
- Test setup for talat: a few minutes of use, static analysis of the app, and macOS logs kept over a weekend. Signed-in mode and Google Calendar were not tested. The author works for talat, a competing local note-taker. — [talat](https://talat.app/blog/google-ai-edge-foresight)
- Setup took about 8.5 minutes before recording was possible, on a fast connection. About 4.2 GB of models downloaded during setup. The app itself is a 153 MB download and 376 MB unpacked. — [talat](https://talat.app/blog/google-ai-edge-foresight)
- Model choice depends on available memory, with up to three Gemma sizes offered. The tester saw Gemma 4 E4B (the default) and Gemma 4 12B, and tested a 3.41 GB model. About 800 MB more is downloaded for speech recognition and search models. — [talat](https://talat.app/blog/google-ai-edge-foresight)
- English transcription was "very good and quick" and nearly error-free. Words appear provisionally and then firm up. — [talat](https://talat.app/blog/google-ai-edge-foresight)
- Microphone and system audio are recorded as separate streams, and speakers are not identified. With laptop speakers instead of headphones, remote speech appears twice and the microphone copy is often garbled ("water contact" for "longer context"). Headphones avoided the problem. — [talat](https://talat.app/blog/google-ai-edge-foresight)
- Bugs:
  - Live Enhance showed as on but produced nothing until the note style was toggled.
  - Asked for a summary nine minutes into a recording, chat apologised three times.
  - A 12-minute solo recording with a video playing was summarised as a "team discussion".
  - — [talat](https://talat.app/blog/google-ai-edge-foresight)
- Calls must be started manually because nothing detects when a call begins. Transcripts are kept but audio is discarded. There is no dictation and no audio-file import. — [talat](https://talat.app/blog/google-ai-edge-foresight)
- Foresight crashed once (17:29 on Saturday) while being relaunched by a background job. — [talat](https://talat.app/blog/google-ai-edge-foresight)
- Recall test setup: Foresight 1.0.0 (build 1.0.0.28.20261005) on an M3 with 16 GB RAM, macOS 26.5.2. The author works for Recall, a competing "second brain" product, and calls the test "not a full review". — [Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)
- On a meeting of about 1.5 hours, transcription kept up and matched what was said. The summary showed 55% done and took about two more minutes before the overview appeared. — [Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)
- Imported sources:
  - PDFs imported and worked as references during a meeting.
  - Adding a YouTube video saved only the YouTube page footer.
  - A web article would not save.
  - — [Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)
- Asked a factual question about the meeting, chat said it could not find the answer in the context. The author says this was a single miss. — [Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)
- Neither tester measured RAM, CPU or battery use. — [talat](https://talat.app/blog/google-ai-edge-foresight); [Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)

**Platform and specification facts (reported, not measured):**
- The app runs on Apple Silicon Macs only. No Intel, Windows, Android or iPhone versions exist. — [Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain); [The Tech Basket](https://www.thetechbasket.com/google-ai-edge-foresight/)
- The FAQ says it is "optimized for Apple Silicon and can completely work offline". TechCrunch reports no RAM requirement. — [TechCrunch](https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/)
- Google describes it as an experimental developer showcase that may change or disappear. — [Notebookcheck](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html); [New Face Design](https://newfacedesign.com/blog/google-ai-edge-foresight)
- Features include:
  - Granola-style split screen (your shorthand next to AI notes).
  - Live notes enhancement.
  - Detection of questions asked during the meeting, with answers.
  - A knowledge base built from PDFs, Google Docs, Office files, text, Markdown and web bookmarks.
  - — [TechCrunch](https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/); [GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/)
- The app is built with Flutter and Dart. — [farsight (GitHub)](https://github.com/hadi-buddy/farsight)

**Opinion and editorial:**
- TechCrunch suggests the app may mainly showcase offline Gemma models, noting that the same team's earlier iOS dictation app "didn't reach mainstream use". — [TechCrunch](https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/)
- One commentary notes there are no independent tests of accuracy, resource use or non-English quality. — reported via [pasqualepillitteri.it](https://pasqualepillitteri.it/en/news/21914/google-foresight-mac-offline-meeting-transcription)

### Inferences
- The model default (E4B, about 3.4 GB) plus about 800 MB of ASR and embedding models suggests that roughly 4–5 GB of model weights must be resident or paged. This is my estimate and has not been measured. On an 8 GB Mac it would compete heavily with the meeting app itself.
- The summary latency (about 2 minutes for a 90-minute meeting on an M3 with 16 GB) is one data point. It shows that end-of-meeting summarisation is not instant even with a 4B-class model.
- Both detailed testers sell competing products, which may bias them toward finding flaws.

### Gaps
- No independent, non-competitor hands-on review with measurements was found: no WER, no RAM, CPU or GPU profile, no battery drain, no thermals.
- I found no YouTube reviews with measured results. None surfaced in searches.
- Behaviour on 8 GB Macs is undocumented.

## User sentiment: Reddit, Hacker News, X, Product Hunt, YouTube

### Takeaway
Community discussion is very sparse. Hacker News submissions got almost no traction, I found no Reddit threads, and the visible "community" activity is mostly GitHub hacks that add languages or ports.

### Cited Findings
- Five HN submissions linked the official page between 7 and 17 Oct 2026. They scored 6, 1, 7, 4 and 2 points, with **zero comments** each (for example, "Google AI Edge Foresight – offline, private meeting transcripts", 6 points, id 49998314). — [HN Algolia API](https://hn.algolia.com/api/v1/search?query=foresight%20google&tags=story&numericFilters=created_at_i>1790000000)
- An X post from TestingCatalog announced the launch. No engagement data was obtained. — [X/testingcatalog](https://x.com/testingcatalog/status/2107853628656496657)
- Community GitHub projects:
  - Shims that add Chinese, Traditional Chinese and Persian transcription: [foresight-zh](https://github.com/zhubeilife/foresight-zh), [foresight-zhtw](https://github.com/itemx/foresight-zhtw), [farsight](https://github.com/hadi-buddy/farsight).
  - An unofficial Windows port: [foresight-win](https://github.com/Pantheonn3D/foresight-win).
  - An open-source clone for Linux and macOS using Gemma, Whisper, RAG and MCP: [open-foresight](https://github.com/teng-lin/open-foresight).
- Press tone is broadly positive about the privacy-first, on-device concept. It frames the app as a Granola competitor and calls it an experiment, not a polished product. — [How-To Geek](https://www.howtogeek.com/googles-new-ai-note-taker-doesnt-need-the-cloud/); [AI Weekly](https://aiweekly.co/alerts/google-launches-ai-edge-foresight-to-rival-granola-on-mac); [TechCrunch](https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/)

### Inferences
- Several third-party language shims appeared within about two weeks. This suggests that missing non-English transcription is the most acute pain point for early adopters. The limitation is real enough that people are patching the binary at runtime.

### Gaps
- No Reddit threads were found (r/LocalLLaMA, r/macapps, r/MacOS) in several searches. Some may exist but were not indexed.
- No Product Hunt page or YouTube reviews were found.
- X sentiment could not be assessed.

## Which speech-recognition model does Foresight use? Language support?

### Takeaway
Google has not publicly named the ASR model. Community reverse engineering shows a Google on-device speech library, reached through an "Odml" C API, with an English-only model. The Dart layer also strips non-ASCII characters from transcripts. In practice, transcription is **English-only**.

### Cited Findings
- Foresight's Dart code calls Google's transcription library through a C API (`OdmlSpeechProcessorTranscribe`, `OdmlSpeechProcessorFinishStream`) resolved via `dlsym`. Audio comes in at 48 kHz. The project says that "Foresight ships with an English-only speech model." — [farsight (GitHub)](https://github.com/hadi-buddy/farsight)
- Foresight's Dart layer strips non-ASCII characters from transcripts with a regex. The shim patches this in memory. — [farsight (GitHub)](https://github.com/hadi-buddy/farsight)
- Hands-on test:
  - French words were understood but accented letters were dropped.
  - Arabic was not followed at all.
  - No language setting was found.
  - — [talat](https://talat.app/blog/google-ai-edge-foresight)
- A community Chinese shim also describes the bundled model as English-only. — [foresight-zh](https://github.com/zhubeilife/foresight-zh)
- Neither the TechCrunch nor the GIGAZINE launch coverage names the ASR model. — [TechCrunch](https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/); [GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/)
- Context: Gemma 4 E2B and E4B natively support ASR on audio clips of up to 30 seconds. — [Gemma 4 E4B model card](https://huggingface.co/google/gemma-4-E4B-it)
  - The unofficial Windows port uses Gemma 4 for transcription and offers 15 languages. This tells us nothing about the Mac app. — [search summary of foresight-win](https://github.com/Pantheonn3D/foresight-win)

### Inferences
- "ODML" is Google's on-device ML branding, so the ASR is likely a Google-internal streaming model and not Whisper or Gemma. This is inferred and not confirmed.
- For multilingual meetings, a faster-whisper stack (about 99 languages) has a clear functional advantage over Foresight as shipped.

### Gaps
- The exact ASR model name, size, and WER are unpublished.
- Whether the ASR runs on the Apple Neural Engine or the GPU is unknown.

## Privacy and security analyses (network traffic, telemetry)

### Takeaway
One hands-on log analysis found no audio or transcript content leaving the machine. It did find steady de-identified telemetry with no opt-out, starting before sign-in, which contradicts the in-app "100% offline" wording. It also found an undisclosed background job that relaunches the app every four hours. This is a single competitor's analysis.

### Cited Findings
- Google's claim (Suril Shah): "Your audio, transcripts and sensitive files in your personal knowledge base never leave your device." — [GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/)
- Telemetry observations from talat:
  - No audio or transcript content was seen leaving the machine.
  - While recording, a debug log captured 74 reports of 25 kinds in about two minutes.
  - Fields included meeting duration, word and character counts, question counts, calendar attachment, model names, tab names, startup timings and sign-in status, tied to an anonymous install ID.
  - Telemetry began within 2 seconds of first launch, before sign-in.
  - The setup screen mentions "de-identified usage data". No opt-out was found, while the in-app guide says the app "operates 100% offline".
  - — [talat](https://talat.app/blog/google-ai-edge-foresight)
- Background behaviour:
  - A login item is added at install.
  - A separate background job runs every 4 hours, named for refreshing calendar events. It is not disclosed and cannot be turned off in the app.
  - After the user quit the app, the job reopened it at 14:19 and 18:19, and a helper process kept running.
  - — [talat](https://talat.app/blog/google-ai-edge-foresight)
- PlayCISO's "security checklist" contains **no tested findings**, only recommendations (FileVault, LuLu or Little Snitch, checking backups, narrow permissions). It advises keeping the app away from the most sensitive meetings for now. — [PlayCISO](https://playciso.com/blog/google-ai-edge-foresight-security-settings-checks)
- Recall did not audit privacy claims. — [Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)
- Google Drive and Calendar import requires a connection. — [Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)

### Inferences
- "On-device processing" holds as far as anyone has tested. "100% offline" in the strict sense of no network traffic does not appear to hold by default.

### Gaps
- No independent, non-competitor packet capture (for example with Little Snitch or mitmproxy) has been published.
- Signed-in telemetry has not been tested.
- The storage location and encryption of local data are undocumented.

## Gemma 4: model sizes and benchmarks vs Qwen2.5 1.5B/3B; license

### Takeaway
Gemma 4 is Apache 2.0 licensed. Google's own scores for the small on-device variants (E2B and E4B) are far higher than Qwen2.5-1.5B and 3B on comparable reported benchmarks such as MMLU-Pro and GPQA. However, the numbers come from different vendors, eras and evaluation setups, and the E-models hold more total parameters in memory than their "effective" size suggests.

### Cited Findings
- Model lineup:

  | Model | Parameters | Context |
  |---|---|---|
  | E2B | 2.3B effective (5.1B with embeddings) | 128K |
  | E4B | 4.5B effective (8B with embeddings) | 128K |
  | 12B "Unified" | 11.95B | 256K |
  | 26B A4B MoE | 25.2B total, 3.8B active | 256K |
  | 31B dense | 30.7B | 256K |

  — [Gemma 4 E4B model card](https://huggingface.co/google/gemma-4-E4B-it)
  - Some launch reporting lists only four models (E2B, E4B, 26B MoE, 31B). The 12B appears in the model card and in Foresight's model picker. — [The Decoder](https://the-decoder.com/googles-gemma-4-is-now-available-with-apache-2-0-licensing-for-the-first-time/); [talat](https://talat.app/blog/google-ai-edge-foresight)
- E4B input is text, image and audio (up to 30 seconds), and video as frames (up to 60 seconds at 1 fps). It supports ASR and speech-to-translated-text. — [Gemma 4 E4B model card](https://huggingface.co/google/gemma-4-E4B-it)
- License: Gemma 4 is **Apache 2.0**, the first Gemma release on Apache instead of the custom Gemma Terms of Use. — [Gemma 4 E4B model card](https://huggingface.co/google/gemma-4-E4B-it); [The Decoder](https://the-decoder.com/googles-gemma-4-is-now-available-with-apache-2-0-licensing-for-the-first-time/); [Implicator](https://www.implicator.ai/google-releases-gemma-4-under-apache-2-0-dropping-its-custom-ai-license/)
- Gemma 4 instruction-tuned scores (vendor-reported). — [Gemma 4 E4B model card](https://huggingface.co/google/gemma-4-E4B-it)

  | Benchmark | E2B | E4B |
  |---|---|---|
  | MMLU-Pro | 60.0 | 69.4 |
  | MMMLU | 67.4 | 76.6 |
  | GPQA Diamond | 43.4 | 58.6 |
  | LiveCodeBench v6 | 44.0 | 52.0 |
  | AIME 2026 | 37.5 | 42.5 |
  | Tau2 | 24.5 | 42.2 |
  | BBEH | 21.9 | 33.1 |
  | MMMU-Pro | 44.2 | 52.6 |
  | MRCR v2 (128k) | 19.1 | 25.4 |
  | CoVoST | 33.47 | 35.54 |
  | FLEURS (lower is better) | 0.09 | 0.08 |

- The larger Gemma 4 models (vendor-reported, thinking mode):
  - 31B: MMLU-Pro 85.2, GPQA Diamond 84.3, LiveCodeBench v6 80.0.
  - 26B A4B: MMLU-Pro 82.6.
  - — [The Decoder](https://the-decoder.com/googles-gemma-4-is-now-available-with-apache-2-0-licensing-for-the-first-time/)
- Qwen2.5 instruct scores (vendor-reported, Sept 2024). — [Qwen2.5 blog](https://qwenlm.github.io/blog/qwen2.5-llm/)

  | Benchmark | 1.5B-Instruct | 3B-Instruct |
  |---|---|---|
  | MMLU-Pro | 32.4 | 43.7 |
  | MMLU-redux | 50.7 | 64.4 |
  | GPQA | 29.8 | 30.3 |
  | MATH | 55.2 | 65.9 |
  | GSM8K | 73.2 | 86.7 |
  | HumanEval | 61.6 | 74.4 |
  | LiveCodeBench (2305–2409) | 14.8 | 19.9 |
  | IFEval strict-prompt | 42.5 | 58.2 |

  - Base-model MMLU is 60.9 for 1.5B and 65.6 for 3B.
- License caveat: **Qwen2.5-1.5B is Apache 2.0, but Qwen2.5-3B uses the Qwen Research License**, not Apache. — [Qwen2.5 blog](https://qwenlm.github.io/blog/qwen2.5-llm/)
- Speed of Gemma 4 E4B on Apple Silicon (**mostly estimates, not controlled measurements**):

  | Machine | Runtime | Figure | Source and status |
  |---|---|---|---|
  | M1, 8 GB | Ollama, Q4_K_M | ~42 tok/s | Explicitly an estimate from bandwidth scaling ([LLMCheck](https://llmcheck.net/models/gemma-4-e4b-on-m1/)) |
  | M3 | Ollama | ~62 tok/s | Estimate ([LLMCheck](https://llmcheck.net/models/gemma-4-e4b-on-m1/)) |
  | M4 Pro, 24 GB | MLX | ~78 tok/s | Estimate ([LLMCheck](https://llmcheck.net/models/gemma-4-e4b-on-m4-pro/)) |
  | M3, 16 GB | MLX-LM | 40–60 tok/s | Reported in an article ([pasqualepillitteri.it](https://pasqualepillitteri.it/news/1587/free-offline-vibe-coding-gemma-4-mac-mlx)) |
  | Base M1, 16 GB | Not stated | 10–15 tok/s | "The 4B model", no methodology ([AI Indigo](https://aiindigo.com/blog/the-local-ai-stack-for-mac-optimizing-gemma-4-and-mlx-on-apple-silicon)) |

  - These sources conflict widely.

### Inferences
- On vendor numbers, E2B (60.0 MMLU-Pro) beats Qwen2.5-3B (43.7) and E4B (69.4) beats it by a wide margin. GPQA shows a similar gap (43.4 and 58.6 versus 30.3). The comparison is not apples to apples: the benchmark versions differ (GPQA vs GPQA Diamond, different LiveCodeBench windows), Gemma 4 scores may involve thinking mode, and the evaluations are about 1.5 years apart. Even so, the direction is very likely real.
- Memory footprint matters for a fair comparison. E4B is about 8B total parameters (Foresight's quantised download was 3.41 GB, per [talat](https://talat.app/blog/google-ai-edge-foresight)). Qwen2.5-1.5B is about 1 GB at 4-bit and 3B is about 2 GB. The smaller stack therefore has a real RAM and latency advantage on 8 GB Macs. The Qwen sizes are approximate and from my own calculation, not cited.
- Licensing: a stack using Qwen2.5-3B is *less* permissive than Gemma 4 (Apache 2.0) for commercial use.
- Qwen2.5-VL-3B is also under the Qwen Research License. This comes from my prior knowledge and was not verified in this session.

### Gaps
- No independent, like-for-like benchmark of Gemma 4 E2B/E4B against Qwen2.5-1.5B/3B was found.
- No measured tok/s for Gemma 4 E4B inside Foresight.
- No measured Apple Silicon latency for Qwen2.5 to compare.

## EmbeddingGemma 2 vs all-MiniLM-L6-v2; license

### Takeaway
EmbeddingGemma 2 (released 6 Oct 2026, Apache 2.0) is a 740M-parameter multimodal embedder. Its text-only path is 270M parameters. It reports MTEB English v2 68.46 and Multilingual v2 61.36. all-MiniLM-L6-v2 is 22.7M parameters, 384 dimensions, English-focused, with an MTEB average of about 56 on a different MTEB version. EmbeddingGemma 2 is much stronger and multilingual, but about 12 times larger even in text-only mode.

### Cited Findings
- Architecture:
  - 740M parameters in total: a 130M transformer plus a 140M embedder (270M for text), a 170M vision encoder and a 300M audio encoder.
  - Encoders load selectively: 270M text-only, 440M text and image, 570M text and audio.
  - Output is 768 dimensions, with Matryoshka truncation to 512, 256 or 128.
  - 8,192-token context; 100+ languages.
  - — [EmbeddingGemma 2 model card](https://huggingface.co/google/embeddinggemma-2)
- License: Apache 2.0. — [EmbeddingGemma 2 model card](https://huggingface.co/google/embeddinggemma-2); [Google AI docs](https://ai.google.dev/gemma/docs/embeddinggemma)
  - EmbeddingGemma 1 (300M) used the Gemma license. — [search summary](https://huggingface.co/lazyDataScientist/EmbeddingGemma/blob/main/README.md)
- Benchmarks at 768 dimensions (vendor-reported):
  - MTEB Multilingual v2: 61.36 (v1 was 61.15).
  - MTEB English v2: 68.46.
  - MTEB Code v1: 78.68 (v1 was 68.76).
  - Scores at lower dimensions:

    | Benchmark | 512d | 256d | 128d |
    |---|---|---|---|
    | MTEB English v2 | 68.41 | 67.78 | 65.68 |
    | MTEB Multilingual v2 | 61.17 | 60.41 | 57.89 |

  - — [EmbeddingGemma 2 model card](https://huggingface.co/google/embeddinggemma-2)
  - English v2 reportedly dropped from 69.67 in v1 to 68.46 in v2. — [eesel.ai](https://www.eesel.ai/de/blog/embeddinggemma-2-erklaert)
- No independent evaluator results exist yet, and the prompt and task details behind the scores are unpublished. — [gradually.ai](https://www.gradually.ai/en/ai-models/embeddinggemma-2/)
- Memory: about 191 MB of RAM minimum with text-only weights, per Google as reported by the press. — [GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/); [livedoor/GIGAZINE JP](https://news.livedoor.com/article/detail/32509507/)
  - Google's docs page states the under-200 MB figure only for v1. — [Google AI docs](https://ai.google.dev/gemma/docs/embeddinggemma)
- The model card warns: use bf16 or fp32, because fp16 can produce NaN or silently degraded embeddings. — [EmbeddingGemma 2 model card](https://huggingface.co/google/embeddinggemma-2)
- all-MiniLM-L6-v2:
  - 22.7M parameters and 384 dimensions.
  - Trained at 128 tokens; 256 word-pieces usable.
  - English-focused, Apache 2.0.
  - MTEB average about 56, with the MTEB version unspecified; marked "likely" from an aggregator.
  - About 14,000 sentences per second on GPU.
  - — [TokenMix](https://tokenmix.ai/blog/all-minilm-l6-v2-free-local-embedding-guide-2026)
  - It trails bge-small and gte-small by about 5–6 MTEB points. — [search summary, TokenMix](https://tokenmix.ai/blog/all-minilm-l6-v2-free-local-embedding-guide-2026)

### Inferences
- The roughly 56 versus 68.46 gap is **not directly comparable** (MTEB English v1 against v2). The quality advantage of EmbeddingGemma 2 is nevertheless large, especially for multilingual and code text and for long documents (8K versus 256 tokens). For short English meeting chunks, MiniLM is far cheaper and probably "good enough".

### Gaps
- No verified MTEB(eng, v2) score for all-MiniLM-L6-v2 was found.
- No measured EmbeddingGemma 2 latency on Apple Silicon was found.

## Comparisons with other local meeting tools

### Takeaway
Reviewers and the press mainly position Foresight against Granola, which has the same split-screen layout but is cloud-based. The only detailed comparisons come from competitors (talat, Recall). I found no head-to-head reviews against MacWhisper, Meetily or Hyprnote.

### Cited Findings
- TechCrunch frames Foresight as a "local-first Granola competitor" with a similar split-screen shorthand and AI-notes design. It also names Wispr, Calendly and Superhuman/Fathom as recent market entrants. — [TechCrunch](https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/)
- talat compared with Foresight (by talat's own author, so biased):

  | | talat | Foresight |
  |---|---|---|
  | Download / installed size | 15 MB / 29 MB | 153 MB / 376 MB |
  | Setup time | ~3:40 | ~8.5 min |
  | Languages | 33 (vendor claim) | English only |
  | Speaker ID | Yes | No |
  | Echo removal | Yes | No |
  | Auto-record | Yes | No (manual start) |
  | Dictation | Yes | No |
  | File import | Yes | No |
  | Model choice | Swappable LLMs (Ollama, BYO key, Claude Code, Codex) | Gemma only |

  — [talat](https://talat.app/blog/google-ai-edge-foresight)
- Recall compared with Foresight: Recall saved PDFs, the YouTube video and the article, and its chat answered from them. Foresight failed on YouTube and the web article. This is by Recall's own author. — [Recall](https://www.recall.it/post/google-ai-edge-foresight-vs-a-second-brain)
- An open-source clone (Open Foresight) recreates the concept with Gemma, **Whisper**, RAG and MCP on Linux and macOS. — [open-foresight (GitHub)](https://github.com/teng-lin/open-foresight)

### Inferences
- Reviewers' main criticisms map directly onto areas where a faster-whisper + Qwen + MiniLM stack can differentiate: English-only transcription, no speaker labels, no auto-start, no audio-file import, opaque telemetry and closed source. Foresight's advantages are stronger generation and embedding models, and polish from Google's ODML stack.

### Gaps
- No reviewer comparison of Foresight with MacWhisper, Meetily or Hyprnote was found.
- No independent accuracy benchmark between the tools exists yet.
