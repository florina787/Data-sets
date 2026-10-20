#!/usr/bin/env bash
# Backup & restore drill against the docker compose stack: pg_dump -> restore into a fresh database -> verify
# row counts for every table and the audit hash chain on the restored copy. Exits non-zero on any mismatch.
set -euo pipefail
cd "$(dirname "$0")/.."
TS=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p var/backups
docker compose exec -T postgres pg_dump -U flo -d flo -Fc > "var/backups/flo-$TS.dump"
echo "backup: var/backups/flo-$TS.dump ($(du -h var/backups/flo-$TS.dump | cut -f1))"
docker compose exec -T postgres psql -U flo -d postgres -qc "DROP DATABASE IF EXISTS flo_restore" -c "CREATE DATABASE flo_restore"
docker compose exec -T postgres pg_restore -U flo -d flo_restore --no-owner < "var/backups/flo-$TS.dump"
q() { docker compose exec -T postgres psql -U flo -d "$1" -Atc "$2"; }
fails=0
for t in $(q flo "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1"); do
  a=$(q flo "SELECT count(*) FROM \"$t\""); b=$(q flo_restore "SELECT count(*) FROM \"$t\"")
  if [ "$a" != "$b" ]; then echo "MISMATCH $t: $a vs $b"; fails=1; fi
done
echo "row counts: $([ $fails = 0 ] && echo identical || echo MISMATCH)"
docker compose exec -T -e FLO_AUDIT_DATABASE_URL=postgresql+psycopg://flo:${POSTGRES_PASSWORD:-flo-demo}@postgres:5432/flo_restore api \
  python -c "from governance.audit import verify_chain; r=verify_chain(); print('restored audit chain:', r); raise SystemExit(0 if r['valid'] else 1)"
docker compose exec -T postgres psql -U flo -d postgres -qc "DROP DATABASE flo_restore"
[ $fails = 0 ] && echo "DRILL PASSED $TS" || { echo "DRILL FAILED"; exit 1; }
