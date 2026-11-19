# Florome Shield: baseline audit

Recorded 2026-11-19, before any Shield code was added. Every capability below was re-verified by running it, not by reading the README.

## Architecture inventory (verified)

| Component | Location | Size |
|---|---|---|
| FastAPI backend | `florome/backend/florome/` | 3,471 Python lines |
| React frontend | `florome/frontend/src/` | 2,019 TS/TSX lines |
| Project A (unchanged) | `conversation-intelligence-copilot/` | n/a |
| Project B (unchanged, served via adapter) | `archai-enterprise-advisor/` | n/a |
| CI | `.github/workflows/florome-ci.yml`, `cic-ci.yml` | n/a |

## Test results

| Suite | Result |
|---|---|
| Florome backend (`pytest`) | **64 passed** |
| Florome frontend (`vitest`) | **12 passed**, `tsc` clean |
| Project A | 163 passed, 2 failed (pre-existing; see EXISTING_CAPABILITY_AUDIT.md) |
| Project B | 76 passed |

## Verified working capabilities (must remain unchanged)

Simulated multi-cloud incident, evidence RCA with competing hypotheses, timeline, remediation planning, approval by someone other than the creator, approval bound to plan hash, nonce replay protection, expiry, emergency stop, resumable execution, business-recovery validation, read-only MCP gateway with quarantine and schema pinning, hash-chained audit, tenant isolation, the React UI. Each is covered by the tests listed in TEST_EVIDENCE.md.

## Security scan of Florome itself (first real use of the Shield toolchain)

| Tool | Target | Result | Disposition |
|---|---|---|---|
| Bandit 1.9.4 | backend | B613: literal bidirectional/zero-width characters in `security/injection.py` (inside a regex) | **Confirmed, low severity, fixed.** Replaced with escape sequences; same behaviour, verified by test |
| Bandit 1.9.4 | backend | B105 "hardcoded password: 'probable'" | **Disproven:** an RCA status string |
| Trivy 0.76.2 | `frontend/package-lock.json` | echarts 5.6.0 CVE-2026-45249 (medium, fixed in 6.1.0); react-router 6.30.6 CVE-2026-53666 and CVE-2026-53669 (medium, fixed in 7.18.0) | **Open.** Fixes require major upgrades; tracked in PRODUCTION_READINESS.md |
| Trivy 0.76.2 | `backend/pyproject.toml` | 0 findings | **Not meaningful:** dependencies are unpinned (no lockfile), so there is nothing exact to match |

## Security gaps before Shield

* Authentication is demo bearer tokens only; no OIDC/SAML.
* No signed plans; integrity relies on the plan hash stored in the same database.
* No HTTP rate limiting or resource quotas.
* No isolation boundary for running untrusted code; nothing in Florome executed code before Shield.
* The MCP gateway has no server-level manifest pin and no emergency revocation.
* No agent runtime containment.
* Python dependencies are unpinned, so supply-chain scanning is impossible.

## Migration risks

* Shield adds tables to the same SQLAlchemy metadata: `create_all` is additive, but there are no Alembic migrations yet.
* Shield runs scanners as subprocesses: their binaries must be present, and Shield must fail closed and visibly when they are missing.
* Running verification code requires Linux namespaces (`unshare -n`). This works in this container but not in every deployment.
