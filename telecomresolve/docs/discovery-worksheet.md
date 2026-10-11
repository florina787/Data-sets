# Discovery worksheet and gap-validation matrix (for Bell Canada stakeholder conversations)

## Boundaries

- This is an independent prototype on synthetic data. It does not use, and does not claim access to, Bell
  systems, data, policies, network topology or models, and it does not use Bell branding or imply sponsorship.
- Nothing here asserts that Bell lacks orchestration, governance or any integration. The point of discovery is
  to find out what already exists.
- All policy values in the prototype are configurable synthetic rules, not Bell policies.

## Public context (accessed 9 October 2026)

- Bell Contact Centre AI Services:
  https://business.bell.ca/shop/medium-large/contact-centre/ai-services
- Bell and ServiceNow expanded multi-year strategic agreement, 18 July 2024:
  https://newsroom.servicenow.com/press-releases/details/2024/Bell-Canada-and-ServiceNow-announce-expanded-multi-year-strategic-agreement-to-accelerate-Bells-digital-transformation-and-leadership-in-AI-powered-solutions-07-18-2024-traffic/default.aspx

These show public investment in contact-centre AI and in network, customer and field-service operations on
ServiceNow. They support choosing this domain; they do not establish a gap.

## Hypothesis

Investigators could benefit from a unified, evidence-backed workflow that connects recurring complaints with
network conditions, earlier interventions and resolution outcomes.

## Discovery questions

| # | Question | Who to ask | What a useful answer looks like | Answer | Owner | Status |
|---|---|---|---|---|---|---|
| 1 | Which existing platforms already correlate incidents, account history and service-to-network mapping? | Network ops, ITSM platform owner | Named systems, which joins they do, latency | | | Open |
| 2 | Where do specialists still switch systems or collect evidence by hand? | Contact-centre team leads, specialists (observation) | Screen-switch counts, time per case, which lookups | | | Open |
| 3 | Which recurring issue creates measurable repeat contacts or avoidable dispatches? | Operations analytics | Volume, repeat-contact rate, no-fault-found dispatch rate | | | Open |
| 4 | Which actions may be automated, which need approval, and who owns that decision? | Operations leadership, risk, legal | Action list with owner and approval level | | | Open |
| 5 | What data can be accessed, with what freshness, permissions and retention? | Data governance, privacy | Field-level access list, freshness SLAs, retention periods | | | Open |
| 6 | How would this integrate with existing ServiceNow and contact-centre investments (extend vs. build alongside)? | Platform architecture | Preferred integration points, constraints | | | Open |
| 7 | What baseline and controlled pilot would show incremental value? | Analytics, finance | Agreed metrics, baseline period, control group design | | | Open |
| 8 | Where must data and model inference be hosted? | Privacy, security | Region requirements per component | | | Open |

## Gap-validation matrix

| Hypothesised need | Current capability (to be confirmed) | Evidence collected | Owner | Status |
|---|---|---|---|---|
| Single view joining complaint, account history, service mapping and incidents | Unknown — may already exist in ITSM/CRM | — | TBD | Not validated |
| Mapping-based (not proximity-based) incident association | Unknown | — | TBD | Not validated |
| Visibility of earlier interventions to avoid repeating failed steps | Unknown | — | TBD | Not validated |
| Cited, evidence-sufficiency-labelled diagnosis with abstention | Unknown | — | TBD | Not validated |
| Approval bound to exact payload, policy version and evidence | Unknown — may exist in workflow engine | — | TBD | Not validated |
| Recovery verified from subsequent telemetry before closure | Unknown | — | TBD | Not validated |
| Replayable audit of AI-assisted decisions | Unknown | — | TBD | Not validated |

## Choosing a pilot

Only after the answers above: pick one recurring issue with measurable repeat contacts, a single region, read-only
integrations first, and a control group. Write actions (dispatch, messaging) come later and behind the existing
approval owners.
