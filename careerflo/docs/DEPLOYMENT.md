# Deployment guide

> Nothing has been deployed. No paid cloud resources, live Stripe keys or DNS have been created. Every step below needs your accounts and your explicit go-ahead.

## 1. Supabase (database + auth)
1. Create a project. Copy the **connection string** (session pooler, port 5432), the **project URL** and the **anon key**.
2. Auth → Providers → Email: turn on **Confirm email**. Auth → URL configuration: set the site URL to your app URL.
3. Run the migrations from your machine: `cd backend && DATABASE_URL=... uv run alembic upgrade head`. This creates 41 tables and the RLS policies. The backend connects with the database owner role, which bypasses RLS; the policies protect direct client access.

## 2. Stripe (test mode)
1. In **test mode**, create two products with monthly CAD prices: Pro 9.99 and Premium 19.99. Put the price IDs in `STRIPE_PRICE_PRO` and `STRIPE_PRICE_PREMIUM`.
2. Turn on Stripe Tax if you need GST/HST. Checkout sends `automatic_tax`.
3. Configure the Customer Portal: allow cancellation and switching between the two prices, with proration.
4. Add a webhook endpoint `https://<api-host>/api/webhooks/stripe` for `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed` and `charge.refunded`. Put its signing secret in `STRIPE_WEBHOOK_SECRET`.
5. Local testing: `stripe listen --forward-to localhost:8000/api/webhooks/stripe`, then pay with card `4242 4242 4242 4242`.
6. Going live means swapping in live keys **and** setting `STRIPE_ALLOW_LIVE=true`. Without that flag the backend refuses `sk_live_` keys.

## 3. Backend + Qwen on one VM (e.g. Oracle Cloud Always Free Ampere A1, if eligible)
Ampere A1 is ARM64, and the Ollama and Python images used here are multi-arch.
```bash
git clone <repo> && cd careerflo
cp .env.example .env      # fill in values
docker compose up -d --build
```
- `ollama` is not published to the host. Only the `api` container can reach it.
- Put Caddy or nginx with TLS in front of `web:8080`, or use a Cloudflare Tunnel.
- Choose the model with `LLM_MODEL`. See [BENCHMARK.md](BENCHMARK.md).

## 4. Frontend on Cloudflare Pages (optional, instead of the `web` container)
Build command `npm run build`, output `dist`, root `careerflo/frontend`. Set `VITE_API_URL=https://<api-host>`, `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. Add the Pages origin to `CORS_ORIGINS`. Vercel Hobby is non-commercial, so don't use it here.

## 5. Production checks
- `GET /api/health` and `GET /api/system/llm` (`ok: true`, model loaded).
- Register a user, confirm the email, run a job search, and check `/api/usage` (1 of 2 left).
- Complete a test checkout. The plan must change **only after** the webhook arrives; watch the success page poll.
- Check that `/api/admin/metrics` returns 403 for a normal user.

## Hosting terms to confirm before launch
Check the current Oracle Always Free eligibility and acceptable-use terms, the Cloudflare Pages commercial terms, the Supabase plan limits, and each job provider's commercial-use terms and quotas (JSearch/RapidAPI, Adzuna, the Greenhouse/Lever/Ashby public board APIs).
