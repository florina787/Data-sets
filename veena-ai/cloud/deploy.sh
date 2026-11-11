#!/usr/bin/env bash
# Deploy, back up or roll back a VEENA Worker (insights | billing). Run from veena-ai/cloud.
# Nothing happens without an explicit confirmation word, so it can't be run by accident.
#
#   ./deploy.sh plan     billing                       # dry run: config checks + tests, deploys nothing
#   ./deploy.sh migrate  billing  I-APPROVE-MIGRATE    # apply migrations/*.sql to the remote D1 database
#   ./deploy.sh deploy   billing  I-APPROVE-DEPLOY     # tests, backup, then wrangler deploy
#   ./deploy.sh backup   billing                       # export the D1 database to backups/<name>-<time>.sql
#   ./deploy.sh rollback billing  I-APPROVE-ROLLBACK   # previous Worker version (wrangler rollback)
#   D1 point-in-time restore (7 days on the Free plan):
#     wrangler d1 time-travel restore <db> --timestamp=<unix time>
set -euo pipefail
cmd="${1:-}"; svc="${2:-}"; ok="${3:-}"
[[ "$svc" == "insights" || "$svc" == "billing" ]] || { echo "service must be insights or billing" >&2; exit 2; }
cd "$(dirname "$0")/$svc"
db="veena-$svc"
need() { [[ "$ok" == "$1" ]] || { echo "refusing: pass $1 to confirm (owner approval required)" >&2; exit 3; }; }
check() {
  [[ -f wrangler.toml ]] || { echo "copy wrangler.example.toml to wrangler.toml first" >&2; exit 4; }
  grep -q "REPLACE_AFTER" wrangler.toml && { echo "fill database_id in wrangler.toml" >&2; exit 4; }
  if [[ "$svc" == "billing" ]] && grep -Eq '^ALLOW_LIVE *= *"yes"' wrangler.toml; then echo "refusing: ALLOW_LIVE is set" >&2; exit 5; fi
  node --no-warnings --test test/*.test.mjs
}
case "$cmd" in
  plan) check; echo "plan OK: nothing deployed" ;;
  backup) mkdir -p ../backups; out="../backups/$db-$(date -u +%Y%m%dT%H%M%SZ).sql"; npx wrangler d1 export "$db" --remote --output "$out"; echo "backup: $out" ;;
  migrate) need I-APPROVE-MIGRATE; check; npx wrangler d1 migrations apply "$db" --remote ;;
  deploy) need I-APPROVE-DEPLOY; check; "$0" backup "$svc" || echo "backup skipped (first deploy?)"; npx wrangler deploy ;;
  rollback) need I-APPROVE-ROLLBACK; npx wrangler rollback ;;
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
