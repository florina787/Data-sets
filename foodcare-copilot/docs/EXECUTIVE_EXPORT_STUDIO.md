# Executive Export Studio

Real PDF files built on the server with ReportLab (`backend/app/exports.py`) from the same
policy-filtered data as the screens, with purpose `export` (no confidential values).

## How to get one

* **Reports → Export Studio**: one card per report, **Download PDF**.
* **Ask Jerry**: "Prepare a PDF for my board", "Make this board-ready", "Prepare a security and
  savings board report", "Prepare a board-ready enterprise delivery briefing PDF". Jerry builds the
  file and offers a download action.
* API: `GET /api/exports` (list), `GET /api/exports/{kind}.pdf?ref=` (signed in).

## Report kinds

Executive: `board`, `executive`, `decisions`, `architecture`, `investigation`, `conversation`.
Security and savings: `security_savings`, `security_posture`, `incident_impact`, `availability`,
`remediation`, `licenses`, `renewals`.
Delivery portfolio: `delivery_board`, `portfolio_weekly`, `project_status`, `tech_dependencies`,
`commercial_review`, `marketing_readiness`.
Operations: `technology`, `supplier_risk`.

## What every PDF contains

Executive summary · findings · charts with text alternatives · evidence and provenance ·
reporting period · assumptions and limitations · next steps · generation timestamp ·
classification footer · "synthetic data" label where applicable. Savings are written as
**cost savings / avoided expenditure**, never as revenue.

## Safety

* `investigation` and `conversation` exports check ownership of the referenced record.
* Unknown kinds are rejected with the list of valid kinds.
* Tests decode the PDF streams and search for canaries (`test_pdf_exports_are_real_and_policy_filtered`,
  `test_new_reports_are_real_and_clean`).

Dependency: `reportlab==4.2.5` (BSD), listed in `THIRD_PARTY_NOTICES.md`.
