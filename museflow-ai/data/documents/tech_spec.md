# Technical Specification — Approval Service (SYNTHETIC SAMPLE)

Version: 1.3
Author: Demo Dreamer
Last Updated: 2026-09-28
Latency Budget: 200 milliseconds

## Overview

The approval service pauses a workflow when a consequential action is proposed. It stores a checkpoint, notifies the user, and resumes the same workflow once a decision is recorded.

## Components

- Checkpoint store: keeps workflow state per session thread.
- Policy engine: decides whether an action requires approval using an allowlist.
- Audit log: records every decision in a hash-chained log.

## Interfaces

The service exposes resume(run_id, decision) where decision is approved, rejected or cancelled. Unknown decisions are rejected with a validation error.

## Security

Checkpoints are never shared between sessions. Inputs are validated against a schema. No secrets are stored in the client.

## Open Questions

- Should approvals expire after 24 hours?
- Should rejected workflows be replayable?
