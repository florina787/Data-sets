# Demo Walkthrough

All data is synthetic. Every facility name ends in "(Demo)", phone numbers use 555-01xx and booking links use the
reserved `.invalid` domain. Open the app, choose a demo account on the sign-in screen.

## A. Patient — "I need an MRI. My appointment is three months away."

1. Sign in as **Demo Patient** → **Ask Christina**.
2. Type: `I need an MRI. My appointment is three months away.` → Christina asks about the requisition and location.
3. `Yes, I have a requisition` → `Toronto. Search within 25 kilometres.`
4. Christina reports the earliest **verified** opening (Northgate MRI & CT Clinic (Demo), 5 days, ~14 km, 85 days
   sooner) and says how many other openings are advertised/unverified. The live agent workflow lights up node by node.
5. **View full results** → verified alternatives vs. unverified possibilities, wait-time comparison, map, requisition
   checklist and sources. Note: Bayfield Advanced Imaging (Demo) has a 3-day opening that is only *advertised* — it is
   never shown as confirmed.
6. **Prepare booking handoff** → consent → the workflow pauses at the Human Approval Agent → **Approve** → official
   booking instructions, marked **NOT CONFIRMED**. Appointment Tracker shows the handoff; "I booked this" records a
   self-report, which is still not a provider confirmation.

## B. Demo scenarios (Settings → Demo scenarios)

| # | Scenario | How |
|---|---|---|
| 1 | MRI long wait | as above |
| 2 | CT earlier appointment | Find Healthcare Services → CT, North York, 10 km |
| 3 | Blood test nearby | Blood Tests, `M5V`, 3 km |
| 4 | Specialist expanded radius | Specialist, Toronto, 5 km → approve the radius expansion prompt |
| 5 | Provider API failure | Settings → "Provider API failure", then search MRI Toronto 25 km: Recovery Agent retries, opens the breaker and marks INT-SYN-NORTH unavailable; Northgate shows UNKNOWN + contact details |
| 6 | No eligible appointment | Mammography, Toronto, 2 km → expansion offered |
| 7 | Requisition not accepted | in MRI results, Lakeshore Health Network Imaging (Demo) is INELIGIBLE for a standard requisition (see checklist) |
| 8 | AI-SDLC defect detection | sign in as Demo Engineer → AI-SDLC Command Center (below) |
| 9 | Human approval workflow | Human Approval Center (patients see their own; approvers see releases) |
| 10 | Production anomaly simulation | QA & Test Center → simulate build 1.5.0, then Production Monitoring → Run detection |

Emergency check: type `I have chest pain` — the search is interrupted immediately with 911 / Health811 guidance.

## C. AI-SDLC — the 90-Day MRI Wait-Time Challenge

1. **Demo Engineer** → AI-SDLC Command Center → *Start the challenge* (simulation volume configurable).
2. Stage 2 detects: *"Does an earlier slot qualify if the facility cannot accept the patient's requisition?"* — the run
   pauses. Record the product-owner decision.
3. Stages 4–12 run: architecture (Mermaid), development (build 1.4.0), QA (29 scenarios, all pass), baseline simulation,
   **controlled defect** (build 1.5.0 deployed to demo-production), monitoring detects `VERIFICATION_MISCLASSIFICATION`
   and `UNVERIFIED_AS_CONFIRMED`, RCA confirms the status-mapping change with diff + failing tests + traces, fix proposal
   (1.5.1), regression (passes on 1.5.1, fails on 1.5.0), security scan.
4. Stage 13 waits for a **different** user with release authority: sign out, sign in as **Demo Release Approver**,
   approve. Stages 14–15 deploy (simulated) and confirm the defect is absent in post-release traffic.
5. Tabs show monitoring, root cause, fix diff, release checklist and the full traceability chain REQ → ARCH → CODE → TEST → REL → MON.

While 1.5.0 is active, patient searches really use the defective mapping (search results show the build number) —
that is the point of the demonstration. `Administration → Reset demo` restores 1.4.0.

## Screenshots (captured by the Playwright suite)

![Search results](screenshots/results-desktop.png)
![Christina on mobile](screenshots/christina-mobile.png)
![Booking handoff approval](screenshots/booking-handoff.png)
![AI-SDLC root cause](screenshots/sdlc-complete.png)
