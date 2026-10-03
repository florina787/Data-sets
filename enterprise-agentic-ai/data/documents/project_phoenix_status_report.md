# Project Phoenix Status Report

> SYNTHETIC DATA — NovaGrid Corp is a fictional company. All names, figures and events are invented for demonstration purposes.

- Document owner: Maya Okafor, Engineering Manager
- Reporting period: 2026-09-15 to 2026-09-28
- Project ID: PRJ-PHOENIX
- Overall status: AMBER

## Executive Summary

Project Phoenix is the modernisation of the NovaGrid customer self-service portal onto the new AI Platform. The project is 68 percent complete and remains AMBER for the October release (Release 2026.10), which is scheduled for production on 2026-10-28.

Feature development for the conversational support assistant and the knowledge search experience is largely complete. The main concerns are the payment gateway integration, the SSO migration and a decline in sprint velocity over the last two sprints.

The team still targets code freeze on 2026-10-14, but this date is at risk unless the three release blockers are resolved by 2026-10-07.

## Milestones

- Discovery and architecture sign-off: completed on 2026-05-30.
- Conversational assistant MVP: completed on 2026-08-22.
- Knowledge search with semantic retrieval: completed on 2026-09-19.
- Payment gateway integration: in progress, 55 percent complete, blocked by vendor sandbox instability.
- SSO migration to the new identity provider: in progress, waiting on the security review.
- Code freeze: planned for 2026-10-14.
- Production release 2026.10: planned for 2026-10-28.

## Progress This Period

The team completed 38 story points against a plan of 46 story points in Sprint 21. Sprint 20 delivered 41 of 48 planned points.

Automated test coverage on the Phoenix services increased from 71 percent to 74 percent, still below the 80 percent engineering standard.

The knowledge search feature passed user acceptance testing with 92 percent of scenarios accepted on first run.

## Release Blockers

Three issues are currently marked as blocking the October release:

- PHX-214: Payment gateway sandbox returns intermittent timeout errors, preventing end-to-end checkout tests.
- PHX-221: SSO token refresh fails for federated enterprise accounts after 60 minutes.
- PHX-230: Load test shows p95 latency of 2.8 seconds on the assistant API against a 1.5 second target.

## Budget

The approved budget is 1.20 million USD. Spend to date is 0.86 million USD, which is 72 percent of budget at 68 percent completion. Budget status is GREEN but trending toward AMBER.

## Decisions Needed

- Approve two additional performance engineers for three weeks to address PHX-230.
- Confirm whether the SSO migration can ship behind a feature flag if the security review is not complete by 2026-10-10.
- Escalate the payment gateway sandbox instability to the vendor account executive.

## Next Steps

- Resolve PHX-214, PHX-221 and PHX-230 by 2026-10-07.
- Run a full regression cycle in the week of 2026-10-12.
- Hold a go/no-go review on 2026-10-21.
