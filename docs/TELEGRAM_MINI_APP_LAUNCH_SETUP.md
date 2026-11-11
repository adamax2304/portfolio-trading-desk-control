# Telegram Mini App — Launch Setup (PART 4)

**Date:** 2026-06-17

## Architecture
- **Backend** verifies Telegram `initData` server-side (HMAC-SHA256 with the bot token) on
  every request, checks freshness (`INITDATA_MAX_AGE`) and the user-id whitelist
  ([telegram_auth.py](../backend/app/telegram_auth.py)). `initDataUnsafe` is never trusted.
- **Bot** ([bot/bot.py](../bot/bot.py)) is a thin launcher/notifier (aiogram) — **no trading
  logic**: `/start` (Open Trading Desk + Emergency Pause), `/help`, allowed-user check.
- **Mini App** (frontend) sends `tg.initData` in the `X-Telegram-Init-Data` header.

## BotFather setup
1. `@BotFather` → `/newbot` → get the **bot token** → set `TELEGRAM_BOT_TOKEN`.
2. Host the built frontend (`frontend/dist`) over **HTTPS** (Telegram requires https for Web Apps).
3. `@BotFather` → `/mybots` → your bot → **Bot Settings → Menu Button → Configure menu button**
   → set the URL to your Mini App https URL. (Or set the URL on the inline Web App button —
   the bot already builds it from `MINI_APP_URL`.)
4. Set `MINI_APP_URL` to that https URL (used by the bot's "Open Trading Desk" button).

## Auth testing
- **Local dev:** `AUTH_DISABLED=1` returns a demo user — bypasses Telegram auth. Dev only.
- **Real auth:** set `TELEGRAM_BOT_TOKEN` + `ALLOWED_TELEGRAM_USER_IDS`, `AUTH_DISABLED=` empty.
  Open the Mini App from your bot; the backend validates initData and rejects non-whitelisted
  users (HTTP 401). Bad/expired hashes are rejected (covered by tests).
- **Bot emergency-pause:** the bot cannot mint initData, so it calls `/api/emergency-pause`
  with `X-Control-Bot-Token` = `CONTROL_BOT_TOKEN` (a shared server-to-server secret). Only the
  safest command (pause) accepts this path; everything else needs a real Mini App user.

## Run locally (dev)
```powershell
# 1) backend (demo or real DB)
./scripts/start_backend.ps1
# 2) frontend dev (proxy → backend)
./scripts/start_frontend.ps1
# 3) bot (needs TELEGRAM_BOT_TOKEN + MINI_APP_URL in .env)
./scripts/start_bot.ps1
```
For Telegram to reach a local Mini App, expose the frontend over https (e.g. a tunneling
service) and point `MINI_APP_URL` at it. For pure browser dev, just open `http://localhost:5173`.

## Production caveats
- `APP_ENV=production` makes the backend **refuse to start** if `AUTH_DISABLED=1`, or if
  `TELEGRAM_BOT_TOKEN` / `ALLOWED_TELEGRAM_USER_IDS` are missing.
- Serve the frontend as static files over https; set `VITE_API_BASE` at build time if the API
  is on a different origin (CORS is open in v1 — tighten `allow_origins` for production).
- Keep `CONTROL_BOT_TOKEN` secret; rotate if leaked. Secrets live only in backend env.
