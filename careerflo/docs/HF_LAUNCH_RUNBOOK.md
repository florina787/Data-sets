# Launch runbook — each step needs the owner's go-ahead

Nothing in this runbook has been executed. Steps that create accounts, cost money or make the app public are marked 🔐.
Commands run from `careerflo/` unless stated.

## 0. Preconditions
- CI green on the commit you will deploy (`Career_flo AI CI`: backend SQLite+PostgreSQL+stripe-mock, frontend, gitleaks,
  e2e, space-image).
- Decide the architecture (`HF_DEPLOYMENT_ARCHITECTURE.md`). Recommended: **B** (beta) → **C** (paying customers).

## 1. 🔐 Supabase project
1. Create the project (Free for the private beta; **Pro before paying customers**).
2. Auth → Email: enable *Confirm email*; set Site URL to your app URL; configure SMTP (custom SMTP is recommended for volume).
3. Apply the schema + RLS from your machine:
   ```bash
   cd backend && DATABASE_URL='postgresql://…' uv run alembic upgrade head
   ```
4. Note: `SUPABASE_URL`, anon key (public), connection string (secret).

## 2. Verify RLS on the real project (SQL editor)
```sql
select count(*) from pg_policies where schemaname = 'public';   -- expect 37
select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
 where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity;  -- expect no rows
```

## 3. 🔐 Stripe (TEST mode)
Products Pro CA$9.99 / Premium CA$19.99 monthly → `STRIPE_PRICE_PRO`, `STRIPE_PRICE_PREMIUM`; enable Stripe Tax if needed;
Customer Portal (cancel, switch plans, proration); webhook endpoint `https://<api-host>/api/webhooks/stripe` with
`checkout.session.completed`, `customer.subscription.created|updated|deleted`, `invoice.paid`, `invoice.payment_failed`,
`charge.refunded` → `STRIPE_WEBHOOK_SECRET`. Keep `STRIPE_ALLOW_LIVE=false`.

## 4. Verify a real test-mode checkout (before inviting anyone)
```bash
stripe listen --forward-to https://<api-host>/api/webhooks/stripe   # or the dashboard webhook
```
Register → Pricing → Choose Pro → card 4242 4242 4242 4242 → the success page must show "Confirming payment…" until the
webhook arrives, then the plan becomes Pro. Then: cancel in the portal → `cancel_at_period_end`; simulate a failed
payment (card 4000 0000 0000 0341) → Alerts tab shows it.

## 5. 🔐 API + Qwen host
**Architecture B/C (recommended) — VPS:**
```bash
python3 scripts/hf_deploy.py --stage-only --out .hf-staging       # build context + secret scan
cd deploy/vps && cp ../hf-space/space.env.example .env              # fill real values (never commit)
DOMAIN=api.example.com docker compose up -d --build
curl https://api.example.com/api/health/ready                        # expect "status":"ok"
```
**Architecture A — Docker Space (requires HF PRO):**
```bash
export HF_TOKEN=…   # fine-grained, write access to this Space only
backend/.venv/bin/python scripts/hf_deploy.py --space OWNER/careerflo                       # dry run
backend/.venv/bin/python scripts/hf_deploy.py --space OWNER/careerflo --apply --sync-secrets # private Space
```
Then open the Space logs and `GET /api/health/ready`. **If `database.ok` is false, the port is blocked — stop here and
use the VPS path** (or ask HF support for a 5432/6543 exception).

## 6. 🔐 Frontend on a free Static Space (architecture B)
```bash
VITE_API_URL=https://api.example.com VITE_SUPABASE_URL=https://<ref>.supabase.co VITE_SUPABASE_ANON_KEY=<anon> \
HF_TOKEN=… backend/.venv/bin/python scripts/hf_deploy.py --target static-frontend --space OWNER/careerflo-web --apply
```
Set `CORS_ORIGINS=https://<owner>-careerflo-web.static.hf.space` (or your domain) on the API and restart it.
(Architecture C: skip — the container already serves the frontend.)

## 7. Smoke test the deployment
```bash
cd frontend && E2E_BASE_URL=https://<app-url> E2E_SUPABASE=1 npx playwright test   # journeys 1–10
backend/.venv/bin/python scripts/load_test.py --base https://<api-host> --users 5 --chats 1  # only with REGISTER_LIMIT_PER_HOUR raised temporarily, or skip
```
Check `/app/ops` (admin): readiness ok, error rate ≈ 0, Qwen TTFT/tok/s plausible.

## 8. 🔐 Go public
`scripts/hf_deploy.py … --visibility public` (or protected) / point DNS. Announce only after steps 1–7 pass.

## 9. Before charging customers
Supabase Pro (backups) · privacy policy + retention (resumes, applications, chats: define retention; automate account
deletion) · terms of service · support email · uptime monitor on `/api/health/ready` · incident/restore drill from a
Supabase backup · job-provider commercial licences · 🔐 Stripe live keys **only after written approval**, then set
`STRIPE_ALLOW_LIVE=true`.

## Rollback
```bash
backend/.venv/bin/python scripts/hf_rollback.py --space OWNER/careerflo --list
HF_TOKEN=… backend/.venv/bin/python scripts/hf_rollback.py --space OWNER/careerflo --to <space_commit> --apply
# or redeploy a git tag:  scripts/hf_deploy.py --space OWNER/careerflo --git-ref v0.4.0 --apply
```
GitHub: *Actions → "Career_flo AI → roll back Hugging Face Space"* (manual, approval-gated). VPS: `docker compose` with
the previous staging artifact (`careerflo-space-<sha>.tgz` from CI) — `tar xzf` into `.hf-staging` and `up -d --build`.
Database migrations are forward-only: take a Supabase backup before deploying a migration.
