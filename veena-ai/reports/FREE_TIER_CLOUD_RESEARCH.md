# Free-tier cloud, storage and website research for VEENA.AI

Verified on **9 November 2026** from each provider's own pricing or documentation pages (links in the table).
Where a page did not state something, it is marked **unverified** rather than filled in from memory.
Prices are in USD as published; no CAD prices were published on these pages.

## Bottom line

VEENA's first public beta does not need a cloud backend, a database or paid storage. Everything a customer needs is:

1. a public website: **GitHub Pages** (free, HTTPS, `florina787.github.io`), with **Cloudflare Pages** as the fallback;
2. installer downloads: **GitHub Releases** (2 GiB per file, *no bandwidth or total-size limit stated*);
3. AI inference and data: **on the customer's own computer** (Ollama + SQLite), which costs the owner nothing per user.

This is **Option A** below. At 100, 1,000 or 10,000 customers it stays at **CAD $0 per month** within the limits verified here, and none of its services can bill the owner: none of them has a payment method on file.

## Verified comparison

| Provider | Service | Free allowance (as published) | Always on? | Card required? | Commercial use? | Key limits | Official URL | Verified |
|---|---|---|---|---|---|---|---|---|
| GitHub | Releases | Files up to 2 GiB each; up to 1,000 assets per release; "no limit on the total size of a release, nor bandwidth usage" | Yes | No | Yes (public repo) | 2 GiB per file | [docs](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) | 2026-11-09 |
| GitHub | Pages | Site ≤ 1 GB; soft 100 GB/month bandwidth; soft 10 builds/hour (not for Actions-deployed sites); 10-minute deploy timeout | Yes (static) | No (unverified for private repos) | Not for "online business, e-commerce" or "commercial software as a service". A free open-source project page is in scope | 1 site per repo | [limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits), [terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features) | 2026-11-09 |
| Cloudflare | Pages | Static asset requests "free and unlimited" on free and paid plans; 500 builds/month; 1 concurrent build; 20,000 files; 25 MiB per file | Yes (static) | Unverified | Unverified (Cloudflare terms not reviewed) | 25 MiB per file, so installers cannot go here | [limits](https://developers.cloudflare.com/pages/platform/limits/), [pricing](https://developers.cloudflare.com/pages/functions/pricing/) | 2026-11-09 |
| Cloudflare | Workers | 100,000 requests/day; 10 ms CPU per invocation; KV: 100k reads/day, 1k writes/day, 1 GB; D1: 5M rows read/day, 100k written/day, 5 GB | Yes (serverless) | Unverified | Unverified | KV ops fail with an error when exceeded (no charge on Free) | [pricing](https://developers.cloudflare.com/workers/platform/pricing/) | 2026-11-09 |
| Cloudflare | R2 | 10 GB-month storage; 1M Class A and 10M Class B operations/month; **egress free** | Yes | Unverified | Unverified | Overage *is billed*: $0.015/GB-month, $4.50/M Class A, $0.36/M Class B | [pricing](https://developers.cloudflare.com/r2/pricing/) | 2026-11-09 |
| Vercel | Hobby | 100 GB Fast Data Transfer; 1M function invocations; 4 active CPU-hours; 1M CDN requests | Yes | No (Pro needs card) | **No: "non-commercial, personal use only"** | Exceeding usually pauses the feature for 30 days | [hobby](https://vercel.com/docs/plans/hobby) | 2026-11-09 |
| Netlify | Free | 300 credits/month, "hard limit and no auto recharge"; bandwidth 20 credits per GB (≈ 15 GB if nothing else used); production deploy 15 credits | Yes | "You'll never be charged for the Free plan" | Unverified | What happens at 300 credits is not stated (a "resume paused projects" page exists) | [credits](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/) | 2026-11-09 |
| Google Firebase | Spark (Hosting) | 10 GB storage; **360 MB/day** transfer; no payment method needed. Cloud Storage not available on Spark. Firestore: 1 GiB, 50k reads and 20k writes per day | Yes | No | Unverified | 360 MB/day is under one installer | [pricing](https://firebase.google.com/pricing) | 2026-11-09 |
| Microsoft Azure | Static Web Apps Free | 100 GB/month bandwidth (overage "Unavailable" on Free); 250 MB per app; 2 custom domains; free SSL; no SLA | Yes | Azure subscription needs a credit or debit card | Plan is labelled "For personal projects" | 10 apps per subscription | [plans](https://learn.microsoft.com/en-us/azure/static-web-apps/plans), [quotas](https://learn.microsoft.com/en-us/azure/static-web-apps/quotas) | 2026-11-09 |
| Microsoft Azure | Free account | Credits must be used within 30 days; card required (temporary authorisation hold); 12-month free services require moving to pay-as-you-go within 30 days | Promotional | **Yes** | Yes | The $200 figure was not on the fetched page (unverified) | [offer](https://azure.microsoft.com/en-us/pricing/offers/ms-azr-0044p), [free services](https://azure.microsoft.com/en-us/pricing/free-services) | 2026-11-09 |
| Oracle Cloud | Always Free | 2 AMD micro VMs (1/8 OCPU, 1 GB); Ampere A1 up to 2 OCPU / 12 GB; 200 GB block storage; 20 GB object storage; **10 TB/month outbound**; 2 Autonomous DBs (20 GB each) | Yes, but idle instances "may" be reclaimed (CPU p95, network and memory all under 20% for 7 days) | Unverified on fetched page | Yes | Home-region only; "out of host capacity" errors | [always free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) | 2026-11-09 |
| Google Cloud | Free Tier | Cloud Run: 2M requests, 180k vCPU-s, 360k GiB-s per month; one e2-micro VM in us-west1/us-central1/us-east1; Cloud Storage 5 GB (US regions); $300 trial for 90 days | Run scales to zero | **Yes: "A Google Cloud billing account is required"** | Yes | Only 1 GB/month free egress for Run and Compute; overage billed | [free tier](https://docs.cloud.google.com/free/docs/free-cloud-features) | 2026-11-09 |
| AWS | Free plan | Up to $200 credits; account closes 6 months after opening or when credits run out; "30+ services always free within monthly usage limits" | Promotional | Unverified on fetched page | Yes | Free plan account closes at 6 months unless upgraded | [free](https://aws.amazon.com/free/) | 2026-11-09 |
| Render | Free web service | 750 instance-hours/month per workspace; spins down after 15 minutes without traffic, about one minute to wake; free Postgres expires after 30 days | **No** (sleeps) | Not required for Free; bandwidth overage is billed if a card is on file | "Do not use them for production applications" | Without a card, services are suspended when limits are hit | [free](https://render.com/docs/free) | 2026-11-09 |
| Koyeb | Free | Only a free Postgres (0.25 vCPU, 1 GB RAM, 1 GB storage, "5h") is described on the pricing page | Scale-to-zero | Unverified | Unverified | Free compute instance **unverified** on the fetched page | [pricing](https://www.koyeb.com/pricing) | 2026-11-09 |
| Hugging Face | Spaces | **Static Spaces free for everyone**; Gradio/Docker Spaces "require a paid plan to create" (except 2 ZeroGPU Spaces per free account); CPU Basic 2 vCPU / 16 GB; free Spaces sleep when unused | Static: yes; compute: sleeps | No for static | Unverified | Disk is not persistent | [spaces](https://huggingface.co/docs/hub/spaces-overview) | 2026-11-09 |
| Supabase | Free | 500 MB database; 1 GB file storage; 5 GB egress; 50,000 MAU; 2 active projects; **paused after 1 week of inactivity**; no automatic backups | No (pauses) | Unverified | Unverified | | [pricing](https://supabase.com/pricing) | 2026-11-09 |
| Neon | Free | 1 GB per project (20 GB per account); 100 CU-hours per project per month; scale to zero after 5 minutes (always on); pgvector available; no card | Scales to zero | **No** | Unverified | Writes blocked over 1 GB; compute suspended when CU-hours run out | [pricing](https://neon.com/pricing) | 2026-11-09 |
| Turso | Free | 100 databases; 5 GB; 500M rows read and 10M written per month; "no credit card required" | Yes | **No** | Unverified | | [pricing](https://turso.tech/pricing) | 2026-11-09 |
| Railway | Trial / Free | One-time $5 for up to 30 days, then $1/month credit; 1 GB RAM, shared vCPU | Credit-limited | Unverified | Unverified | $1/month cannot run an always-on service | [trial](https://docs.railway.com/reference/pricing/free-trial) | 2026-11-09 |
| Backblaze | B2 | First 10 GB always free; egress free up to 3× average monthly storage, then $0.01/GB | Yes | Unverified (pay-as-you-go uses card or invoice) | Unverified | Egress beyond 3× storage is billed | [pricing](https://www.backblaze.com/cloud-storage/pricing) | 2026-11-09 |
| Oracle | Object Storage | 20 GB (Always Free only), 50,000 API requests/month; objects over 20 GB are **deleted** when a trial ends | Yes | Unverified | Yes | 50k requests/month caps downloads | (Always Free page above) | 2026-11-09 |

Not researched in detail because the fetched pages did not answer the questions, or the service is clearly unsuitable: Azure Blob Storage and AWS S3 (both bill egress after small or promotional allowances; pricing pages not fetched, so **unverified**).

### Canada

None of the fetched pages restricted the free static hosting or releases above by country. Oracle Always Free resources must be in the home region chosen at sign-up, and Canadian regions exist but were not verified for capacity. Google's free e2-micro and Cloud Storage are **US regions only**.

## Website hosting: comparison and choice

| Need | GitHub Pages | Cloudflare Pages | Vercel Hobby | Netlify Free | Firebase Spark | Azure SWA Free |
|---|---|---|---|---|---|---|
| Public, no login, HTTPS, free subdomain | Yes | Yes | Yes | Yes | Yes | Yes |
| Commercial use | OK for a free open-source project page; not for SaaS or e-commerce | Unverified | **No** | Unverified | Unverified | "Personal projects" |
| Bandwidth | 100 GB soft | Unlimited static | 100 GB | ≈ 15 GB of credits | 360 MB/day | 100 GB |
| Needs a new account | No (same GitHub) | Yes | Yes | Yes | Yes (Google) | Yes + card |
| Auto-deploy from this repo | GitHub Actions (built) | Git integration | Git integration | Git integration | CLI/Actions | Actions |
| Analytics | None built in | Web Analytics (free tier unverified) | 50k events | Paid | GA (separate) | No |

**Choice: GitHub Pages.** It needs no new account, no card, and no third-party data processor beyond GitHub, which already hosts the code. It deploys from the workflow already in the repository and allows 100 GB/month, about 70,000 full visits of the 1.4 MB page. **Fallback: Cloudflare Pages**, if traffic outgrows the soft limit or GitHub asks the project to move.

## Storage: installer distribution

Installers measured from CI run [42651931298](https://github.com/florina787/Data-sets/actions/runs/42651931298): **Windows 487 MB, Linux 740 MB**. macOS has not been measured, because that job did not get a runner; planning assumes it is no larger than Linux.

| Option | Fits a 740 MB file? | Bandwidth for 10,000 downloads (~6 TB) | Can it bill the owner? |
|---|---|---|---|
| **GitHub Releases** | Yes (≤ 2 GiB) | No limit stated | **No** |
| Cloudflare R2 | Yes | Egress free; 10M Class B reads/month free | Yes, past 10 GB storage or the operation quotas |
| Backblaze B2 | Yes | Free only up to 3× stored (≈ 6 GB for 2 GB stored) | Yes ($0.01/GB beyond) |
| Oracle Object Storage | Yes | 10 TB/month egress | 50,000 requests/month cap; trial deletion risk |
| Supabase Storage | Upload limit unverified | 5 GB egress | Pauses |
| Firebase Storage | Not on Spark | n/a | Needs Blaze (billing) |
| Azure Blob / AWS S3 | Yes | Egress billed (unverified) | Yes |

**Choice: GitHub Releases.** It is the only option verified to have no bandwidth limit, no card and no billing path. Installers are never stored in a database.

## Databases

VEENA's first public beta **does not need a cloud database**. Conversations, transcripts, documents and agent traces are stored in local SQLite on the customer's computer, by design and as the privacy promise requires. A cloud database would only be needed for optional sync or accounts (Options B and C).

| | Neon Free | Supabase Free | Turso Free | Oracle Autonomous (Always Free) | Firestore (Spark) |
|---|---|---|---|---|---|
| Storage | 1 GB/project | 500 MB | 5 GB | 20 GB × 2 | 1 GiB |
| Inactivity | Scales to zero after 5 min (wakes on query) | **Paused after 1 week** | No pause stated | Unverified | n/a |
| Postgres / pgvector | Yes / yes | Yes / yes (unverified on page) | No (SQLite/libSQL) | No (Oracle) | No |
| Backups | 6 h history | None on Free | Unverified | Unverified | Unverified |
| Card | No | Unverified | No | Unverified | No |

If Option B is ever built: **Neon** (no card, Postgres with pgvector, wakes on demand) or **Turso** (no card, SQLite-compatible like VEENA's local store).

## Backend hosting (not needed for Option A)

| | Can run FastAPI? | Always on? | Free without a card? | Suitable for |
|---|---|---|---|---|
| Cloudflare Workers | No (JavaScript/Python Workers, not a FastAPI server) | Yes | Unverified | Download counters, health endpoint |
| Google Cloud Run | Yes | Scales to zero | **No (billing account)** | Option C |
| Oracle A1 (2 OCPU/12 GB) | Yes | Yes, unless reclaimed when idle | Unverified | Option B/C API |
| Render Free | Yes | No (15-minute sleep, ~1 minute cold start) | Yes | Demos only ("not for production") |
| Koyeb | Unverified | Unverified | Unverified | |
| Hugging Face Spaces | Docker Spaces need a paid plan | Sleeps | n/a | |
| Azure | App Service free tier unverified | | Card required | |

**LLM inference in the cloud is not free at useful scale.** A free CPU instance (for example Oracle A1 with 2 OCPU) would serve one request at a time for a 1.5B model, at speeds comparable to the 4-vCPU test machine (about 20 tokens/s). It cannot serve concurrent customers reliably, and free GPUs were not found on any provider. VEENA therefore keeps inference on the customer's computer.

## Three architectures

| | A. Free desktop distribution (**recommended**) | B. Free-tier hybrid | C. SaaS foundation |
|---|---|---|---|
| Website | GitHub Pages | GitHub Pages | Cloudflare Pages or Pages |
| Installers | GitHub Releases | GitHub Releases | GitHub Releases + CDN |
| Inference | Customer's computer | Customer's computer | Customer's computer, plus optional paid cloud GPU |
| Data | Local SQLite | Local, plus optional sync to Neon/Turso | Multi-tenant Postgres (paid) |
| Accounts | None | Optional | Required |
| Backend | None | Cloudflare Workers or Oracle A1 | Cloud Run or managed containers (paid) |
| Cost at 100 / 1k / 10k users | **$0 / $0 / $0** | $0 / $0 / likely $0, with free-tier exhaustion risk | Not free (see cost simulation) |
| Billing risk | **None**: no payment method anywhere | Low with no card on file; Oracle and Google need card or billing | Yes |

Detailed numbers: [FREE_TIER_COST_SIMULATION.md](FREE_TIER_COST_SIMULATION.md). Implementation: [docs/ZERO_COST_DEPLOYMENT_ARCHITECTURE.md](../docs/ZERO_COST_DEPLOYMENT_ARCHITECTURE.md).

## Risks

- **GitHub Pages terms:** Pages is not for "commercial software as a service". A free download page for open-source software fits; a page that sells subscriptions would not. If VEENA later sells plans, move the site to Cloudflare Pages or a paid host first.
- **Soft limits:** the 100 GB Pages bandwidth is "soft". GitHub may contact the owner rather than cut the site off, but this is not guaranteed.
- **Release bandwidth:** GitHub states no limit, but its Acceptable Use Policies still apply, and Actions must not be used "as a content delivery network". Installers belong in Releases, not as Actions artifacts.
- **Third-party downloads at first run:** the AI runtime comes from Ollama's GitHub release, models from the Ollama library, and speech and embedding models from Hugging Face. These cost the owner nothing, but VEENA depends on them staying available. The runtime is pinned by version and SHA-256, so a changed file is rejected rather than run.
- **Promotional credits** (Azure 30 days, Google 90 days, AWS 6 months, Railway 30 days) are not free tiers and were excluded from every recommendation.
