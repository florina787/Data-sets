# Known limitations and cost analysis

## Limitations (honest status)
- **Live job data needs keys.** Without `JSEARCH_API_KEY` or Adzuna keys, discovery uses employer boards you register plus **clearly labelled synthetic demo jobs**. Indeed- and LinkedIn-origin search *requires* JSearch. Without it the request returns 503 and no trial is consumed.
- **Greenhouse, Lever and Ashby** only work per employer. An admin registers board tokens (`POST /api/jobs/boards`).
- **No outbound email.** An approved recruiter email is logged and handed to the user's mail client (`mailto:`). Approving "submit application" marks the record as applied; the user still applies on the employer's site. Career_flo never submits applications to third-party sites.
- **Small-model quality.** Qwen3 0.6B–4B on CPU is slow and imperfect. That is why routing, scoring and safety are deterministic and every generated resume or letter is fact-checked; output that fails the check is rejected.
- **Resume parsing** is heuristic. Unusual layouts may lose dates or employers, and scanned PDFs are refused (no OCR).
- **Company research** uses Wikipedia plus our own posting index only. There are no employee-review sources (they would need licensing).
- **Not verified here:** a real Stripe test checkout (no keys in this environment), Supabase JWKS verification against a real project, Docker image builds (no Docker daemon in the build sandbox), and end-to-end browser tests of payment flows.

## Capacity (single VM, CPU inference)
Measured on 4 vCPU / 16 GB (see [BENCHMARK.md](BENCHMARK.md)). One generation uses all cores, so requests queue (`LLM_MAX_CONCURRENCY=1`). With Qwen3-1.7B at about 10 tok/s, a 200-token narrative takes about 20 s. In practice that means **a handful of concurrent chat users** before queueing becomes noticeable. Deterministic features (search, matching, ATS, metering) are not limited by the model.

**Scaling options, in order:** use Qwen3-0.6B for the chat narrative (about 3× faster); add a second VM running only the inference server; move to a GPU instance (paid); put rate-limiter and cache state in Redis and run several API replicas.

## Cost model (CAD, estimates — verify current prices)
| Item | Free tier | Paid when it grows |
|---|---|---|
| VM (API + Qwen) | Oracle Always Free A1 (if eligible) | 4–8 vCPU VM ≈ $40–120/mo; GPU ≈ $300+/mo |
| Supabase | Free tier (pauses when idle, size limits) | Pro ≈ $35/mo |
| Frontend | Cloudflare Pages free | — |
| Stripe | No monthly fee | ≈ 2.9% + $0.30 per charge, plus Stripe Tax fees if used |
| JSearch / Adzuna | Small free quotas | Paid tiers by request volume |

A Pro subscription (CAD 9.99) nets about CAD 9.40 after card fees. `features.py` carries an estimated marginal cost per use; the admin dashboard reports estimated gross margin from **actual** usage events and **actual** Stripe invoices. Free infrastructure will not carry many paying users. **Zero operating cost at commercial scale is not realistic.**
