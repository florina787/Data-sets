# Data provider matrix

"Tested" means exercised in this repository's automated tests. **No provider was reachable live from the build container.**

| Domain | Provider | Adapter | Point-in-time handling | Licence / limits | Status here |
|---|---|---|---|---|---|
| Daily OHLCV (global) | Stooq | `StooqDaily` | EOD; `available_at` = exchange close + 30 min | Free, personal/research use; check redistribution | Parser tested with recorded payload; live call returned empty body |
| Daily OHLCV adjusted | Alpha Vantage | `AlphaVantageDaily` | as above | Free tier ≈ 25 requests/day; attribution required; key via `ALPHAVANTAGE_API_KEY` | Parser + error path tested; no key |
| Macro series | FRED / ALFRED | `FredSeries` | uses `realtime_start` vintages → value known on its publication date | Free API key (`FRED_API_KEY`); FRED terms | Parser tested; host timed out |
| Daily quotes | Yahoo-compatible | — (not built) | — | Unofficial endpoints, ToS risk, rate limits | 429 from container; **not recommended for production** |
| Filings, insider (Form 4), 13F | SEC EDGAR | ⬜ | acceptance timestamp = `available_at`; 13F is 45 days delayed and must be shown as such | Free; must send declared User-Agent; 10 req/s | 403 from container |
| Intraday / tick / L2 | licensed vendor (e.g. Polygon, Databento, exchange feeds) | ⬜ | microsecond timestamps; LIVE status only within 2 s | Paid; exchange redistribution agreements | **Required before any scalping/intraday readiness claim** |
| Options chains, IV | licensed vendor | ⬜ | — | Paid | not started |
| News | GDELT, NewsAPI, Event Registry, Finnhub, RSS | ⬜ | article publish time + ingestion time | Mixed; respect attribution | not started |
| Disasters / health | USGS, WHO | ⬜ | event time + publish time | Public | not started |
| Engineering data | `synthetic.generate_universe` | ✅ | full `ts`/`available_at`, listings/delistings, split, injected defects | none (generated) | used for all runs, labelled `SYNTHETIC` |

## Rules every adapter follows (`data/providers/base.py`)

* Output columns are fixed (`BAR_COLUMNS`); missing columns raise.
* Token-bucket rate limiter per provider; exponential-backoff retries; failures raise `ProviderError` (never silently empty).
* Cache entries store `retrieved_at`. Within the freshness window the provider's native status is kept; beyond it the data is labelled
  `CACHED`. **Nothing from cache is ever labelled LIVE.**
* `Provenance` (source, retrieved_at, status, licence note) travels with every fetch.

## Calendars and time zones

11 exchanges are configured (NYSE, Nasdaq, TSX, LSE, Xetra, Euronext Paris, Tokyo, Hong Kong, NSE, ASX, B3) with local close times;
bars are stamped at local close converted to UTC (DST-aware). Holiday calendars are **not** bundled: missing weekdays are counted by the
quality check rather than filled. Production should add `exchange_calendars`.
