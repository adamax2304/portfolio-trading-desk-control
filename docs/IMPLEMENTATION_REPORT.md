# Control Plane — Implementation Report

**Date:** 2026-06-17 · **Verdict: `CONTROL_PLANE_READ_ONLY_READY`** (read-only monitoring +
safe paper command queue are built, tested, and verified against the live desk DB; manual-
live and auto-live are intentionally locked pending a separate live-readiness audit).

## Built (MVP)
**Backend (FastAPI) — fully implemented + 18 passing tests:**
- Telegram `initData` HMAC verification + freshness + user-id whitelist (`telegram_auth.py`).
- Read adapter over `crypto-ai-desk` SQLite (read-only `mode=ro`) + OHLCV cache, with demo
  fallback (`desk_adapter.py`). Verified live: 500 real signals normalized; actionability
  {actionable 49, shadow 65, late 4, blocked 154, closed 228}; all 97 scalp non-actionable.
- Central actionability engine (`actionability.py`): tier/mode/timeframe-freshness/scalp/
  concentration → takeable/shadow/late/blocked + reasons + badges.
- Control DB (`control.sqlite`, separate): commands, audit, settings, runtime_overrides,
  manual_orders, notifications.
- Command processor with hard safety gates (`commands.py`).
- API: all read endpoints + `POST /api/command` (+ `/api/risk/update`, `/api/emergency-pause`).

**Frontend (Vite + React + TS + Tailwind):** 6 tabs (Home/Signals/Trades/Market/Risk/System)
+ trade-detail with `lightweight-charts` (entry zone/stop/TP overlays + entry marker) +
`ManualTradeModal` (paper confirm; live hold-to-confirm locked). Dark institutional design.
Safety baked into rendering: shadow/late/C-tier/paused → no Manual Entry; late → DO NOT CHASE.

**Bot (aiogram):** `/start` opens the Mini App; emergency-pause enqueues a command.

## Tests (18 passed)
Auth: valid initData passes; bad hash rejected; non-whitelisted rejected; missing-auth → 401.
Read-only endpoints don't mutate the control DB. Shadow scalp not actionable. Commands:
unknown rejected; confirm-token required; risk out-of-range rejected / in-range applied;
crypto **and** stocks scalp can't be enabled; `MANUAL_LIVE_ORDER` locked; `SET_MODE
manual_live/auto_live` locked; emergency-pause is a flag/command (no process killed); manual
paper order on a shadow signal rejected, on an actionable signal applied; commands write audit.

## Safe ✅
- No trading-DB writes, no YAML writes, no exchange calls. Read adapter is `mode=ro`.
- Every mutation → command queue + audit row; confirm token required.
- Emergency pause = flag + command (no destructive process control).

## Locked 🔒 (require separate review before enabling)
- Live + auto-live trading modes; `MANUAL_LIVE_ORDER` (Level 2/3).
- Enabling `crypto_scalp` / `stocks_scalp`; promoting C-tier to live.
- Exchange API integration (none present; read-only keys first when L2 unlocks).

## Must be reviewed before live (Phase 3)
Exchange adapter w/ read-only→trade key staging; PIN + hold-to-confirm + 10s cooldown wired
to a real order path; daily-loss kill switch enforcement on fills; per-order max size; live
balance source; 30-day forward-validation/readiness audit gating `auto_live`.

## Remaining / nice-to-have
Frontend `npm install` + build not run in this environment (offline) — source is complete;
run `npm i && npm run dev`. SSE/WebSocket live push (currently poll-on-mount). Dashboard
"Stocks Concentration Guard" detail panel. Per-command `approved` step (currently
pending→applied for safe paper commands; add a 2-step approve for future live).
