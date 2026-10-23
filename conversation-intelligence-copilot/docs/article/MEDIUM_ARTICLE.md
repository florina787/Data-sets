# No LLM Required: How I Built an AI Copilot That Still Gives the Right Answer With the Model Switched Off

*An AI engineer's notes on building a contact-centre analytics copilot: the rule that shaped it, the router that decides when a model is worth calling, and ten problems that nearly sank it.*

**Code:** [github.com/florina787/Data-sets → conversation-intelligence-copilot](https://github.com/florina787/Data-sets/tree/claude/happy-edison-gef7ay/conversation-intelligence-copilot)

![The copilot answering a question: KPIs, charts, cited conversations and an evidence review, with zero model calls](https://raw.githubusercontent.com/florina787/Data-sets/claude/happy-edison-gef7ay/conversation-intelligence-copilot/docs/readme/demo.gif)

---

A contact-centre analyst asks a simple question: *which topics drove negative sentiment last month?*

The tempting build is to give the transcripts to a large language model and print whatever comes back. It reads well. It might also be wrong, in ways nobody notices until a leadership deck goes out with a number that never existed.

I have shipped enough analytics to distrust that build. A wrong number in a dashboard is worse than no dashboard, because people act on it. So I built the opposite.

The **Conversation Intelligence Copilot** is an agentic analytics assistant for customer-support conversations. A LangGraph workflow:
* plans the analysis;
* runs registered DuckDB queries over 3,000 conversations (41,965 messages);
* retrieves the transcripts behind each finding;
* explains the result;
* audits its own answer before anyone sees it.

A language model is optional. The four questions the project was built around are answered with **zero model calls**, in a median of **125 ms** on a laptop CPU.

| What | Result |
|---|---|
| Assignment questions answered and independently re-computed | 4 / 4 |
| Intent routing, 73 held-out questions, scored once | 95.9% |
| Median answer time, deterministic path | 125 ms (p95 540 ms) |
| Cost to run, model included | $0 |

## The rule that shaped everything

Before writing any code, I wrote one rule and let it settle every later trade-off:

> **Numbers are computed, never generated.**

I wrote it down because I knew I would be tempted later. At some point a model would "almost" get a count right, and it would be so much faster to let it.

* **Every figure is computed.** Every count, rate and rank comes from one of 15 registered, parameterised DuckDB operations.
* **The model never writes SQL.**
* **Explanations are checked.** If an explanation contains a figure that is not in the verified result, it is thrown away and a deterministic explanation is used instead.

![Verification: an explanation is only shown if every number in it exists in the verified result, then the Evidence Challenger checks it](https://raw.githubusercontent.com/florina787/Data-sets/claude/happy-edison-gef7ay/conversation-intelligence-copilot/docs/article/img/flow-verify.png)

Once that rule existed, a harder question followed: if the model cannot contribute facts, when is it worth calling at all? I spent more time on that question than on any single feature.

## The system at a glance

![System overview: React UI, FastAPI, a LangGraph workflow, DuckDB, FAISS, SQLite, and an optional local model](https://raw.githubusercontent.com/florina787/Data-sets/claude/happy-edison-gef7ay/conversation-intelligence-copilot/docs/article/img/flow-overview.png)

| Layer | Choice |
|---|---|
| Orchestration | LangGraph, with a SQLite checkpointer |
| Analytics | DuckDB, pandas and SciPy: exact and deterministic, with Wilson intervals and χ² tests |
| Retrieval | FAISS, with MiniLM sentence embeddings and LSA, fused by reciprocal rank fusion |
| Memory and telemetry | SQLite |
| API / UI | FastAPI with Server-Sent Events; React 18 with TypeScript, Recharts and React Flow |
| Optional model | Qwen2.5-1.5B-Instruct, run locally with llama.cpp on CPU. No API key. |

The workflow runs in four stages. Every box is a real LangGraph node: the UI lights each one up live as it runs, and a **Decision Replay** panel lets you step back through them afterwards.

![The agent graph in four stages: understand, plan and compute, explain and verify, deliver and remember](https://raw.githubusercontent.com/florina787/Data-sets/claude/happy-edison-gef7ay/conversation-intelligence-copilot/docs/article/img/flow-stages.png)

Three choices in this graph matter more than the rest.

1. **The supervisor plans; it does not compute.** It resolves the time window and any references to earlier answers, then chooses registered operations. The analytics layer accepts nothing else.
2. **Retrieval runs in parallel, and only illustrates.** Hybrid search finds real transcripts for the top-ranked result. It never produces a number.
3. **Verification is a stage, not an afterthought.** A QA agent and an Evidence Challenger run on every answer.

## The Zero-LLM router

Before any model is involved, a cascade of cheap, high-precision checks decides what the question is, and whether a model would add anything.

![The routing cascade: policy check, high-precision rules, semantic match, vagueness guard, local model, clarify](https://raw.githubusercontent.com/florina787/Data-sets/claude/happy-edison-gef7ay/conversation-intelligence-copilot/docs/article/img/flow-router.png)

* **Fact questions stop at the rules.** Most analytical questions stop at the second step: a rule recognises the intent, the registered operations compute the full answer, and a model would only add cost and latency.
* **The model is called in two situations:** when no rule can route the question with high precision, or when the question asks for interpretation (*why*, *explain*, *recommend*). Even then it only picks a category from a closed list, or phrases an explanation of numbers that were already computed.
* **Policy checks run first and always win.** Questions that need data the dataset doesn't have (revenue, CSAT, handle time), or that ask for a personnel decision, are refused deterministically. No model is needed to say no.

Some examples of how questions are routed:

| Question | Route | Model calls |
|---|---|---|
| What were the top 5 topics associated with negative sentiment last month? | Analytics only | 0 |
| Why is duplicate charge so negative? | Hybrid: DuckDB computes, the model explains | 1 |
| How much revenue did we lose to coupon issues? | Refused (the data has no revenue) | 0 |
| Anything interesting? | Ask to clarify | 0 |

## Question one, answered

The first question asks for the top 5 topics associated with negative sentiment *in the last month*. "Last month" was the first trap. The data spans August to early December 2025, so the last month means the latest month in the data, not today's calendar month.

In November 2025, **240 of 682** conversations were negative.

![Negative conversations by topic in November 2025, top 5 highlighted, with the tie at rank 5](https://raw.githubusercontent.com/florina787/Data-sets/claude/happy-edison-gef7ay/conversation-intelligence-copilot/docs/readme/q1-negative-topics-light.png)

| Rank | Topic | Negative | Of | Rate |
|:-:|---|--:|--:|--:|
| 1 | General help request | 49 | 156 | 31.4% |
| 2 | Duplicate charge | 42 | 87 | 48.3% |
| 3 | Paid but service not delivered | 30 | 75 | 40.0% |
| 4 | Feature not working | 28 | 76 | 36.8% |
| 5 | Login / account locked | 24 | 58 | 41.4% |

* **By count, General help request leads**, because it has twice the volume of any other topic.
* **By rate, Duplicate charge leads.**
* **The differences are not significant.** The confidence intervals overlap heavily, and a χ² test across topics gives p = 0.07.
* **Rank 5 is a tie** with Coupon not applying (also 24).

A careful analyst would say all of that out loud, so the copilot does.

## The challenges

None of these were in the brief. They are the problems that took the time, roughly in the order I hit them.

### 1. A mean of exactly −0.25, according to a computer

A conversation counts as negative when the mean sentiment of its customer turns is −0.25 or lower. Conversation C0010797 has eight customer turns:

```
−0.6, −0.6, −0.6, −0.6, +0.8, −0.6, +0.8, −0.6
```

On paper the mean is exactly −0.25. In floating point, summed left to right, it is not:

```js
let sum = 0;
for (const s of [-0.6, -0.6, -0.6, -0.6, 0.8, -0.6, 0.8, -0.6]) sum += s;
sum / 8;            // -0.24999999999999994
sum / 8 <= -0.25;   // false: labelled "not negative"
```

I found it because one score in my own audit was off by 0.5, and I refused to explain it away.

* **The fix** rounds the mean to 9 decimals before the comparison.
* **It changed real answers.** A leadership priority score moved from 52.9 to 53.4, and the November negative count went from 239 to 240.
* **My checker had the same bug.** I had written an independent checker for the audit, to recompute answers from the raw CSV. It averaged with floats too, so it agreed with the bug. The evaluation oracle now uses exact fractions (`Fraction(str(score))`), and a regression test pins this exact score pattern.

**Lesson:** check the checker. Two implementations that share an assumption are one implementation.

### 2. Timestamps that are not in turn order

In all 3,000 conversations, message timestamps don't follow the turn order. Sort by time and a conversation reads as nonsense: answers before questions, thanks before help.

The turn index is authoritative. Each conversation is dated by its earliest message, and every sentiment-trajectory answer says that timestamps were not used for ordering.

### 3. One agent per conversation makes coaching rankings unfair

Question two asks which agents may benefit from coaching. The data holds **2,987 agent IDs for 3,000 conversations**, with at most two conversations each. Any ranking of individual agents would rest on one or two transcripts.

I would rather tell a team lead "the data cannot support this" than hand them a ranking that could cost someone their job on the strength of two chats. So the copilot says so, and answers the useful version of the question instead:
* **Workforce-level patterns.** Only **29.3%** of negative customer turns got an acknowledgement or apology, and **57.3%** of assessable closing actions didn't fit the issue.
* **A review queue of conversations**, each with its evidence.
* **Human review required.** Every coaching answer is flagged for it, and requests for personnel decisions are refused.

### 4. 41,965 messages, 426 unique texts

The dataset is synthetic. Every message ends with random filler tokens, and once those are stripped there are only **426** distinct message templates.

That sounded like a problem; it was an opportunity. I labelled the 426 templates with a documented rule set instead of labelling 41,965 messages with a model. The trade-off is explicit: the labels are my judgement. The app includes a review panel for collecting human labels, and the evaluation says plainly that agreement with humans has not been measured yet.

### 5. The hosted model key was blocked

My plan included a hosted model. The key I had during development returned `401 API_KEY_SERVICE_BLOCKED`.

This became the most useful constraint of the project, because it forced the question: what does the product actually *need* a model for? I made the model optional everywhere and added a free local one, Qwen2.5-1.5B-Instruct (Q4_K_M, about 1.1 GB), through llama.cpp on CPU.
* **Warm calls:** a routing call takes about a second.
* **Cold start:** the first call after start-up measured 8.7 s on an idle CPU, and 30 to 55 s when other jobs competed for it.

### 6. A small model routing questions: 19% accurate

My first prompt asked the 1.5B model to classify questions into intents. On a frozen held-out test set, it scored **19.2%**. Rewriting the prompt around a closed category list, enforced by a JSON-schema grammar, took it to **58.9%**.

I could have kept tuning prompts. I decided against it. A 1.5B model was never going to be reliable on the long tail, and every prompt tweak was a guess I could not verify without spending the test set.

The fix was to stop asking the model to do the whole job. The confidence cascade lets each stage answer only when it is sure.

![Intent routing accuracy on 73 held-out questions, from 19.2% (local model, first prompt) to 95.9% (confidence router with the local model)](https://raw.githubusercontent.com/florina787/Data-sets/claude/happy-edison-gef7ay/conversation-intelligence-copilot/docs/readme/routing-accuracy-light.png)

| Method (73 held-out questions, scored once) | Accuracy |
|---|--:|
| Local Qwen, first prompt | 19.2% |
| Local Qwen, closed-list prompt | 58.9% |
| Previous router (rules first) | 61.6% |
| Confidence router, no model | 90.4% |
| **Confidence router + local Qwen** | **95.9%** |

Two details I am proud of:
* **The semantic stage turned itself off.** The semantic-similarity stage was built and calibrated, and then disabled by its own calibration: no threshold reached 95% precision on validation.
* **The model is rarely needed.** It is now called for only 6.9% of test questions.

### 7. The Evidence Challenger corrected my own sentence

The Evidence Challenger is an adversarial check that runs after the explanation is written. It:
* re-reads every quoted excerpt from the database, word for word;
* discloses samples under 30;
* states counter-evidence ("61% of Item-not-received conversations were not negative");
* rewrites causal wording as association.

When I added the tie disclosure to question one, I wrote that a topic was listed last *because of* the tie-breaker. The Challenger rewrote "because of" as "associated with" and mangled the sentence. It was doing its job; my wording was the problem.

Building it also exposed two real bugs:
* QA had been reporting "0 evidence items resolved", because the explanation node overwrote the evidence report.
* A repeated-phrase detector always returned zero.

### 8. Demo data leaking into the real answers

For UI demos I generated 120 tagged synthetic conversations. They were loaded by default, so the dashboard showed 3,120 conversations for an assignment that supplied 3,000.

* **The fix:** demo data is now opt-in.
* **A side effect:** removing it changed the lexical index's vocabulary, which moved the retrieval scores. The evaluation reports the new numbers and explains why they changed, rather than keeping the old, slightly better ones.

### 9. Retrieval that is honest about a small gain

Retrieval indexes 18,639 four-turn chunks twice: once with MiniLM embeddings and once with LSA. The two rankings are fused with weighted reciprocal rank fusion.

![Retrieval quality by method: LSA, MiniLM and hybrid](https://raw.githubusercontent.com/florina787/Data-sets/claude/happy-edison-gef7ay/conversation-intelligence-copilot/docs/readme/retrieval-methods-light.png)

| 36 paraphrased queries | LSA | MiniLM | Hybrid |
|---|--:|--:|--:|
| Topic precision@5 | 28.9% | 62.2% | **62.8%** |
| Hit rate@5 | 41.7% | 83.3% | **86.1%** |

The hybrid wins, but only by a little, and the fusion weight was tuned on these same queries. The evaluation says both things. A small honest gain is more useful to a reviewer than a large flattering one.

### 10. Token counts that don't lie

Every answer shows its route, how the intent was resolved, and the tokens used. Getting the token count right took more care than I expected:
* tokens show as "0 (no model call)" only when no model was called;
* when a provider returns no usage data, the UI says *not reported*, never a fake zero;
* streaming usage is taken as the cumulative maximum, not summed across chunks, which had been double counting.

## What it doesn't do

These are the questions a reviewer should ask.

* **It doesn't claim cause.** The Root Cause Investigator reports tested associations with intervals and separates symptoms from candidate drivers.
* **It doesn't rank people on thin data.**
* **It hasn't been validated against human labels.** The routing benchmark is 73 questions, written by the same person who wrote the rules. The 95.9% is indicative, and the remaining misroutes are listed in the repository.
* **It isn't production-hardened.** There is no authentication or role-based access, and storage is single-node.

## What I would keep

If I started again tomorrow, I would keep three habits.

1. **Write the rule before the code.** "Numbers are computed, never generated" settled dozens of decisions in advance.
2. **Make the model earn its call.** A router that can say "no model needed" made the system faster, cheaper and easier to test. It also made the model's real contribution measurable: 90.4% without it, 95.9% with it.
3. **Check the checker.** The float bug survived an independent recomputation because both used the same arithmetic. Using exact fractions in the oracle cost one import.

## Run it yourself

No API key and no hosted model. You need Python 3.12+ with `uv`, Node 22+ and `make`:

```bash
git clone https://github.com/florina787/Data-sets.git
cd Data-sets/conversation-intelligence-copilot
git checkout claude/happy-edison-gef7ay
cp .env.example .env
make install && make prepare && make index
make dev          # UI on http://localhost:5173
```

* **Optional local model:** `make install-local-llm && make llm-download`.
* **VS Code:** open the folder and press F5 on the *Full stack* launch configuration.

**The code, the evaluation and every number in this article are in the repository:**
👉 [github.com/florina787/Data-sets/tree/claude/happy-edison-gef7ay/conversation-intelligence-copilot](https://github.com/florina787/Data-sets/tree/claude/happy-edison-gef7ay/conversation-intelligence-copilot)

---

*Tags: Artificial Intelligence, LLM, LangGraph, Data Engineering, Customer Experience*
