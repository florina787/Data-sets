# Cloud migration strategy

VEENA starts with no cloud backend (Option A). This is the order in which cloud pieces would be added, and the trigger for each, so nothing is paid for before it is needed.

| Stage | Trigger | Change | Cost | Data leaving the computer |
|---|---|---|---|---|
| 0. Today | – | GitHub Pages + GitHub Releases; local inference and SQLite | $0 | None (downloads only) |
| 1. Traffic | Pages near 100 GB/month, or GitHub asks | Move the static site to Cloudflare Pages (same `_site` folder); keep Releases | $0 | None |
| 2. Download resilience | Release downloads throttled | Mirror installers to Cloudflare R2 (10 GB free, free egress); website falls back to the mirror | $0 within the free tier; billed past 10 GB or 10M reads | None |
| 3. Optional sync | Customers ask to use VEENA on two computers | Opt-in encrypted sync of settings and selected sessions to Neon or Turso (no card), behind an account | $0 up to about 1,000 users | Only what the user opts to sync, encrypted |
| 4. Teams / SaaS | Paying organisations | See [SAAS_COMMERCIALIZATION_ROADMAP.md](SAAS_COMMERCIALIZATION_ROADMAP.md) | Paid | Per contract and consent |

Principles:

- **Local first stays the default.** No feature that sends transcripts, screens or documents to a cloud service is enabled without explicit consent per feature.
- **No card on file until revenue.** Free tiers that need a payment method (Google Cloud, Azure, Oracle in practice) are avoided until a budget exists, so nothing can bill by surprise.
- **Portable formats.** SQLite, CycloneDX and static HTML move between providers without rewrites.
- **Exit test before entry.** Each stage documents how to roll back to the previous one before it is adopted.
