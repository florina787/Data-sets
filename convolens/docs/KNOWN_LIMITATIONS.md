# Known limitations

## Data
- **Public threads only.** Many Twitter support conversations move to direct messages, so outcomes are often unobservable. On the real 30 MB extract, 2,719 of 3,000 conversations have an `unknown` outcome. This is reported, not imputed.
- **No CSAT, NPS, revenue, churn, location or agent identity.** Flo refuses these questions explicitly, and the geographic map stays disabled.
- **Static export (2017).** Time charts show sampled conversation starts, not trends in contact volume.
- **Partial extracts cut threads.** A file made from the first N rows of `twcs.csv` cuts some threads. Such threads are marked `partial`; threads whose start is missing are excluded. Use `tools/make_upload_csv.py` or `tools/sample_threads.py` to keep complete threads.
- The Kaggle data is CC BY-NC-SA 4.0. Its use must be non-commercial.

## Analysis
- **Rules labels (`rules-v1`) are keyword based** and tuned on fixture phrasing. They:
  - leave many real tweets as `other` or `unknown`,
  - miss sarcasm (for example "thanks for nothing"),
  - can mislabel text such as "Yes thank you! … same problem".

  Model extraction is the intended method for real data. Gemini (free tier) has labelled a 300-conversation sample; see below.
- **Redaction gaps:** some agent sign-offs (for example "~ Jess") and names outside greetings are not removed.
- **Rules sentiment and escalation cover en/es/fr/de only.** Other languages get `unknown`.
- **Subthemes are keyword groupings**, not causes. Opportunity severity is a transparent rubric, and effort is only ever reviewer-entered.
- **Journey stages are inferred per message by rules**; transitions follow real reply links.

## Gemini (free tier)
- **Daily quota:** the free tier allows about 20 requests per day per Flash model. Labelling all 3,000 conversations needs about 200 batched requests, i.e. several days of free quota, or a paid tier.
- **Coverage:** only a 300-conversation sample is labelled by Gemini. The 3,000-conversation dataset still uses rules labels.
- **Accuracy unmeasured:** the model's accuracy has not been measured against human-reviewed labels.
- **Topic boundaries:** Flash-Lite sometimes picks the nearest topic loosely, for example a removed menu item labelled "cancellation". Evidence quotes make such cases visible for reviewers.

## Retrieval and multilingual
- **Semantic retrieval needs the optional `embeddings` extra and a model download.** Without them, search is keyword-only and says so.
- **Cross-language retrieval is weak without multilingual embeddings** (Spanish precision@5 0/4 in the reference evaluation).
- **The multilingual reference set is small and synthetic** (12 scenarios), so per-language scores rest on very small samples and are marked as such.
- **Language detection fails on very short tweets**: they get `unknown` rather than a guess. Code-switched text is sometimes labelled with a single language. Reviewers can correct message labels.

## Platform
- **No authentication, SSO or RBAC.** Run ConvoLens locally only (ports bind to 127.0.0.1). Flo sessions are isolated by token, but anyone who can reach the API can read the datasets.
- **Single-process job worker.** Jobs run one at a time. A restart marks running jobs as `interrupted`; resuming restarts them from the beginning (imports are idempotent).
- **SQLite.** Suited to local, single-user use. Not tested with concurrent multi-user load.
- **Memory.** Importing the full 2.8M-row file holds the reply graph in memory (about 1–2 GB).
- **Partial real-mode verification.** Gemini labelling, Flo live chat and Gemini semantic retrieval are verified on real data. Live Claude calls and LangSmith traces are not (no credentials). See [TEST_RESULTS.md](TEST_RESULTS.md).
- **Gemini embeddings cover customer messages only.** The free tier bills every text as a request, so support replies are keyword-searchable but not semantically indexed.
- **No accuracy numbers until people review.** The Human review page computes them, but nobody has reviewed conversations yet.
