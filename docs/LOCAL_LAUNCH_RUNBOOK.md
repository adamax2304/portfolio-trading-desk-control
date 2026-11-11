# Local Launch Runbook (PART 8)

**Date:** 2026-06-17 · Windows / PowerShell. No Docker required.

## Prerequisites
- Python 3.12 (backend), Node 18+ / npm (frontend).
- `cd backend && pip install -r requirements.txt` (FastAPI, uvicorn, pydantic; aiogram+httpx for the bot).
- `cd frontend && npm install`.

## Step 1 — configure env
Copy `.env.example` → `.env` and fill in. For a **local demo** run you can leave most blank:
```
APP_ENV=dev
DEMO_MODE=1
AUTH_DISABLED=1
```
For **real DB** (read-only): set `DESK_DB_PATH` to the crypto-ai-desk sqlite, `DEMO_MODE=` empty.
For **Telegram**: set `TELEGRAM_BOT_TOKEN`, `ALLOWED_TELEGRAM_USER_IDS`, `MINI_APP_URL`,
`CONTROL_BOT_TOKEN`, and leave `AUTH_DISABLED` empty.

## Step 2 — start backend
```powershell
./scripts/start_backend.ps1      # → http://127.0.0.1:8000  (loads .env)
```
Check: `curl http://127.0.0.1:8000/api/health` → `{"ok":true,...}`.

## Step 3 — start frontend
```powershell
./scripts/start_frontend.ps1     # → http://localhost:5173  (proxies /api → backend)
```
Or build static for hosting: `./scripts/build_frontend.ps1` → `frontend/dist`.

## Step 4 — start bot (optional, for Telegram)
```powershell
./scripts/start_bot.ps1          # needs TELEGRAM_BOT_TOKEN + MINI_APP_URL
```

## Step 5 — open the Mini App
- **Browser dev:** open `http://localhost:5173` (works with `AUTH_DISABLED=1`).
- **Telegram:** open your bot → `/start` → "Open Trading Desk" (Mini App must be served over https).

## Step 6 — verify status
- `curl http://127.0.0.1:8000/api/health` → `ok:true`, `live_locked:true`.
- In the app: System screen → all health cards, **Run Sanity Check** → all safety checks pass.

## Step 7 — stop services
Close the spawned PowerShell windows, or `Ctrl+C` in each. Nothing is left running; the control
DB persists at `CONTROL_DB_PATH`.

## One-shot
```powershell
./scripts/start_control_plane.ps1   # backend + frontend in separate windows
./scripts/run_tests.ps1             # backend pytest + frontend build
```
