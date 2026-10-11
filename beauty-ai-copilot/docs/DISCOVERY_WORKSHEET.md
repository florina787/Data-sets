# Discovery worksheet and pilot definition

Purpose: test whether the workflow needs this prototype assumes are real, and whether existing capabilities already
cover them. Every gap below is a **hypothesis**. Record its status as `unvalidated`, `validated`, `rejected` or
`already addressed`.

## Interview guide

| # | Topic | Questions | Notes / answer | Source |
|---|---|---|---|---|
| 1 | Current change workflow | How does a change to a shade or try-on model move from request to production today? Who signs off at each step? Where are decisions recorded? | | |
| 2 | Existing evaluation tools | Which tools compute subgroup metrics today? Are baseline and candidate compared on matched samples? How are uncertainty and repeated comparisons handled? | | |
| 3 | Pain points | Where do changes stall or get reworked? Any recent regression that reached users? How was it found? | | |
| 4 | Supported models | Which models and versions are in scope? Where are artifacts registered and how are they versioned and digested? | | |
| 5 | Source-of-truth policies | Which documents define release rules, image quality, lighting and consent? Who owns them and how are versions retired? | | |
| 6 | Group definitions | How are evaluation groups defined, and who approved that protocol? Are any labels inferred? (They should not be.) | | |
| 7 | Ground truth | **How is true shade suitability established?** Expert assessment, customer feedback, measured colour references, or a combination? How is inter-rater agreement measured? | | |
| 8 | Consent process | How are consent, permitted use, retention and deletion recorded for evaluation images? Is training consent separate? | | |
| 9 | Release owners | Who may approve a release? Is separation of duties required? How long is an approval valid? | | |
| 10 | Deployment capabilities | Do progressive delivery, canary allocation and rollback already exist? With what controls? | | |
| 11 | Monitoring labels | Which post-release outcome signals exist (returns, re-matches, expert audits)? What is the delay and coverage per device cohort? | | |
| 12 | Existing coverage | **Which existing capabilities already cover this workflow?** Where should this integrate rather than replace? | | |

## Gap hypotheses

| ID | Hypothesis | Status | Evidence needed |
|---|---|---|---|
| H1 | Aggregate metrics are used for release decisions without per-cell gates | unvalidated | Recent release records |
| H2 | Release approvals are not bound to artifact digests and evaluation configuration | unvalidated | Approval records / tooling |
| H3 | Requirement ambiguity (metric, groups, lighting, devices) is resolved informally and not versioned | unvalidated | Change tickets |
| H4 | Device-cohort coverage gaps are not visible at release time | unvalidated | Dataset cards vs device mix |
| H5 | Post-release monitoring cannot attribute regressions to configuration changes quickly | unvalidated | Incident timelines |
| H6 | Evidence used in decisions is not traceable to versioned source sections | unvalidated | Review packets |
| H7 | The proposed workflow duplicates existing tooling | unvalidated | Tool inventory (Q12) |

## Pilot definition

| Item | Proposal |
|---|---|
| Scope | One model (a shade matcher), one change type (preprocessing/config change), one deployment target |
| Dataset | An agreed, consented, licensed evaluation set with a documented grouping protocol and label protocol; held-out split under access control |
| Reviewers | Named, authorized domain, privacy, QA and release reviewers |
| Baseline workflow | Measure the current process for 2–3 comparable changes before the pilot |
| Integrations | Read-only first: model registry, dataset storage, CI results, identity (SSO). Deployment and incident writes stay disabled until authorized |
| Success measures | Defined before the pilot (see METRICS.md): regressions caught before release, reviewer time per change, rework cycles, clarification cycles, approval turnaround, and reviewer-rated evidence completeness |
| Exit criteria | Stakeholders confirm or reject H1–H7; a go/no-go decision on integration with existing tools |
