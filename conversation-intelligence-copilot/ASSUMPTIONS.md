# Assumptions and analytical decisions

Every analytical judgement the copilot makes is listed here, with the reason and where it lives in code. If you change one, the evaluation (`make evaluate`) and tests (`make test`) show the consequences.

## A. Dataset interpretation

| # | Assumption | Evidence / reason | Code |
|---|---|---|---|
| A1 | The supplied `cs_conversations.csv.zip` (Syncora.ai sample, 3,000 conversations, 41,965 messages) is the only original source. | Assignment brief; SHA-256 recorded in `data/manifests/dataset_manifest.json`. | `data/ingestion.py` |
| A2 | Each message is a meaningful sentence followed by **random lowercase filler tokens** (e.g. `… Please expedite. sglcuk scvgay tnah …`). The filler is synthetic noise, not content. | All 41,965 messages end in tokens matching `[a-z ]+` after the last `.`/`!`/`?`; none are words. | `data/normalization.py::split_noise` |
| A3 | `clean_text` = text up to the last sentence terminator **only when** the remainder is pure lowercase filler. Otherwise the full text is kept. Raw `text` is never modified. | Avoids truncating real text in appended data. | same |
| A4 | Message order is `turn_index`. Timestamps are **not** monotonic within any of the 3,000 conversations (they jump backwards by up to ~4 days), so they are used only to date conversations. | Data-quality check `timestamps_not_in_turn_order` = 3000/3000. | `data/validation.py` |
| A5 | A conversation's date is its **earliest** timestamp. | Turn-0 timestamps are not reliably earliest (A4). | `data/pipeline.py` |
| A6 | Conversations contain one agent ID each. There are 2,987 distinct agent IDs for 3,000 conversations (2,974 agents with one conversation, 13 with two). | Data profile. Consequence: no reliable per-agent ranking (see C3). | profile |
| A7 | `customer_name` / `agent_name` are pseudonymous handles. Customer handles are replaced by salted hashes; agent handles are kept as agent IDs because coaching analysis needs them. | Data minimisation. | `governance/pii.py` |

## B. Labels (topic, sentiment, empathy)

| # | Assumption | Reason | Code |
|---|---|---|---|
| B1 | The **primary topic** of a conversation is the issue in the customer's opening message. Nine opening templates map to eight topics; the English and Hinglish "help request" templates both map to *General help request*, which therefore has ~2× the volume of other topics. | Only the opening message carries issue content; later customer turns are generic (urgency, thanks…). | `labeling/taxonomy.py` |
| B2 | Product (51 values) is the noun phrase in the opening template; **domain** is inferred from the product name (Telecom, E-commerce, Financial services, Travel, Healthcare, Education, SaaS). *Billing, Subscription, Membership* are ambiguous and assigned to one domain. "Login / account locked" names no product → domain *Unknown*. | No domain field in the data. | `PRODUCT_DOMAINS` |
| B3 | Message sentiment scores: escalation request −1.0; urgency (EN and Hinglish) −0.6; waiting 0; "works now" +1.0; thanks +0.8; opening fault report −0.6; plain help request 0. Agent messages are neutral for customer sentiment. | Ordinal judgement of the 18 recurring phrases. **Developer-assigned, not independently validated** — see EVALUATION.md §3 and the in-app blind human review. | `FOLLOWUP_ACTS` |
| B4 | Conversation sentiment from customer turns: mean ≤ −0.25 → negative; ≥ 0.25 → positive; otherwise *mixed* if both positive and negative turns occur, else neutral. | Transparent and reproducible; thresholds are configurable constants. | `labeling/rules.py` |
| B5 | Empathy = an agent turn that acknowledges frustration or apologises ("I understand this is frustrating…", "I'm sorry about the trouble…"). It measures observable acknowledgement, not feelings or psychological constructs. | Observable behaviour only. | taxonomy |
| B6 | Resolution fit uses this mapping (escalation is always acceptable; general help is not assessable): duplicate charge → refund; paid-not-delivered → service activated / refund; coupon → coupon applied; not received → out for delivery / refund; app crash & feature not working → service activated / account reset; account locked → account reset. | Domain judgement; documented so it can be challenged. | `RELEVANT_RESOLUTIONS` |
| B7 | Text that matches no template gets a **lexicon** label with confidence 0.4 and status *provisional*. In the original data this never happens (100% template coverage); it applies to appended or synthetic data. | Never silently treat unknown text as known. | `rules._lexicon_label` |
| B8 | Gemini labels, when produced (`make label`), replace rule labels only where they exist; coverage by method is recorded and shown. | Partial coverage is never presented as complete. | `data/pipeline.py` |

## C. Analytical definitions

| # | Decision | Reason |
|---|---|---|
| C1 | **"Last month represented in the dataset"** = latest calendar month in which conversations start. That month is treated as partial (and the previous month used) only if the data stops before its last day **and** it has under 50% of the median monthly volume. For this dataset: November 2025 (682 conversations; data continues to 2 Dec 2025). The real-world current month is never used. | Assignment wording; avoids dropping a month for one missing day while catching true stubs (e.g. a 48-conversation December if dated by any message). |
| C2 | Topic rankings **count conversations** (one primary topic each). Default ranking is by number of negative conversations; negative *rate* (with 95% Wilson interval) is always shown alongside, and the answer says when the two orderings differ. A chi-square test reports whether rates differ beyond chance (November: p = 0.057, i.e. not significant at 5%). | "Most associated" is ambiguous between count and rate. |
| C3 | Coaching: an agent is ranked only with ≥ `MIN_AGENT_CONVERSATIONS` (default 3). No agent qualifies in this dataset, so the answer ranks **conversations** for review and reports workforce-wide patterns. `review_score = 100 × mean(missed-empathy rate after negative customer turns, resolution-misfit flag)`. | Ranking people on one transcript would be unfair and statistically meaningless. |
| C4 | Trajectory turning point = change of ≥ 0.8 in score between consecutive customer messages; the preceding agent message is shown as context, not as a cause. | Simple, explainable. |
| C5 | Leadership priority = Σ wᵢ · minmax(signalᵢ) × 100 with weights volume 0.30, negative rate 0.25, escalation requests per conversation 0.15, ends-unresolved rate 0.15, resolution-misfit rate 0.10, month-on-month change 0.05. A sensitivity analysis (equal weights, each weight ×0.5 and ×1.5: 13 scenarios) reports rank stability. The recommended action for a concern follows the signal on which it stands out most. | Transparent and configurable; no hidden weights. Financial impact, churn, handle time and repeat contact are absent from the data and never estimated. |
| C6 | "Ends unresolved" = the last customer message is negative. "Confirmed fixed" = the customer says it works now. Neither is a ground-truth resolution status. | The dataset has no resolution field. |

## D. Retrieval and memory

| # | Decision | Reason |
|---|---|---|
| D1 | Chunks are windows of 4 turns with 2 turns of overlap, never splitting a message, each prefixed with the opening complaint. | Keeps a complaint and the reply to it together and every chunk interpretable. |
| D2 | `sentence-transformers/all-MiniLM-L6-v2` is preferred; when it cannot be loaded (in the build environment Hugging Face was blocked by network policy), a local TF-IDF + SVD (LSA, 192 dims) embedder is used and the fallback reason is recorded in the index manifest and shown in the UI. | Honest fallback rather than failure. |
| D3 | One passage per conversation in results; cosine similarity is a ranking signal, not confidence. | Avoid duplicate evidence. |
| D4 | Follow-ups resolve against deterministic references stored in session memory (ranked keys, conversation IDs, scope), re-validated against the database. If the latest turn produced no ranking, references use the most recent ranking in the session and the answer says so. Earlier model prose is never treated as evidence. | Prevents compounding errors. |

## E. Synthetic data

`scripts/generate_synthetic.py` writes 120 clearly-labelled conversations (`S…` IDs, `dataset_source = synthetic_demo`) with non-template phrasing. Purpose: exercise synthetic/combined modes and the lexicon fallback. They are excluded from the default (original) mode, from the evaluation, and from every reported finding. Modes other than *original* are disabled unless `ENABLE_SYNTHETIC_DEMO=true`.
