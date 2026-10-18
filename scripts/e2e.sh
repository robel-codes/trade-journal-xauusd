#!/usr/bin/env bash
# End-to-end run against a throwaway database and alternate ports.
# Requires: a reachable Postgres where $PG_ADMIN_URL can create databases; frontend built (pnpm build).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_ADMIN_URL="${PG_ADMIN_URL:-postgresql://xau:xau@localhost:5432/postgres}"
DB=xau_lab_e2e
API_PORT=${API_PORT:-8100}
WEB_PORT=${WEB_PORT:-3100}
export XAU_DATABASE_URL="postgresql+psycopg://xau:xau@localhost:5432/$DB"
export XAU_SECRET_KEY="e2e-secret-key-not-for-production-0001"

psql "$PG_ADMIN_URL" -qc "drop database if exists $DB" -c "create database $DB owner ${DB_OWNER:-xau}"
cd "$ROOT/backend"
uv run alembic upgrade head
uv run python -m app.cli bootstrap --email trader@example.com --name "Gold Trader" --password 'e2e-password-123'
uv run uvicorn app.main:app --port "$API_PORT" >/tmp/xau-e2e-api.log 2>&1 &
API_PID=$!
cd "$ROOT/frontend"
API_URL="http://localhost:$API_PORT" pnpm exec next start -p "$WEB_PORT" >/tmp/xau-e2e-web.log 2>&1 &
WEB_PID=$!
trap 'kill $API_PID $WEB_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 40); do curl -sf "localhost:$WEB_PORT/login" >/dev/null && curl -sf "localhost:$API_PORT/api/health" >/dev/null && break; sleep 0.5; done
E2E_BASE_URL="http://localhost:$WEB_PORT" pnpm exec playwright test "$@"
