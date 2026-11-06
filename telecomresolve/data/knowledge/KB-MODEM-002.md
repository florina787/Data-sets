---
id: KB-MODEM-002
title: HX-series modem indicator and reboot reference
version: "1.4"
doc_type: guide
authority: guide
product: home_internet
tenant_scope: "*"
allowed_roles: [specialist, network_analyst, field_coordinator, supervisor, auditor]
effective_date: "2026-06-15"
---
SYNTHETIC DOCUMENT for fictional HX-series equipment.

## Indicator lights
Power solid: modem has power. All lights off then on again: the modem restarted. DSL/Fibre light flashing: the modem is trying to establish the line connection. Internet light off: no data session.

## Unexpected reboots
An unexpected reboot is a restart not requested by the customer or a remote command. The cpe_unexpected_reboots counter increments on each one. Three or more unexpected reboots in 24 hours with healthy line metrics indicates a suspected equipment or power fault.

## Known firmware note
HX-200 firmware 3.1.0 has a synthetic known issue where overheating can trigger restarts. Ventilation and power checks are the approved first step before equipment replacement is considered.
