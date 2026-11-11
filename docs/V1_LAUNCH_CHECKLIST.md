# V1 Launch Checklist (PART 11)

**Date:** 2026-06-17 · tick each before going live (as a control plane, not live trading).

## Pre-flight
- [ ] `.env` created from `.env.example`; `APP_ENV` set (`dev` local, `production` for deploy)
- [ ] `pip install -r backend/requirements.txt` · `npm install` in `frontend/`
- [ ] Real DB path verified: `DESK_DB_PATH` points to the crypto-ai-desk sqlite (read-only)
- [ ] Control DB path set (`CONTROL_DB_PATH`); initialized automatically on first start

## Services
- [ ] **Backend running** — `./scripts/start_backend.ps1`; `GET /api/health` → `ok:true`
- [ ] **Frontend built / served** — `./scripts/build_frontend.ps1` (prod) or dev server
- [ ] **Bot running** — `./scripts/start_bot.ps1` (if using Telegram)
- [ ] **Mini App URL configured** in BotFather (menu button / web app) = `MINI_APP_URL` (https)

## Auth & secrets
- [ ] `TELEGRAM_BOT_TOKEN` + `ALLOWED_TELEGRAM_USER_IDS` set; `AUTH_DISABLED` empty in prod
- [ ] Auth verified: open Mini App → loads; non-whitelisted user → 401
- [ ] `CONTROL_BOT_TOKEN` set (bot emergency-pause works) and kept secret
- [ ] No secrets in the frontend bundle; no exchange keys anywhere

## Safety (must all hold)
- [ ] **Live locked** — `/api/health` `live_locked:true`; manual-live order rejected
- [ ] **Auto-live locked** — `auto_live_locked:true`; set-mode auto_live rejected
- [ ] **Crypto scalp** shadow-only (enable rejected); **stocks scalp** research-only
- [ ] **C-tier / shadow / late** not actionable (no Manual Entry)
- [ ] **Sanity check** in System → all checks pass (8/8 demo · 9/9 real)

## Function
- [ ] Paper commands working (risk edit → "Applied & audited")
- [ ] Command audit visible (System → Recent commands; Risk → Recent changes)
- [ ] Emergency pause works as a command (System / Home / bot)
- [ ] Charts render (entry/stop/TP overlays in view); honest "unavailable" when no cache
- [ ] System health OK; trading-DB schema OK (no banner)

## Quality
- [ ] Backend tests pass — `cd backend && python -m pytest tests/ -q` (33 passed)
- [ ] Frontend builds — `npm run build` (0 TS errors)
- [ ] No console errors in the Mini App; no backend error spam
- [ ] No horizontal overflow at 390 / 430px

## Stop procedure
- [ ] Close spawned windows / `Ctrl+C` each service. Control DB persists; trading DB untouched.
