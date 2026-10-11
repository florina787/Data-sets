---
doc_id: POL-REL-005
version: 2.1
title: Beauty AI Release Policy (demo)
status: approved
effective_date: 2026-05-01
owner_role: release_manager
access: all
---
DEMO DOCUMENT — illustrative release rules for a prototype. These are not L'Oréal standards or scientifically established thresholds.

## §1 Release gates
Release requires: at least 100 eligible samples in every required evaluation cell; no required cell losing more than 2 percentage points of top-1 accuracy against baseline; the target cell improving by at least 5 percentage points; all privacy and authorization control tests passing; no unresolved required ambiguity; current, digest-matched evaluation evidence. Insufficient data yields INCONCLUSIVE, never PASS.

## §2 Separation of duties
The release approver must differ from the developer who authored the candidate code revision. Code revisions require review by someone other than the author.

## §3 Approval binding
A release approval is bound to the requirement version, model artifact digest, code revision, dataset snapshot, evaluation configuration, policy version and deployment target. Any change invalidates it. Approvals expire after 72 hours and can be used once.

## §4 Rollout
Prototype rollout stages are 5%, 25% and 100% of simulated sessions. Promotion requires at least one monitoring window per stage without an open alert.

## §5 Rollback
In the prototype, rollback requires an authorized release-manager review. Automated production rollback would be a separately approved policy decision.
