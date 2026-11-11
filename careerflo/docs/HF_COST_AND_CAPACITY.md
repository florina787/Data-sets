# Cost and capacity

**Measured** = run by us on 2026-11-10/11 on a 4-vCPU / 16 GB Linux host with the workload pinned to **2 cores**
(same core count as a Hugging Face CPU Basic Space). **Estimated** = calculated from published prices. **Unverified** =
could not be confirmed from an official source in this session.

## Qwen on 2 vCPU (measured, llama.cpp, Q4_K_M GGUF, thinking disabled)

| | Qwen3-0.6B | **Qwen3-1.7B (default)** |
|---|---|---|
| Model server cold start (weights not in page cache) | 20.9 s | 48.9 s |
| Resident memory (8k context × 2 parallel slots) | 2.01 GB | 3.07–3.46 GB |
| Tokens / s, one request | 23.9 | 11.3 |
| Time to first token, one request | 0.18 s | 0.29–0.49 s |
| 2 concurrent requests — aggregate tok/s · TTFT | 33.8 · 0.19 s | 13.7 · 0.33 s |
| 4 concurrent requests — aggregate tok/s · TTFT | 30.8 · 1.86 s | 13.8 · **3.08 s** (queued beyond 2 slots) |
| Structured JSON extraction | 3/4 | **4/4** |
| Tool selection | 6/8 | **8/8** |
| Resume skill recall / precision | 0.44 / 0.67 | 0.56 / 0.83 |
| Licence | Apache-2.0 | Apache-2.0 |

Small fixed test sets: treat accuracy as indicative. Raw data: `docs/benchmark.json` (4-core run) and the 2-core run
described here (`scripts/benchmark_qwen.py`, `LLM_PROVIDER=llamacpp`).

## Whole application on 2 vCPU (measured, `scripts/load_test.py`)

Entire container (API + llama.cpp) pinned to 2 cores; PostgreSQL; 10 users run register → upload resume → job search →
ranking → career graph while 3 users stream an assistant conversation at the same time.

| Step | p50 | p95 | max |
|---|---|---|---|
| Register | 415 ms | 471 ms | 551 ms |
| Upload + parse resume | 109 ms | 136 ms | 146 ms |
| Job search (synthetic provider) | 512 ms | 610 ms | 636 ms |
| Job matching (3 jobs, via MCP) | 817 ms | 820 ms | 832 ms |
| Career graph | 490 ms | 493 ms | 494 ms |
| Chat first token (3 concurrent chats) | 7.97 s | — | **75.8 s** (3rd chat queued) |
| Chat complete (≈ 350 tokens) | 77.0 s | — | 110.9 s |

0 errors, 3/3 SSE streams completed. **Capacity of one 2-vCPU instance: about 2 simultaneous model generations**; the
deterministic product (search, matching, ATS, tracker, graph, billing) handles 10 concurrent users with p95 < 0.9 s.
Live job providers add their own latency (not measured — no keys).

Rule of thumb: if each active user chats ~5 minutes a day, one 2-vCPU instance comfortably serves a few dozen daily
active users; beyond that, add cores or move generation to Inference Providers.

## Monthly cost by usage level (estimated, USD unless noted, before tax)

Fixed prices used: HF PRO $9/mo; HF CPU Upgrade $0.03/h (≈ $22/mo); Supabase Pro $25/mo (Free: $0 with 1-week pause
and no backups); Hetzner shared cloud from €5.49/mo excl. VAT (RAM of that plan *unverified*); Inference Providers
Qwen3.5-9B $0.10/$0.15 per M tokens (DeepInfra via HF router, 2026-11-10). Stripe fees are per transaction (check
stripe.com/ca/pricing) and excluded.

| Stage | Architecture | Infra / month | Inference | Notes |
|---|---|---|---|---|
| Private test (≤ 10 users) | B: Static Space + Oracle Always Free *(if eligible, unverified)* + Supabase Free | **$0** | $0 (CPU Qwen) | Supabase pauses after 1 week idle; no backups |
| Private test, HF-only | A: Docker Space CPU Basic + Supabase Free | **$9** (PRO) | $0 | Only if a Space can reach Postgres (port 5432 exception) |
| Public beta (≤ 100 users) | B: Static Space + VPS 8 GB + Supabase Free | ≈ $10–20 *(VPS size/price to verify)* | $0 | Free DB tier: no backups — no paying customers yet |
| Paying customers (≤ 500 users) | C: VPS 8 GB + Supabase Pro | ≈ **$35–45** | $0–5 | Backups, no pausing |
| Growth (≈ 2,000 users) | C + `LLM_PROVIDER=hf` (Qwen3.5-9B) or a 4–8 vCPU VPS | ≈ $45–80 | ≈ $25 at 60 calls × 1.8k tokens per user per month | Chat no longer limited by local CPU |

Inference estimate per heavy user via the router: 60 calls × (1,500 in + 300 out) tokens = 90k in + 18k out
→ 90k × $0.10/M + 18k × $0.15/M ≈ **$0.012 per user per month**. PRO's $2 monthly credit covers ≈ 165 such users.

Break-even: at Pro (CA$9.99) the margin is positive from the first few paying users on any of the configurations above;
infrastructure is not the constraint — job-provider API fees (JSearch/Adzuna paid tiers) may be.

## What is not free (and why we do not claim it is)

- Docker Spaces need a paid HF plan to create; free hardware sleeps after 48 h and has no SLA.
- Inference Providers: no free credits for free accounts.
- Supabase Free is unsuitable for paying customers (no backups, pausing).
- Job data at scale requires paid provider plans; their commercial terms must be checked before launch.
