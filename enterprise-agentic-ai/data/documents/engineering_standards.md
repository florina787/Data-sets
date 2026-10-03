# Engineering Standards

> SYNTHETIC DATA — NovaGrid Corp is a fictional company. All names, figures and events are invented for demonstration purposes.

- Document owner: Engineering Excellence Group
- Version: 4.1
- Effective date: 2026-01-15

## Purpose

These standards define the minimum engineering quality bar for all NovaGrid product teams. Exceptions require written approval from the Engineering Excellence Group.

## Code Quality

- All production services must maintain at least 80 percent automated test coverage.
- Every change requires at least one peer review before merge.
- Static analysis and dependency vulnerability scanning must pass in the CI pipeline.

## Release Management

- Code freeze occurs at least 10 business days before a production release.
- A release may not proceed with any open issue marked as a release blocker.
- A go/no-go review must be held no later than five business days before release.
- Rollback plans must be documented and rehearsed for every major release.

## Delivery Performance Targets

- Deployment frequency: at least weekly for each production service.
- Lead time for changes: under five days.
- Change failure rate: below 15 percent.
- Mean time to restore service: under four hours.
- Sprint predictability: teams should complete at least 85 percent of planned story points.

## Security and Secrets

- Credentials, API keys and tokens must never be committed to source control.
- Secrets are loaded from the secrets manager or environment variables at runtime.
- Personal data must be masked in logs and in AI-generated outputs.

## AI System Standards

- AI-generated answers must cite the evidence they are based on.
- Answers that cannot be grounded in evidence must clearly state that more information is required.
- Every AI request must be traceable with a request ID, latency and token usage.
