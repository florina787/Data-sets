---
id: KB-DIAG-007
title: Diagnostic signal reference and recovery verification standard
version: "1.1"
doc_type: runbook
authority: runbook
product: home_internet
tenant_scope: "*"
allowed_roles: [specialist, network_analyst, field_coordinator, supervisor, auditor]
effective_date: "2026-09-01"
---
SYNTHETIC REFERENCE for an independent prototype.

## Freshness
Diagnostic samples older than 24 hours are stale. Stale samples may describe history but cannot support a current diagnosis.

## Signals
link_state (up/down), loss_of_signal_events (count per interval), link_retrains (count per interval), packet_loss_pct (percent), latency_ms (milliseconds), snr_margin_db (dB), crc_errors (count per interval), cpe_uptime_s (seconds), cpe_unexpected_reboots (count per interval).

## Recovery verification
Recovery is verified only when at least 4 fresh samples collected after the action, spanning a 30 minute observation window, are all healthy: link up, no loss of signal, no retrains, packet loss at or below 1 percent, no unexpected reboots. Missing samples never count as healthy. A customer report that conflicts with telemetry keeps the case open.
