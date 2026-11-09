# Free-tier cost simulation

Inputs are measured or taken from the official pages in [FREE_TIER_CLOUD_RESEARCH.md](FREE_TIER_CLOUD_RESEARCH.md), verified on 9 November 2026. All figures are monthly.

## Inputs

| Input | Value | Source |
|---|---|---|
| Windows installer | 487 MB | CI run 42651931298 artifact (zipped installer) |
| Linux AppImage | 740 MB | same run |
| macOS disk image | **not measured** (job had no runner); planned at 740 MB | assumption, upper bound |
| Average installer download | **0.62 GB** | 60% Windows, 30% macOS, 10% Linux (assumed mix) |
| Website, one full visit | 1.4 MB, all images | `site/build.sh` output |
| Website visits per download | 5 (assumed) | |
| AI runtime download (Ollama, ~1.5 GB Windows/Linux, 181 MB macOS) | **not served by VEENA**: comes from Ollama's GitHub release | `backend/runtime/ollama_runtime.py` |
| AI model download (1–4 GB) | **not served by VEENA**: comes from the Ollama library | |
| Inference per answer | **customer's own computer** | |

Assumption: one installer download per new customer per month, plus an update download per existing customer per release.

## Option A: free desktop distribution (recommended)

| Monthly new customers | Installer traffic (GitHub Releases) | Website traffic (GitHub Pages, 100 GB soft limit) | Cloud database | Inference | **Owner's cost** |
|---|---|---|---|---|---|
| 100 | 62 GB | 0.7 GB | none | on customers' computers | **CAD $0** |
| 1,000 | 620 GB | 7 GB | none | on customers' computers | **CAD $0** |
| 10,000 | 6.2 TB | 70 GB (70% of soft limit) | none | on customers' computers | **CAD $0** |

- GitHub Releases: "no limit on the total size of a release, nor bandwidth usage". There is no payment method, so there is no overage path.
- At around 14,000 new customers a month, website traffic would pass the 100 GB **soft** limit. Mitigations, still $0: compress screenshots to WebP (about ×4 smaller), or move the static site to Cloudflare Pages (static requests "free and unlimited").
- Updates: if 10,000 existing customers update once a month, installer traffic rises by about 6.2 TB, still on GitHub Releases at $0.

## Option B: free-tier hybrid (optional sync and accounts)

Adds a small API (Cloudflare Workers Free: 100,000 requests/day) and Neon Free (1 GB, 100 CU-hours per project).

| Users | API requests (assume 20 per active user per day) | vs Workers Free | Sync data (assume 2 MB per user) | vs Neon 1 GB | Cost |
|---|---|---|---|---|---|
| 100 | 2,000/day | 2% | 200 MB | 20% | $0 |
| 1,000 | 20,000/day | 20% | 2 GB | **over 1 GB**: writes blocked, needs sharding across projects or Turso (5 GB) | $0, at risk |
| 10,000 | 200,000/day | **200%**: requests fail past 100k/day | 20 GB | over every free database | **not free** |

Option B is free to about 1,000 users, and only if sync stays small. Neon blocks writes and Workers return errors instead of billing on the free plans, so there are no surprise charges; the cost is service failures instead.

## Option C: SaaS foundation

Accounts, multi-tenant data, cloud storage and optional cloud inference cannot stay on free tiers at 1,000+ users. The verified free offers that could host it either need a billing account (Google Cloud Run), are promotional credits (Azure 30 days, AWS 6 months), sleep (Render, Supabase after a week), or are capacity-limited (Oracle A1 "out of host capacity", idle reclamation). Cloud LLM inference has no free tier suitable for customers. Option C needs a budget and should follow customer acceptance of the free desktop product; see [docs/SAAS_COMMERCIALIZATION_ROADMAP.md](../docs/SAAS_COMMERCIALIZATION_ROADMAP.md).

| Users | Option A | Option B | Option C |
|---|---|---|---|
| 100 | $0 | $0 | Free-tier possible, but needs a card on Google or Oracle |
| 1,000 | $0 | $0, near limits | Paid |
| 10,000 | $0 | Paid or degraded | Paid |

## Exhaustion and suspension risks (Option A)

| Risk | Likelihood | Effect | Response |
|---|---|---|---|
| Pages soft bandwidth exceeded | Low below 14k downloads/month | GitHub may contact the owner | Move the static site to Cloudflare Pages |
| GitHub flags release downloads as abuse | Low for a public open-source project | Downloads throttled | Mirror installers to Cloudflare R2: 10 GB free, egress free, but a card may be needed and operations are billed past 10M reads |
| Ollama changes or removes the pinned runtime release | Low | Setup cannot download the runtime | Pin a new version and SHA-256 in `backend/runtime/ollama_runtime.py`, ship an update |
| Ollama library or Hugging Face outage | Occasional | New installs cannot download models | Already-installed customers unaffected; Setup shows a retry |

**No component of Option A has a payment method attached, so none of them can produce a charge.**
