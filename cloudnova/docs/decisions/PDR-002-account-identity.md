# PDR-002 — Account identity

**Status:** PROPOSED — recommendation **keep `account_id`** (no change), **awaiting finance-owner confirmation**.
`account_name` can be recorded as a decision but is **blocked from being applied** (see evidence).

## The ambiguity
The brief lists `account_id / account_name — The customer account`. The export has 3,815 `account_id`s but only
200 `account_name`s, so "top 5 accounts" gives different answers depending on which one is the identity.

## Evidence (computed by `app/policy.py::impact` and a profiling script during the build)
| Candidate key | Groups | % of groups whose invoices disagree on region, plan or churn |
|---|---|---|
| `account_id` | 3,815 | 24.4% |
| `account_name` | 200 | **100%** |
| company stem (first word of name) | 20 | 100% |
| email domain | 20 | 100% |

Every name appears with several regions, plans, industries and signup dates; each email domain is shared by ~10
names. Names behave like randomly attached labels, not a customer master. `account_id` is far more coherent (its
remaining 24% inconsistency is handled by the latest-invoice snapshot rule).

Top-5 by net revenue: by `account_id` → ACC-7509, ACC-1420, ACC-9946, ACC-1196, ACC-5211; by name → Oscorp
Industries, Nakatomi Labs, Tyrell Industries, Soylent Holdings, Stark Inc.

## Recommendation
Keep `account_id` as identity; treat `account_name` as a display label. A company-level roll-up needs a master-data
mapping (account_id → legal entity) from CloudNova's CRM — the export cannot provide one.

## What does NOT change automatically
`XFAIL-top5-by-company-name` stays an expected failure: it documents that a name-based reading exists and differs.
