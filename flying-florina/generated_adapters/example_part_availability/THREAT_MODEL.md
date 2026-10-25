# Threat model - part availability adapter (generated, synthetic)

| Asset | Threat | Mitigation in this bundle | Residual risk |
|---|---|---|---|
| Inventory data (INTERNAL) | Unauthenticated read | HMAC demo token: signature, audience, expiry, scope checked per request | Demo HMAC secret; use enterprise IdP (OIDC/JWT) in production |
| Legacy DB | SQL injection | Strict part-number regex; parameter compared, never interpolated; read-only view only | Production view permissions must be verified by DBA |
| Legacy DB | Writes via adapter | No write routes (tested); MCP exposes one read tool | Gateway must also block non-GET |
| User identity | Token passthrough to upstream | User token verified at adapter and never forwarded; backend uses a service credential | Service credential custody |
| Availability | Large result sets / slow backend | Pagination with max limit 50; backend timeout -> 504 | No rate limiting here: add at the gateway |
| Agents | Tool abuse / tool spoofing | Single read tool; scope check per invocation; tool pinned in caller allowlist | MCP is not the security boundary |
| Logs | Secret leakage | Logs contain request id, path, status, latency only | Upstream logs out of scope |
| Network | SSRF | Adapter accepts no URLs; backend is a fixed module | Production endpoint must be allowlisted |
