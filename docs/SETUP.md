# Setting up and running XAU Lab

This guide takes you from a clean computer to XAU Lab running in your browser. It covers macOS, Windows and Linux.
Expect about 20–30 minutes the first time, and two terminal windows each time after that.

XAU Lab has three parts that run on your own machine:

| Part | What it is | Address |
|---|---|---|
| Database | PostgreSQL. Stores your strategies, accounts and trades | `localhost:5432` |
| API | Python (FastAPI). Does the analysis and calculations | http://localhost:8000 |
| Web app | Next.js. The screens you use | http://localhost:3000 |

You only ever open the web app. It passes requests to the API, and the API talks to the database.

---

## Part 1 — One-time installation

### Step 1. Install the tools

You need five things: **Git**, **uv** (manages Python for you), **Node.js 22**, **pnpm** and **PostgreSQL 16**.
You do not need to install Python yourself: `uv` downloads the right version (3.13) automatically.

**macOS** (with [Homebrew](https://brew.sh)):

```bash
brew install git node@22 postgresql@16
brew services start postgresql@16
curl -LsSf https://astral.sh/uv/install.sh | sh
corepack enable            # turns on pnpm, which ships with Node
```

If `node --version` doesn't show v22 afterwards, run `brew link --overwrite node@22`.

**Windows** (PowerShell):

1. Install Git: https://git-scm.com/download/win
2. Install Node.js 22 LTS: https://nodejs.org (use the installer and keep the defaults)
3. Install PostgreSQL 16: https://www.postgresql.org/download/windows/ . The installer asks for a password for the `postgres` superuser; write it down. Keep the default port, 5432.
4. Install uv:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
5. Turn on pnpm (in a PowerShell window opened **as Administrator**):
   ```powershell
   corepack enable
   ```
6. Close and reopen PowerShell so the new commands are found.

**Linux** (Ubuntu/Debian):

```bash
sudo apt update && sudo apt install -y git postgresql curl
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo corepack enable
```

**Check everything is installed** (open a new terminal first):

```bash
git --version
uv --version
node --version     # should start with v22
pnpm --version     # if it asks to download pnpm, answer yes
psql --version     # should say 16.x (on Windows, see the note below)
```

> **Windows:** if `psql` is "not recognized", add `C:\Program Files\PostgreSQL\16\bin` to your PATH
> (Start → "Edit the system environment variables" → Environment Variables → Path → New), then reopen PowerShell.

### Step 2. Download the code

```bash
git clone https://github.com/robel-codes/trade-journal-xauusd.git
cd trade-journal-xauusd
```

All later commands assume you start in this `trade-journal-xauusd` folder.

### Step 3. Create the database

This creates a database user called `xau` and a database called `xau_lab`. Pick your own password in place of `choose-a-password`.

**macOS** (Homebrew makes your login user the database superuser):

```bash
psql postgres -c "CREATE USER xau WITH PASSWORD 'choose-a-password' CREATEDB;"
psql postgres -c "CREATE DATABASE xau_lab OWNER xau;"
```

**Linux:**

```bash
sudo -u postgres psql -c "CREATE USER xau WITH PASSWORD 'choose-a-password' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE xau_lab OWNER xau;"
```

**Windows** (enter the `postgres` password from the installer when asked):

```powershell
psql -U postgres -c "CREATE USER xau WITH PASSWORD 'choose-a-password' CREATEDB;"
psql -U postgres -c "CREATE DATABASE xau_lab OWNER xau;"
```

Both commands should print `CREATE ROLE` and `CREATE DATABASE`.

### Step 4. Configure the API

Copy the example settings file into the `backend` folder:

```bash
cd backend
cp ../.env.example .env          # Windows PowerShell: Copy-Item ..\.env.example .env
```

Generate a secret key. It signs your login sessions, so keep it private:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The first run of `uv` downloads Python 3.13; that is expected. Now open `backend/.env` in any text editor and set two lines:

```ini
XAU_DATABASE_URL=postgresql+psycopg://xau:choose-a-password@localhost:5432/xau_lab
XAU_SECRET_KEY=paste-the-generated-key-here
```

Use the password you chose in Step 3. You can leave the other lines as they are.

> `.env` is listed in `.gitignore`, so it is never committed. Never put your real password or key in `.env.example`.

### Step 5. Install the API and create the tables

Still in the `backend` folder:

```bash
uv sync                          # installs Python packages into backend/.venv
uv run alembic upgrade head      # creates the database tables
```

The second command ends with a line like `Running upgrade  -> 643ea9d10de9, phase 1 foundation`.

### Step 6. Create your login

```bash
uv run python -m app.cli bootstrap --email you@example.com --name "Your Name"
```

It asks for a password (at least 10 characters) and prints `Created user you@example.com.`.
This also adds the XAUUSD instrument. You only do this once. Running it again does no harm: it tells you the user already exists.

### Step 7. Install the web app

```bash
cd ../frontend
pnpm install
```

Installation is now finished.

---

## Part 2 — Running it (every time)

You need **two terminal windows**, both left open while you use the app. PostgreSQL normally starts by itself when your computer starts.

**Terminal 1 — API**

```bash
cd trade-journal-xauusd/backend
uv run uvicorn app.main:app --port 8000
```

Wait for `Application startup complete.`

**Terminal 2 — Web app**

```bash
cd trade-journal-xauusd/frontend
pnpm dev
```

Wait for `Ready`, then open **http://localhost:3000** and sign in with the email and password from Step 6.

**To stop:** press `Ctrl + C` in each terminal.

> **Faster option for daily use:** `pnpm dev` recompiles pages as you open them, which suits development.
> For snappier everyday use, build once and serve the build:
> ```bash
> pnpm build      # run again after each update
> pnpm start
> ```

---

## Part 3 — First steps in the app

1. **Settings → Display timezone.** Choose your timezone, for example `Europe/London`. Times are stored in UTC and shown in this zone.
2. **Settings → Trading sessions.** Check the Asian, London, New York and overlap windows. Each is defined in its own market's timezone, so daylight-saving changes are handled for you. The "Today in UTC" column shows the current equivalent.
3. **Settings → Trading accounts → Add account.** Add each account you trade: demo, live, prop evaluation, or a simulation account for paper trading. Live, demo and prop accounts count as actual results. Simulation accounts are reported separately.
4. **Strategy Library → Import scripts.** Drag in your `.pine` or `.txt` files, or one `.zip` of the whole folder. You get an import report for every file, then the library table with each script's compatibility class.
5. **Open a strategy** to see its findings. Click a "line N" chip to jump to that line in the source. Use the Details tab to record your hypothesis, entry/exit rules and supported timeframes.

To get your scripts out of TradingView, open each one in the Pine Editor and either copy it into a `.pine` text file or save it locally, then zip the folder.

---

## Part 4 — Updating to a new version

When new work is pushed to GitHub:

```bash
cd trade-journal-xauusd
git pull

cd backend
uv sync                          # new Python packages, if any
uv run alembic upgrade head      # new database tables or columns, if any

cd ../frontend
pnpm install                     # new web packages, if any
```

Then start it again as in Part 2 (run `pnpm build` again if you use `pnpm start`). Your data is kept: migrations only add or change structure.

---

## Part 5 — Backing up your data

Everything you enter lives in the `xau_lab` database. Back it up with:

```bash
pg_dump -U xau -h localhost -F c -f xau_lab-backup-$(date +%F).dump xau_lab
```

On Windows PowerShell, replace `$(date +%F)` with a date you type yourself, for example `xau_lab-backup-2026-10-18.dump`.

To restore a backup into an empty `xau_lab` database:

```bash
pg_restore -U xau -h localhost -d xau_lab --clean xau_lab-backup-2026-10-18.dump
```

Keep backups somewhere other than this computer.

---

## Part 6 — Running the tests (optional)

The backend tests use a **separate** database and erase it on every run. Never point them at `xau_lab`.

```bash
# one time: create the test database (macOS shown; use sudo -u postgres / -U postgres as in Step 3)
psql postgres -c "CREATE DATABASE xau_lab_test OWNER xau;"

cd backend
XAU_TEST_DATABASE_URL=postgresql+psycopg://xau:choose-a-password@localhost:5432/xau_lab_test uv run pytest
```

On Windows PowerShell, set the variable first: `$env:XAU_TEST_DATABASE_URL="postgresql+psycopg://xau:choose-a-password@localhost:5432/xau_lab_test"`, then run `uv run pytest`.

Frontend checks:

```bash
cd frontend
pnpm exec vitest run      # unit tests
pnpm lint                 # code style
pnpm exec tsc --noEmit    # type check
```

The browser end-to-end tests (`scripts/e2e.sh`) need a Bash shell (macOS, Linux, or WSL/Git Bash on Windows) and `pnpm exec playwright install chromium` once. See the main README.

---

## Part 7 — Docker (alternative, untested)

If you prefer Docker Desktop to installing PostgreSQL, Node and uv, a `docker-compose.yml` is included. It **has not been tested yet**, so treat it as a starting point.

```bash
cp .env.example .env              # in the repo root; set XAU_SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
docker compose exec api uv run python -m app.cli bootstrap --email you@example.com
```

Then open http://localhost:3000. The database is kept in a Docker volume called `pgdata`.

---

## Troubleshooting

| What you see | Cause and fix |
|---|---|
| Login page shows "The API service is not reachable" | Terminal 1 isn't running, or it crashed. Look at its output and start it again. |
| API won't start: `connection refused` on port 5432 | PostgreSQL isn't running. macOS: `brew services start postgresql@16`. Linux: `sudo systemctl start postgresql`. Windows: start the "postgresql-x64-16" service in the Services app. |
| API won't start: `password authentication failed for user "xau"` | The password in `backend/.env` doesn't match Step 3. Fix `.env`, or reset it: `ALTER USER xau WITH PASSWORD '...';` |
| API won't start: `secret_key ... at least 32 characters` | `XAU_SECRET_KEY` in `backend/.env` is too short. Generate one as in Step 4. (If the line is missing entirely, the API starts with a built-in development key: fine for trying it out, but set your own before relying on it.) |
| API starts but pages error with `relation "users" does not exist` | The tables weren't created. Run `uv run alembic upgrade head` in `backend`. |
| "Email or password is incorrect" | Check the email from Step 6. To add another login, run the bootstrap command again with a different email. |
| "Too many sign-in attempts" | More than 10 attempts in a minute from your machine. Wait one minute. |
| `address already in use` on 8000 or 3000 | Something else uses that port. Use another one: API `--port 8001` and start the web app with `API_URL=http://localhost:8001 pnpm dev` (PowerShell: `$env:API_URL="http://localhost:8001"; pnpm dev`). For the web app, `pnpm dev -p 3001`. |
| `uv`, `pnpm` or `psql`: "command not found" / "not recognized" | Close and reopen the terminal after installing. On Windows, check the PATH note in Step 1. |
| `pnpm` asks to download itself | Answer yes. Corepack fetches the right pnpm version the first time. |
| A strategy import shows "not valid UTF-8" | The file was saved in another encoding. Open it in a text editor and save it as UTF-8, then import again. |

If you hit something not listed here, copy the full error text from the terminal. That text is what's needed to diagnose it.
