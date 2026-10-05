# NorthStar Health Benefits — Claims Operations Manual (2026)
Document-ID: NSHB-OPS-CLM-2026
Version: 2026.1

> SYNTHETIC DEMO DATA — NOT FOR REAL CLAIM ADJUDICATION. Fictional operations manual.

## O-01 Adjudication Principles

### O-01.1 Deterministic Adjudication
All claim determinations are produced by the versioned, deterministic rules engine. Every determination records a reason code, the rule identifier and the ruleset version that produced it.

### O-01.2 Reason Codes
Standard reason codes are PAID, PAID_CAPPED, MEMBER_INELIGIBLE, POLICY_NOT_EFFECTIVE, PROVIDER_INELIGIBLE, NOT_COVERED, DUPLICATE, VISIT_LIMIT_EXCEEDED, AUTH_REQUIRED and BENEFIT_MAX_REACHED.

## O-05 Overrides and Human Review

### O-05.1 Manual Overrides
Manual overrides of claim determinations require a claims supervisor role and are recorded in the audit log with the reason for the override.

### O-05.2 Reprocessing
Bulk reprocessing of claims after a defect correction requires approval from the claims operations manager and the release manager.

## O-08 Release Management

### O-08.1 Rule Changes
Changes to adjudication rules must be traceable to an approved business requirement and policy section, must pass the regression suite and claims simulation, and require release manager approval before deployment.

### O-08.2 Post-Release Monitoring
After every rule release, denial rates by benefit and reason code are monitored against the approved simulation projection for at least 8 weeks.
