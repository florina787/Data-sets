# Hugging Face services — free-tier research (verified 2026-11-10)

Every fact below was read from Hugging Face's official documentation or live API on **2026-11-10**, unless marked
*community evidence* or *unverified*. Prices and policies change: re-check before launch.

## Summary

| Service | Free? | Needs paid plan? | Quotas / limits | Sleeps when idle? | Persistent storage | Fit for Career_flo |
|---|---|---|---|---|---|---|
| **Static Space** | ✅ free for everyone | No | Static files only; optional build step (`app_build_command`) | No compute to sleep | n/a | ✅ React frontend |
| **Docker Space – CPU Basic** | Hardware free | **Yes — PRO ($9/mo) to create** Docker/Gradio Spaces on a personal account | 2 vCPU, 16 GB RAM, 50 GB **ephemeral** disk; **outbound only to ports 80, 443, 8080** | **Yes — after 48 h without visitors** (wakes on next visit) | Disk lost on restart; Storage Buckets as volumes | ⚠️ Works for API + Qwen, **but cannot reach Supabase Postgres (5432/6543)** — see below |
| **Docker Space – CPU Upgrade** | No | PRO | 8 vCPU, 32 GB, $0.03/h ≈ $22/mo; never sleeps by default; custom sleep time | Configurable | as above | Paid scale-up path |
| **GPU Spaces** | No | PRO | From $0.40/h (T4 small, ≈ $288/mo) | Configurable | as above | Not needed for 0.6–1.7B |
| **ZeroGPU** | ✅ (2 Spaces for free accounts older than 30 days) | No (10 with PRO) | **Gradio SDK only**; daily GPU quota 5 min (free) / 40 min (PRO); 60 s default per call | n/a | n/a | ❌ Not a FastAPI/Docker server |
| **Inference Providers** | ❌ free accounts get **no credits** (must buy) | PRO gets **$2/month** credits | Pass-through provider prices, no HF markup | n/a | n/a | ✅ Optional Qwen path (Qwen3.5-9B and larger) |
| **Inference Endpoints** | ❌ | Subscription + card | From $0.033/h (1 vCPU / 2 GB) ≈ $24/mo; per-minute billing; scale-to-zero exists | Optional scale-to-zero | n/a | Possible, but costs more than a VPS |
| **Hub (models/datasets)** | ✅ public repos | No | Storage pricing beyond free quota ($12–18/TB/mo) | n/a | ✅ | Model download source (pinned revisions) |
| **Storage Buckets** | Paid storage | — | Mounted into a Space at a chosen path at runtime (not at build time) | n/a | ✅ | Not suitable for a production database (see below) |
| **Secrets & variables** | ✅ | No | Variables are **public** and passed as Docker build args; Secrets are private, exposed at runtime (and at build via `--mount=type=secret`) | — | — | ✅ Used by `space.env.example` |
| **`huggingface_hub` / GitHub Actions** | ✅ | No | `upload_folder`, `create_repo`, secrets/variables API; official `huggingface/hub-sync` action | — | — | ✅ `scripts/hf_deploy.py`, `hf_rollback.py` |

Sources: [Spaces overview](https://huggingface.co/docs/hub/spaces-overview), [Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker),
[Static Spaces](https://huggingface.co/docs/hub/spaces-sdks-static), [GPU Spaces & sleep time](https://huggingface.co/docs/hub/spaces-gpus),
[ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu), [Inference Providers pricing](https://huggingface.co/docs/inference-providers/pricing),
[Inference Endpoints pricing](https://huggingface.co/docs/inference-endpoints/en/pricing), [Pricing](https://huggingface.co/pricing),
[Spaces storage](https://huggingface.co/docs/hub/spaces-storage), [GitHub Actions](https://huggingface.co/docs/hub/spaces-github-actions).

## The decisive constraint: outbound ports

The Spaces documentation states: *"you can make requests through the standard HTTP and HTTPS ports (80 and 443)
along with port 8080. Any requests going to other ports will be blocked."* Supabase Postgres listens on **5432**
(direct/session pooler) and **6543** (transaction pooler).

*Community evidence:* users report `Network is unreachable` connecting to Postgres from Spaces
([example](https://huggingface.co/spaces/danishjameel003/assitantchatbot/blob/main/fix_supabase_connection.py)); HF staff
have opened port 5432 for individual Spaces on request
([forum](https://discuss.huggingface.co/t/open-port-for-space-to-connect-to-postgresql/29938/9),
[forum](https://discuss.huggingface.co/t/open-5432-port-to-connect-to-postgresql-for-langfuse-app/149230)) — an exception,
not a policy. **Not tested by us** (no HF account was used). The packaged Space reports this immediately: on first boot
`GET /api/health/ready` returns `"database": {"ok": false}` and HTTP 503 if the port is blocked.

Consequences: running Career_flo's FastAPI backend *inside* a Space requires either (a) HF opening 5432/6543 for the
Space, (b) rewriting the data layer onto Supabase's HTTPS Data API — a large rewrite of working code, rejected by the
brief — or (c) a database reachable on 443 (none of the managed Postgres offerings we use provide that). Hence the
recommended architecture keeps the API off Spaces (see `HF_DEPLOYMENT_ARCHITECTURE.md`).

## Storage Buckets as a database? No.

Buckets are object storage mounted as a volume. Running SQLite or Postgres on such a mount risks file-locking and
durability problems; it is single-replica and would make Career_flo's billing ledger (atomic trial reservations) depend
on it. Not acceptable for paying customers.

## Qwen availability on Inference Providers (live router catalogue, 2026-11-10)

`GET https://router.huggingface.co/v1/models` listed 126 models, 21 Qwen-family. **Qwen3-0.6B, 1.7B and 4B are not
offered.** The smallest routable Qwen was **Qwen/Qwen3.5-9B** (cheapest provider DeepInfra: **$0.10 / $0.15 per million
input / output tokens**); Qwen/Qwen3-32B: $0.08 / $0.28. Licences (Hub metadata): Qwen3-0.6B/1.7B/4B, Qwen3.5-9B and
Qwen3-32B are **Apache-2.0**, not gated.

## Commercial use

The [Terms of Service](https://huggingface.co/terms-of-service) do not prohibit hosting a commercial app on Spaces, but
provide services "as is" with no availability warranty, allow suspension/termination at any time, and cap liability
(e.g. $50 for free services). There is **no SLA on Spaces**. For paying customers this matters: plan for an alternative
host (the same container runs on any VPS — `deploy/vps/compose.yml`).

## Supabase Free vs Pro (supabase.com/pricing, 2026-11-10)

Free: 500 MB DB, 50,000 MAU, 5 GB egress, **paused after 1 week of inactivity**, **no automatic backups**, 2 active
projects. Pro (from $25/mo): daily backups (7 days), never paused, 8 GB disk, 100,000 MAU.
→ Free is fine for development and a private beta; **paying customers need Pro** (backups + no pausing).
