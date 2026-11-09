# Real-model evaluation

Every result here comes from **real local models through VEENA's real API**, with real MiniLM embeddings, real Tesseract, and VEENA's real retrieval, governance and semantic-spine code. Nothing is simulated.

**Machine:** cloud VM, 4 vCPU, 15.7 GiB RAM, **no GPU**. Ollama's log confirms `library=cpu`; its "CPU/GPU" split display is a quirk. Ollama 0.40.11. Results on GPUs or Apple Silicon were **not measured**.

Reproduce:
- `python -m tests.performance.model_eval --text qwen2.5:1.5b qwen3:1.7b --vision qwen3-vl:2b-instruct`
- the offline check in `tests/performance/offline_check.py`
- the real end-to-end suite `npx playwright test` in `apps/desktop`

Raw data: [`docs/benchmarks/`](../docs/benchmarks).

## Tasks and pass rules

| Task | Pass rule (checked mechanically) |
|---|---|
| arithmetic | answer contains "42" for "12 plus 30" |
| rag_grounded | mentions HNSW and 300 ms and cites [1] from an uploaded design doc |
| rag_trap_no_invention | asked who built the project, the owner and the monthly cost (none of which the document says): no `unbacked_claims` flag |
| meeting_notes | the Friday release is a decision, and both the runbook update and the Redis check are action items |
| interview_practice | the model (not the fallback bank) generated the question, and feedback has a numeric score |
| screen_error | names the KeyError/user_id in a traceback screenshot |
| screen_code | explains code in a screenshot as a palindrome/reverse check |

## Results (run 2, clean: no other load on the machine)

| Model | Licence | arithmetic | rag_grounded | rag_trap | meeting | interview | Speed |
|---|---|---|---|---|---|---|---|
| qwen2.5:1.5b | Apache 2.0 | ✅ 3.1 s | ✅ 3.4 s | ✅ 2.2 s | ❌ 5.8 s | ✅ 12.2 s | 19–27 tok/s |
| qwen3:1.7b | Apache 2.0 | ✅ 3.4 s | ✅ 3.8 s | ✅ 1.9 s | ❌ 13.5 s | ✅ 23.0 s | 17–26 tok/s |
| qwen3:4b (separate run) | Apache 2.0 | ✅ 18 s | ✅ 64 s | ✅ 197 s | ✅ 33 s | ❌ 49 s | reasoning leaked into the answer text despite thinking being disabled |

| Vision model | Licence | screen_error | screen_code |
|---|---|---|---|
| qwen2.5vl:3b (old default) | **research only** | ✅ 17.6 s | ✅ 15.8 s |
| **qwen3-vl:2b-instruct (new default)** | Apache 2.0 | ✅ 40.2 s | ✅ 33.3 s |
| granite3.2-vision:2b | Apache 2.0 | ✅ 89.3 s | ✅ 82.2 s |
| qwen3-vl:2b (Ollama default tag = thinking variant) | Apache 2.0 | ❌ empty after 406 s | ❌ empty after 339 s (run 1) |

### Invention test across runs

The trap question was asked in four real runs of qwen2.5:1.5b and two of qwen3:1.7b:

| Model | Runs | Invented names or figures | Example |
|---|---|---|---|
| qwen2.5:1.5b | 4 | **3** | "built by a team of 10 engineers at Anthropic … a subsidiary of OpenAI"; "2 engineers at Anthropic … Meta Group … $100,000 per month" |
| qwen3:1.7b | 2 | 0 | "The uploaded documents do not cover the number of engineers…" |

Every invented answer was caught by VEENA's semantic-spine check, which showed "not in its inputs: …" under the answer and raised the `unbacked_claims` flag. Small samples: this shows a tendency, not a rate.

## Decisions taken from these results

- **Vision default → qwen3-vl:2b-instruct.** It passes the screen tasks under Apache 2.0, at roughly twice the latency of the research-licensed model, and is 1.9 GB instead of 3.2 GB.
- **Balanced text → qwen3:1.7b**, which did not invent in any run. **Lite text stays qwen2.5:1.5b**, which is fastest; its invention tendency is mitigated by the visible flag.
- **qwen3:4b rejected**: too slow on CPU, and its reasoning text leaks into answers.
- **Ollama's `qwen3-vl:2b` tag must not be used**; only `-instruct`.

## Defects found by real-model testing, and fixed

| Defect | Evidence | Fix | After |
|---|---|---|---|
| Full-screen analysis ran for 5 min 20 s | Ollama log: a busy screen's OCR plus image filled the 4,096-token context; no answer length cap | OCR capped at 2,500 chars when the image goes to a vision model; every answer capped at 1,024 tokens; regression tests | 141 s in the same end-to-end test |
| Speech on short phrases transcribed as Japanese | "What is a hash map?" → katakana, detection p = 0.33 | If auto-detection confidence < 0.5, transcribe in the user's language (set from the system language in Setup); real-model regression test | "What's in a hash map?" |
| Reasoning models think before answering | Qwen3 `thinking` capability | VEENA sends `think: false` to models that report thinking | |
| Evaluation rules too lenient or wrong (my own harness) | interview checked `"llm"` instead of `"model"`; the meeting rule passed notes with an empty action list | Rules corrected before the run 2 results | |

## Known limitations (not fixed)

- **`unbacked_claims` false positives on screen explanations.** Explaining code naturally names things that are not on screen (for example "Python"), so every vision model's code explanation was flagged. On screen answers, treat the flag as a hint.
- **Meeting notes miss action items.** Both small text models put the runbook task under decisions instead of action items. The notes are a draft.
- **Full-screen analysis takes about 2.4 minutes** on this 4-vCPU CPU-only machine with the licensed 2B vision model, compared with about 1 minute for the research-only model it replaced. A GPU or Apple Silicon should be much faster, but that was **not measured**.

## Network-disconnected run

In a Linux network namespace with only loopback (internet unreachable, verified first), with models downloaded beforehand: chat 2.9 s ✅, cited document answer 6.1 s ✅, meeting notes 4.6 s ✅, interview question 3.7 s ✅, screen analysis 29.4 s ✅, speech-to-text 3.4 s ✅. Raw data: [`offline_check.json`](../docs/benchmarks/offline_check.json).

## End-to-end (real Electron app, real models)

9/9 pass ([`tests/e2e/app.spec.ts`](../tests/e2e/app.spec.ts)): renderer isolation, loopback + token, the new 7-step setup through a real first answer, streaming chat, documents with citations, refusal of capture without a user selection, real screen capture and analysis, microphone speech to answer, and deletion.
