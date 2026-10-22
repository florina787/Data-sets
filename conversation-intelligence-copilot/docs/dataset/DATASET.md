# Dataset: preparation, profile and data dictionary

## Source

* **Customer Support Conversation Dataset — Syncora.ai (Kaggle)**, sample supplied with the assignment: `data/raw/cs_conversations.csv.zip`
  (`cs_conversations.csv` + a macOS resource fork, ignored). SHA-256 `53ff0645…c51628` (full hash in `data/manifests/dataset_manifest.json`).
* Optional: `data/synthetic/synthetic_conversations.csv` — 120 generated demo conversations, tagged and excluded by default (ASSUMPTIONS.md §E).

## Preparation steps (`make prepare` → `backend/scripts/prepare_dataset.py`)

1. **Discover** the archive members, detect encoding (UTF-8) and delimiter (`,`), map columns to the canonical schema via an explicit alias table (`conv_id→conversation_id`, `role→speaker_role`, …). Missing required columns are a hard error.
2. **Normalise**: parse timestamps, normalise roles, split the synthetic filler off each message into `clean_text` (raw kept), mask PII, pseudonymise customers, create stable IDs (`C0000006-T03`) and source references (`cs_conversations.csv:line 5`).
3. **Validate**: 17 data-quality checks → `data/manifests/data_quality_report.json`.
4. **Label**: deterministic, versioned labeller (`tax-1.0` / `rules-1.0`); optional Gemini labels (`make label`, then `LABEL_SOURCE=gemini make prepare`).
5. **Aggregate** conversation-level fields (topic, product, domain, sentiment, empathy signals, resolution fit, …).
6. **Write** `data/processed/analytics.duckdb` atomically (build to a temp file, then rename) plus manifests.
7. **Index** (`make index`): conversation-aware chunks → embeddings → FAISS (`data/indexes/`).

## Profile (original data)

| Measure | Value |
|---|---|
| Rows (messages) | 41,965 (customer 21,639; agent 20,326) |
| Conversations | 3,000 (10–18 messages, median 14) |
| Distinct agent IDs | 2,987 — 2,974 handle one conversation, 13 handle two |
| Customers | 3,000 (one per conversation) |
| Timestamp range | 1 Aug 2025 10:00 – 2 Dec 2025 10:49 |
| Conversations by start month | Aug 788 · Sep 750 · Oct 780 · Nov 682 |
| Unique cleaned message texts | 426 |
| Opening language | English 2,343 · Hinglish 657 |

### Data-quality findings

| Check | Result |
|---|---|
| Duplicates (rows, turn indexes, conversations), missing values, empty text, unknown roles, turn gaps | none |
| Timestamps decreasing while `turn_index` increases | **3,000 / 3,000 conversations** → turn order treated as authoritative |
| Synthetic filler tokens | 41,965 / 41,965 messages (removed in `clean_text`) |
| PII patterns (email, phone, card, UPI ID, account no., IP) | 0 hits |

### What the data can and cannot support

* Topic (from the opening message), product, inferred domain, language, sentiment trajectory, empathy acknowledgement, resolution fit, escalation/urgency signals: **supported**.
* Per-agent comparison: **not reliable** (≤ 2 conversations per agent).
* Resolution status, CSAT, handle time, revenue, churn, repeat contact: **not in the data**.
* Beyond the opening message, customer and agent turns are drawn from a small phrase pool and the agent's closing action is unrelated to the issue in most conversations (57.3% misfit where assessable) — a property of the generator that the copilot reports rather than hides.

## Data dictionary (DuckDB `analytics.duckdb`)

### `messages`
| Column | Meaning |
|---|---|
| message_id | `<conversation_id>-T<turn>` |
| conversation_id, turn_index | source IDs; turn order is authoritative |
| timestamp | parsed source timestamp (not monotonic) |
| speaker_role | customer / agent / unknown |
| text | raw source text (unchanged) |
| clean_text | text without trailing filler |
| masked_text | clean_text with PII masked (used everywhere downstream) |
| noise_token_count, pii_hits | counts |
| customer_id | salted hash of the customer handle |
| agent_id | source agent handle |
| dataset_source | `original` / `synthetic_demo` |
| source_reference | `file:line` of the source row |

### `message_labels`
act, sentiment, sentiment_score (−1…1), empathy, courtesy, resolution, language, topic/product (opening only), method (`template` / `lexicon` / `gemini`), confidence, labeler, model_name, prompt_version, taxonomy_version, labeled_at, validation_status.

### `conversations`
start/end timestamp, month, agent_id, message/turn counts, topic, topic_label, product, domain, opening_language, sentiment, sentiment_score_mean, first_followup_score, last_customer_score, negative/positive turns, negative_share, escalation_requests, urgency_signals, confirmed_fixed, empathy_turns, empathy_rate, negative_turns_with_reply, empathic_replies, empathy_response_rate, repeated_agent_phrases, final_resolution, resolution_relevant, ends_negative, timestamps_monotonic, label_methods, min_label_confidence, label_version, processing_status, dataset_source, source_record_id.

### `topics`, `build_metadata`
Topic catalogue; pipeline/taxonomy/labeller versions, build time, sources and label coverage.
