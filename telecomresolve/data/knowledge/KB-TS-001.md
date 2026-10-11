---
id: KB-TS-001
title: Home internet disconnection troubleshooting guide
version: "3.0"
doc_type: guide
authority: guide
product: home_internet
tenant_scope: "*"
allowed_roles: [specialist, network_analyst, field_coordinator, supervisor, auditor]
effective_date: "2026-09-01"
---
SYNTHETIC DOCUMENT for an independent prototype. Not an operator's real procedure.

## Scope
Applies to recurring home-internet disconnections reported by residential customers on fixed-line access. Use this guide only after checking for an incident on the service's mapped network path.

## Step 1 - Modem power cycle
Ask the customer to power-cycle the modem once, unless fresh diagnostics already show a line impairment (KB-DSP-004 indicators): a power cycle does not repair a line fault. If a power cycle was already performed for the same symptom within the last 7 days and the symptom continued, do not repeat this step; record that it was already tried and move on.

## Step 2 - Power adapter and ventilation check
If diagnostics show unexpected modem reboots while the line metrics are healthy, ask the customer to confirm the original power adapter is firmly connected, the modem is not covered or near a heat source, and the modem is not plugged into a switched outlet or power bar. Unexpected reboots with healthy line metrics usually indicate a customer equipment or power issue rather than a line fault.

## Step 3 - Wi-Fi versus line connection
Ask whether wired devices also lose connection. If only Wi-Fi devices are affected and the line is stable, the symptom is likely in the home network, not the access line.

## When to stop customer troubleshooting
Stop customer troubleshooting and follow the dispatch prerequisites (KB-DSP-004) when fresh diagnostics show a line impairment and the customer has already completed the applicable steps above. Do not ask the customer to repeat steps that already failed.
