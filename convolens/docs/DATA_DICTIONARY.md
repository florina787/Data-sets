# Data dictionary

## Source: Kaggle `twcs.csv` (validated on import)

| Column | Type in ConvoLens | Notes |
|---|---|---|
| `tweet_id` | string | Never float-coerced. `123.0` is normalised to `123`. Invalid IDs reject the row. |
| `author_id` | string | Brand handle for support accounts; anonymised numeric ID for customers. Customers are re-pseudonymised as `cust_<hash>`. |
| `inbound` | boolean | Accepts only true/false/1/0/yes/no/t/f. Other values reject the row. `True` = customer, `False` = support. |
| `created_at` | UTC timestamp | Twitter format (`Tue Oct 31 22:10:47 +0000 2017`) or ISO. Invalid values are kept as null and counted. |
| `text` | string | **Redacted before storage.** The raw text is never persisted. |
| `response_tweet_id` | list of IDs | Cross-checked against `in_response_to_tweet_id`; references to absent messages mark a thread `partial`. |
| `in_response_to_tweet_id` | string | The authoritative parent link that builds the reply graph. |

## Unit of analysis

A **conversation** is one reply tree, rooted at a message whose parent is absent. Each message belongs to exactly one conversation.

## Tables (`var/convolens.db`)

| Table | Purpose / key fields |
|---|---|
| `datasets` | `id` (from file hash + parameters), `kind` (`demo`, `synthetic_multilingual`, `kaggle_twcs`), `synthetic`, `status`, `manifest` (JSON), `active_analysis` |
| `import_jobs` | Background jobs: `kind`, `status` (queued/running/completed/failed/cancelled/interrupted), `stage`, `progress`, `params`, `error` |
| `conversations` | `key` (stable `cv_` + sha256(source kind, root ID)), `root_source_id`, `brand`, counts (`message_count`, `customer_turns`, `support_turns`), `branch_count`, `max_depth`, `completeness`, `started_at`/`ended_at`, `first_response_s`, `content_hash`, `languages`, the **effective labels**, `analysis_id`, `corrected` |
| `messages` | `source_id`, `parent_source_id`, `role`, `author_ref`, `created_at`, `position`, `depth`, `child_count`, redacted `text`, `redactions`, `language`, `language_confidence`, `language_detail`, `language_corrected`, `stage` |
| `exclusions` | Every non-selected thread: `root_source_id`, `reason`, `message_count` |
| `analyses` | **Original predictions** (never overwritten): `method` (rules/llm), `model_id`, `prompt_version`, `content_hash`, `source_text` (original/translated), `fields`, `status`, `error`. Unique per cache key. |
| `corrections` | Reviewer corrections and confirmations: `target_type`, `field`, `original_value`, `corrected_value`, `reviewer`, `note` |
| `translations` | `method` (llm/reference), `model_id`, `prompt_version`, `checks`, `needs_review`. Stored separately from the original text. |
| `chat_sessions` | Flo session ID and hashed token |
| `runs` | One Flo graph run: question, type, mode, status, visited nodes, tool calls, evidence IDs, response, model, prompt versions, tokens, latency, LangSmith run ID, error |
| `feedback` | Score, comment or correction, and whether it was sent to LangSmith |
| `investigations` | Saved Flo answers (scoped to a session) |
| `actions` / `action_events` | Action records with a unique `idempotency_key`, owner and `owner_confirmed`, `due_date`, intended outcome, success measure, `status` (proposed/approved/in_progress/completed/rejected), brief, investigation link, approval history |
| `opportunity_reviews` | Reviewer-entered effort (1–5), effort source, severity override |
| `eval_runs` | `suite`, `judgment` (deterministic/human/llm_judge), `system`, `language`, `n`, `passed`, `score`, `details`, LangSmith experiment |
| `impact_reviews` | Intervention date, parameters, result, reviewer |

## Label vocabularies

| Field | Values |
|---|---|
| `primary_topic` / `secondary_topics` | `billing_refunds`, `orders_delivery`, `account_access`, `app_technical`, `network_connectivity`, `travel_disruption`, `cancellation`, `service_experience`, `other` (covered language, no keyword match), `unknown` (language not covered) |
| `resolution_status` | `resolved_confirmed` (customer confirms), `unresolved_explicit` (customer says it is not resolved), `solution_offered_unconfirmed`, `unknown` |
| `sentiment_start` / `sentiment_end` | `negative`, `neutral`, `positive`, `unknown`. Inferred from the first and last customer turn. Not a satisfaction score. |
| `escalation_requested` | `yes`, `no`, `unknown` |
| `customer_intent` | `request_refund`, `report_problem`, `ask_status`, `cancel_service`, `complain`, `request_help`, `unknown` |
| message `language` | ISO 639-1 code, `mixed`, `hi-Latn` (Romanized Hindi), `unknown` |
| message `stage` | `problem`, `clarification`, `support_action`, `follow_up`, `escalation`, `outcome` (inferred by rules) |
| claim `kind` | `observed`, `inference`, `hypothesis`, `recommendation` |

## Evidence identifiers

The format is `<conversation_key>/<message source id>[#start-end]`. An identifier resolves only within its own dataset, and a span must fall inside the stored redacted text.

## Import manifest fields

The manifest records:

- `source`, `source_kind`, `synthetic`, `file_name`, `file_bytes`, `file_hash_sha256`, `schema`,
- `parser_version`, `redactor_version`, `language_detector`, `analysis`, `unit_of_analysis`,
- `sampling` (seed, method, requested, eligible, selected, not sampled, coverage, eligibility rules),
- `counts`, `exclusions`, `completeness`, `branching` (selected and eligible), `languages`, `redactions`,
- `import_started_at`, `import_completed_at`.
