---
doc_id: ENG-INV
title: Inventory System Integration Standard (synthetic)
version: "1.4"
owner: Platform Engineering
effective: 2026-05-20
---
# Inventory System Integration Standard

## 1. Reservation API
Clients reserve stock with `POST /reserve` and an idempotency key, then confirm the reservation with `/commit` or release it with `/release`. A held reservation that is never committed expires automatically.

## 2. Idempotency
Retrying a reservation with the same key returns the original reservation.

## 3. Errors
`409` means insufficient stock and includes the SKU. Any `5xx` response is a dependency failure.

## 4. Timeouts and failure handling
Every client call must set an explicit timeout of 2 seconds or less. When a call times out or fails, checkout must fail closed. It must not create an order and must not skip the stock check. The customer must be shown a "temporarily unavailable" message, and their cart must be kept.
