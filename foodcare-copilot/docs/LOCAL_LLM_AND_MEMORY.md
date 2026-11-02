# Local model and persistent memory

## Using your local Qwen model

FoodCare never downloads, loads or starts a model. In LIVE mode it sends requests to **one OpenAI-compatible server that is already running on your machine**. Ollama, LM Studio, llama.cpp `llama-server` and MLX all expose this interface. Without LIVE mode configured, everything works in DEMO mode (deterministic answers).

GitHub Copilot in VS Code can use a local model through its *Manage Models* setting (for example the Ollama provider). In that case, Copilot is a client of a local server, usually Ollama on port 11434. FoodCare connects to the **same server**, so both share one loaded model instance. Copilot itself has no API that other applications can call.

1. Find the server and the model name:
   * **Ollama:** run `ollama list`. The base URL is `http://127.0.0.1:11434/v1`.
   * **LM Studio:** open the *Developer* tab and start the server. The base URL is `http://127.0.0.1:1234/v1`.
   * **llama.cpp:** start `llama-server --port 8080 …`. The base URL is `http://127.0.0.1:8080/v1`.
2. Start FoodCare with the URL and the exact model name:

   ```bash
   FOODCARE_LLM_BASE_URL=http://127.0.0.1:11434/v1 \
   FOODCARE_LLM_MODEL=qwen2.5:7b-instruct \
   scripts/start.sh
   ```

3. Tick **LIVE** in *Ask Copilot*. `GET /api/llm/status` shows whether the server is reachable and the model is listed, along with queue depth and latency.

The status check lists models (`GET /v1/models`), which loads no weights. It runs only when someone asks for it, never in the background.

### Settings

| Variable | Default | Purpose |
|---|---|---|
| `FOODCARE_LLM_BASE_URL` | unset | Local server URL, including `/v1` |
| `FOODCARE_LLM_MODEL` | unset | Model name exactly as the server lists it |
| `FOODCARE_LLM_API_KEY` | unset | Only for servers that require one; it is never passed to child processes |
| `FOODCARE_LLM_RESPONSE_FORMAT` | `json_schema` | `json_schema`, `json_object` or `none`. Use `json_object` or `none` if your server rejects schemas |
| `FOODCARE_LLM_CONCURRENCY` | `1` | Requests sent to the model at once |
| `FOODCARE_LLM_QUEUE_SIZE` | `4` | Requests allowed to wait. When the queue is full, callers get "busy" immediately and the copilot shows its deterministic answer |
| `FOODCARE_LLM_QUEUE_WAIT_S` | `20` | Maximum time a request waits in the queue |
| `FOODCARE_LLM_TIMEOUT_S` | `60` | Maximum time per request. The stream is closed when it runs out |
| `FOODCARE_LLM_MAX_TOKENS` | `800` | Maximum output tokens per answer |
| `FOODCARE_LLM_MAX_PROMPT_CHARS` | `6000` | Prompt-size cap. FoodCare never changes the server's context size (`num_ctx`) |
| `FOODCARE_LLM_CACHE_ENTRIES` | `64` | In-memory cache of answers to identical prompts |

### What the model is used for

The model only writes the prose of an answer, from facts that deterministic Python and SQL have already computed. Every number comes from a read-only query. Every citation in the model's answer must refer to a source it was given. An answer with no citations, or with invented ones, is discarded, and the deterministic answer is shown with a notice. The model receives a bounded context: the computed facts, the last few exchanges (`FOODCARE_MEMORY_CONTEXT_TURNS`, default 3) and a short summary of earlier questions. It never receives the whole conversation history.

The **Stop** button cancels a LIVE answer. The connection to the model server is closed, which ends generation on Ollama, LM Studio and llama-server.

## Persistent memory (SQLite)

`var/memory/memory.db` is a separate SQLite file in WAL mode with versioned, checksummed migrations (`backend/app/memory/schema.py`). It survives backend restarts and *Reset Demo*.

| Data | Table(s) |
|---|---|
| Conversations and messages; full-text search over questions | `conversations`, `messages`, `messages_fts` (FTS5) |
| Follow-up context (last topic and entities) and rolling summary | `conversations.context_json`, `conversations.summary` |
| Agent and tool execution history, with timings | `agent_runs`, `tool_calls` |
| Human approvals, evaluations | `human_approvals`, `evaluations` (tables ready for the Agent Harness phase) |
| Architecture questionnaires (revisioned answers) | `architecture_assessments`, `architecture_answers` (ready for the Architecture Studio phase) |
| Inspection batches (file references and metadata only, never image bytes) | `inspection_batches`, `inspection_items` |

* **Privacy:** users see, search, resume and delete only their own conversations. Another user's conversation ID returns 404.
* **Retention:** conversations not updated within `FOODCARE_MEMORY_RETENTION_DAYS` (default 180; 0 keeps them forever) are deleted at startup.
* **Backups:** an online backup through the SQLite backup API, at startup when the last backup is older than `FOODCARE_MEMORY_BACKUP_INTERVAL_H` (default 24), or on demand with `POST /api/memory/backup` (engineer or release approver). The newest `FOODCARE_MEMORY_BACKUPS_KEPT` (default 5) are kept.
* **Recovery:** at startup a failed `PRAGMA quick_check` moves the damaged file aside and restores the newest backup that passes the check.
* **Rolling summary:** after `FOODCARE_MEMORY_SUMMARY_AFTER` messages (default 20), earlier questions are condensed into an extractive summary. It is plain SQL with no model inference.
* **Scaling out:** the code uses the `MemoryStore` interface (`backend/app/memory/store.py`). A multi-replica deployment should implement it over an external transactional database such as PostgreSQL. Never share one SQLite file between Kubernetes replicas over a network filesystem.

### API

`GET /api/copilot/conversations`, `GET|DELETE /api/copilot/conversations/{id}`, `DELETE /api/copilot/conversations` (all of your own), `GET /api/copilot/search?q=`, `POST /api/copilot/cancel/{request_id}`, `GET /api/memory/status`, `POST /api/memory/backup`, `GET /api/agents/runs`, `GET /api/llm/status`.

## Measured results

All figures were measured on 2026-11-02 in a cloud container (4 vCPUs, Python 3.13), with the backend on isolated ports, in DEMO mode, using `/proc` for CPU and RSS. No real model was available there, so **no local-model latency was measured**. Measure it on your own machine with `GET /api/llm/status` after a few LIVE answers.

| Measurement | Result |
|---|---|
| Backend memory (RSS) at idle, after sign-in | 81 MB |
| RSS after 60 copilot answers, 30 searches and 30 history listings | 82 MB |
| Copilot answer latency, 60 deterministic answers over HTTP | p50 26.6 ms, p95 86.3 ms, max 109.5 ms |
| Backend CPU for those 60 answers | 1.69 s CPU in 2.1 s wall time (about 80% of one core while busy) |
| History search (FTS5) over HTTP | p50 5.6 ms, p95 6.1 ms |
| Conversation list over HTTP | p50 4.9 ms |
| Memory database after the run (30 conversations, 120 messages, 60 agent runs) | 479 KB |
| Backend start-up, including the demo seed and storefront deploy | 2.2 s (first start), 2.2 s (restart) |
| Persistence across a backend restart | 30 of 30 conversations, with all 62 messages of the longest one |
