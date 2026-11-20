# Deployment guide

**Status: local development only.** No production deployment has been done and none is configured. No paid service is required or activated.

| Setting (env) | Default | Notes |
|---|---|---|
| `FLOROME_DATABASE_URL` | `sqlite:///./florome.db` | PostgreSQL: `postgresql+psycopg://...`, then `pip install -e ".[postgres]"`. Not yet tested against PostgreSQL. |
| `FLOROME_DEFAULT_MODE` | `demo` | `live` disables demo seeding. Live login needs OIDC, which is not implemented yet. |
| `FLOROME_GITHUB_REPOSITORY`, `FLOROME_GITHUB_TOKEN` | unset | Enables `POST /api/v1/connections/github`. Use a fine-grained token on a non-production repository. |
| `FLOROME_MCP_ALLOWLIST_EXTRA` | `[]` | JSON list of `name=python.module` entries |

Production prerequisites are listed in PRODUCTION_READINESS.md: OIDC, a secrets manager, Alembic migrations, a worker queue for long executions, OpenTelemetry export and HTTP rate limits.
