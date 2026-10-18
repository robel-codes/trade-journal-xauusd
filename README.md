# XAU Lab

A trading journal, Pine Script strategy library and (soon) backtesting and research platform for
XAUUSD. It is built for one trader first, with user scoping throughout so more users can be added.

> Results in this application are **historical, simulated, or actual journal results**, and are
> labelled as such. Nothing here predicts or guarantees future profitability.

## Status

| Phase | What works today |
|---|---|
| 1 Foundation | FastAPI + SQLAlchemy + Alembic on PostgreSQL, Argon2 sign-in with HttpOnly session cookie, settings (timezone, theme, DST-aware sessions), trading accounts, audit log, Next.js shell with dark and light themes, Overview computed from stored data with honest empty states |
| 2 Strategy library | Import of single files, batches and ZIPs; byte-exact storage and export; exact and near-duplicate detection; immutable versions, cloning, version diff; static compatibility analyzer with line-referenced findings; inputs and `strategy()` settings extraction; source viewer with syntax highlighting |
| 3 to 7 | Designed (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)) but not built. Their pages say so and show no figures. |

## Run locally

**New to this? Follow the step-by-step guide in [docs/SETUP.md](docs/SETUP.md)** (macOS, Windows and Linux). The short version for developers:

Requirements: Python 3.13 with [uv](https://docs.astral.sh/uv/), Node 22 with pnpm, PostgreSQL 16.

```bash
# 1. Database
createuser -P xau            # password: xau (or change XAU_DATABASE_URL)
createdb -O xau xau_lab

# 2. API
cd backend
cp ../.env.example .env      # then set XAU_SECRET_KEY to a long random value
uv sync
uv run alembic upgrade head
uv run python -m app.cli bootstrap --email you@example.com --name "Your Name"   # prompts for a password
uv run uvicorn app.main:app --reload --port 8000

# 3. Web (another terminal)
cd frontend
pnpm install
pnpm dev                     # http://localhost:3000, proxies /api to API_URL (default http://localhost:8000)
```

With Docker (not tested in the environment this was built in, which had no Docker daemon):

```bash
cp .env.example .env         # set XAU_SECRET_KEY
docker compose up --build
docker compose exec api uv run python -m app.cli bootstrap --email you@example.com
```

API docs: http://localhost:8000/api/docs

## Tests

```bash
cd backend && uv run pytest          # needs a database; defaults to postgresql://xau:xau@localhost:5432/xau_lab_test
cd backend && uv run ruff check app tests
cd frontend && pnpm exec vitest run && pnpm lint && pnpm exec tsc --noEmit
scripts/e2e.sh                       # builds nothing; run `pnpm build` in frontend first. Uses a throwaway DB and ports 8100/3100
```

Set `XAU_TEST_DATABASE_URL` to point the backend tests elsewhere, and `PW_CHROMIUM` to use an
already-installed Chromium for Playwright.

## Importing your strategies

Strategy Library → Import scripts. Drop any mix of `.pine`, `.txt` and `.zip` files (up to 300 files
per request, or one ZIP of up to 500 scripts). For each file you get one of:

* **Imported**, with its compatibility classification
* **New version**, when a strategy with the same declared title already exists (or choose "Create a separate strategy")
* **Duplicate**: byte-identical to something already stored
* **Near duplicate**: differs only in comments, whitespace or line endings
* **Error**: wrong type, not UTF-8, empty, too large, unsafe path inside the ZIP, nested archive

Scripts are never executed and never modified. "Export original" returns the exact bytes imported.

### What the compatibility classes mean

| Class | Meaning |
|---|---|
| Validated | A native adapter exists **and** it matches a TradingView Strategy Tester export in parity tests. The analyzer can never assign this by itself. |
| Partially supported | Every construct found is one the engine is designed to model. Still needs a reviewed translation. |
| Manual conversion | Uses constructs that need human decisions (lookahead without offset, `strategy.order`, `varip`, other symbols, unsupported built-ins, libraries, Pine ≤ v4…). |
| Not executable | Indicator or library, or depends on data the platform cannot reproduce (`request.financial`, `request.economic`…). |

## Layout

```
backend/
  app/models/        SQLAlchemy models (all timestamps UTC)
  app/pine/          scanner.py (masking, call parsing) and analyzer.py (rules, classification)
  app/analytics/     positions.py (fill-based P&L, R) and metrics.py (summary, drawdown, calendars)
  app/services/      strategy_import.py (decode, ZIP safety, dedupe, versions)
  app/api/           auth, settings, accounts, strategies, dashboard
  migrations/        Alembic
  tests/             pytest, hand-calculated fixtures in tests/fixtures/pine
frontend/
  src/app/(app)/     Overview, Strategy Library, strategy detail, Settings, roadmap pages
  src/app/api/       runtime proxy to the API (keeps the session cookie first-party)
  src/components/    UI kit, data table, equity chart, P&L calendar, Pine source viewer
  e2e/               Playwright workflows
docs/                ARCHITECTURE.md, METRICS.md
```
