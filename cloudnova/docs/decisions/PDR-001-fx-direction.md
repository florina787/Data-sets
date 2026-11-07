# PDR-001 — FX conversion direction

**Status:** PROPOSED — recommendation `inverse`, **awaiting finance-owner approval**. Active rule remains the
original `documented` (policy v1.0). Nothing changes until approved on the Decisions page and rebuilt.

## The ambiguity
BUSINESS_CONTEXT says: *"Invoice amount is stored in the account's local currency … normalize to USD. Reference FX
used to generate the data: EUR→USD 1.08, GBP→USD 1.27."* Read literally: `amount_usd = amount_local × rate`.

## Evidence (computed by `app/policy.py::impact`, reproducible on the Decisions page)
| Check over 1,421 non-USD, non-refund invoices | `documented` (× rate) | `inverse` (÷ rate) |
|---|---|---|
| Invoices whose USD amount matches the USD price book (list × seats × months × (1 − disc)) within $1 | **0** | **1,421** |
| Q1 paid revenue 2024 | $32,686,371.16 | $29,595,624.38 |
| Paid revenue, all time | $120,147,128.55 | $109,040,641.71 |
| Refunds | −$8,925,163.80 | −$8,200,645.87 |
| Pending + failed exposure | $28,983,255.91 | $26,458,551.07 |

Under the literal rule, every EUR invoice converts to exactly 8% above list price and every GBP invoice to 27% above
— a pattern no discount or pricing rule explains. Under the inverse rule every invoice reconciles to the price book.
The brief says the rates were *"used to generate the data"*; the data shows they were applied by multiplication, so
undoing that generation step means dividing.

## Recommendation
Adopt `inverse` (policy v1.x): `amount_usd = amount_local ÷ rate`. Confidence: high (1,421/1,421 vs 0/1,421).

## What does NOT change automatically
* The eval oracle and the six stakeholder expectations stay on the original rule. If the policy is approved and
  rebuilt, Q1/Q3/Q6-exposure cases will FAIL and `XFAIL-q1-inverse-fx` will XPASS — deliberately, so the change is
  reviewed and the expected values are updated in a separate, explicit commit.
* MRR, churn, counts and Q2/Q4 are list-price based and unaffected.

## Decision log
Recorded in the runtime `policy_decisions` table (approver, role, rationale, impact hash, timestamps, resulting
policy version) and shown on the Decisions page.
