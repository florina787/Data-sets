# Delivery Risk Report — Q4 2026 Portfolio

> SYNTHETIC DATA — NovaGrid Corp is a fictional company. All names, figures and events are invented for demonstration purposes.

- Document owner: Elena Varga, Head of Delivery
- Report date: 2026-09-30
- Scope: Project Phoenix, Project Atlas and Project Orion

## Executive Summary

The Q4 portfolio carries five major delivery risks. The highest-rated risk is the Project Phoenix October release, where three open blockers, falling velocity and a performance gap threaten the 2026-10-28 production date.

Project Atlas is on track. Project Orion is RED because of a critical dependency on an offline-sync library that has not passed security review.

## Major Delivery Risks

### RISK-01: Phoenix release blockers (High likelihood, High impact)

Three release blockers (PHX-214, PHX-221, PHX-230) remain open less than four weeks before release. If they are not resolved by 2026-10-07, code freeze will slip and the release date is at risk. Mitigation: daily blocker stand-up and vendor escalation for the payment gateway.

### RISK-02: Declining Phoenix sprint velocity (High likelihood, Medium impact)

Phoenix velocity fell from 47 story points in Sprint 19 to 38 story points in Sprint 21. Unplanned production support work consumed roughly 20 percent of team capacity. Mitigation: ring-fence capacity and route support tickets to the platform on-call rotation.

### RISK-03: Assistant API performance gap (Medium likelihood, High impact)

Load testing shows p95 latency of 2.8 seconds against a 1.5 second target. Mitigation: parallelise retrieval and tool calls, add response caching and bring in two performance engineers.

### RISK-04: Key-person dependency on SSO expertise (Medium likelihood, Medium impact)

Only one engineer, Tomas Lindqvist, has deep knowledge of the identity provider integration. Mitigation: pair a second engineer on PHX-221 and document the token refresh flow.

### RISK-05: Orion offline-sync library security review (High likelihood, High impact)

Project Orion depends on an offline-sync library that failed its first security review. Mitigation: evaluate an alternative library and agree a revised plan with the steering committee by 2026-10-15.

## Risk Trend

- Phoenix overall risk trend: worsening since the previous report.
- Atlas overall risk trend: stable.
- Orion overall risk trend: worsening.

## Recommendations

- Treat the Phoenix release blockers as the top portfolio priority this week.
- Reduce unplanned work for the Phoenix team by at least 50 percent.
- Approve temporary performance engineering support for Phoenix.
- Schedule a steering committee decision on Orion scope by 2026-10-15.
