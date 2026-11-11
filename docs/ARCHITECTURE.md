# AI Trading Desk — Control Plane: Architecture & Design

A **separate** control-plane app beside `crypto-ai-desk`. It monitors and (safely)
controls the trading core via a **read adapter + command queue** — it never edits the
trading YAML/DB or calls an exchange directly.

```
crypto-ai-desk/            # existing trading core (read-only to us)
trading-desk-control/
  backend/   FastAPI control API + control.sqlite (queue/audit/settings)
  frontend/  Vite + React + TS + Tailwind Telegram Mini App
  bot/       aiogram launcher + emergency push (no business logic)
  docs/
```

## 1. Components
1. **Telegram bot** — opens the Mini App, sends push alerts, emergency action. Thin.
2. **Mini App frontend** — 6 tabs (Home/Signals/Trades/Market/Risk/System) + trade-detail
   chart + manual-trade modal. Renders the *derived actionability* the backend computes.
3. **Control API (FastAPI)** — verifies Telegram initData, serves desk state (read), accepts
   commands, writes the queue + audit log. The only writer of control state.
4. **Trading-core adapter** — read-only over the desk SQLite + OHLCV cache; demo fallback.
5. **Command queue** — every action is a row with status `pending|approved|applied|rejected|failed`, fully audited.

## 2. Access levels (Level 3 not built)
- **L0 read-only**: dashboards, signals, trades, chart, health, risk view.
- **L1 paper**: paper balance/risk, manual paper order, close paper, notes — **implemented**.
- **L2 manual-live**: **locked** (needs readiness audit) — UI shows locked, server rejects.
- **L3 auto-live**: **locked/hidden** — “Requires 30d forward validation + readiness audit.”

## 3. Security model
- **initData verified server-side** (HMAC-SHA256 with bot token), freshness window, **user-id
  whitelist**. `initDataUnsafe` is never trusted for authz. (`telegram_auth.py`)
- Secrets (bot token, future exchange keys) live **only** in backend env. Frontend never sees
  keys. Read-only keys first; trade later; **withdrawals never**.
- **Audit log** row per action: user_id, username, ts, action_type, old, new, source=mini_app,
  confirmation, result, error, command_id. (`control_audit_log`)
- **Live protection (when L2 unlocks later)**: PIN, hold-to-confirm, 10s cooldown, daily-loss
  kill switch, max order size, max positions, symbol whitelist, mode whitelist, emergency pause.
  v1 ships the kill-switch/emergency-pause + whitelists + the hard locks below.
- **Hard locks (v1, enforced in `commands.py`/`config.py`)**: live + auto-live trading modes,
  `MANUAL_LIVE_ORDER`, enabling `crypto_scalp`/`stocks_scalp`, promoting C-tier — all rejected.

## 4. DB / API schema
**Control DB (`control.sqlite`, separate):** `control_users`, `control_commands`,
`control_audit_log`, `control_settings`, `runtime_overrides`, `manual_orders`,
`app_notifications`. Trading DB is **never** mutated.

**Runtime-override model:** `effective_config = base YAML + approved runtime overrides`
(stored in control DB, audited, reversible, `source=mini_app`, optional expiry). The UI
never writes YAML.

**Endpoints** (all GET require initData header; commands require `confirm_token`):
`GET /api/status · /api/signals · /api/signals/{id} · /api/trades/{open|pending|closed|shadow}
· /api/chart/{symbol}?tf · /api/market/summary · /api/risk/config · /api/system/health ·
/api/audit`; `POST /api/command` (canonical), thin wrappers `/api/risk/update`,
`/api/emergency-pause`. Command types: `SET_MODE, SET_PAPER_BALANCE, SET_LIVE_BALANCE,
SET_RISK_PER_TRADE, SET_DAILY_LOSS_LIMIT, SET_WEEKLY_LOSS_LIMIT, ENABLE_MODE, DISABLE_MODE,
EMERGENCY_PAUSE, RESUME, MANUAL_PAPER_ORDER, MANUAL_LIVE_ORDER(locked), CANCEL_PENDING_ORDER,
CLOSE_PAPER_TRADE, ADD_NOTE, ACK_ERROR`.

## 5. Frontend route/screen map
Single-page, bottom nav: **Home** (command center, PnL/open/pending/shadow, event feed,
emergency pause) · **Signals** (filters + signal cards; Manual Entry only when actionable) ·
**Trades** (open/pending/closed/shadow) · **Trade Detail** (lightweight-charts: candles +
entry zone/stop/TP lines + entry marker + setup-quality panel) · **Market** (narratives +
funding/OI) · **Risk** (mode + caps; scalp/live locked) · **System** (component health +
errors). Floating **+ Manual** only when paper/manual allowed. `ManualTradeModal`: paper
confirm; live = hold-to-confirm **locked**.

## 6. UI component plan
`ui.tsx`: `Chip` (tone = profit/warn/danger/shadow/accent), `Stat`, `SignalCard`
(badges + DO-NOT-CHASE/SHADOW gating + Manual-Entry enable rule), `ManualTradeModal`.
`Chart.tsx`: `TradeChart`. `screens.tsx`: the 6 screens + `TradeDetail`. Design = dark
institutional (near-black bg, cyan accent, green/amber/red, purple=shadow). Tailwind tokens
in `tailwind.config.js`.

## 7. Integration adapter (crypto-ai-desk)
`desk_adapter.py` reads (read-only `mode=ro`): `proposed_signals` (+ latest `signal_outcomes`
for entry/exit/MFE/MAE + latest `paper_entry` alert `payload_json` for
`concentration_status`), OHLCV CSV cache for charts. `actionability.py` re-derives the
takeable/shadow/late verdict from tier/mode/freshness(timeframe-aware)/scalp/concentration —
consistent with the core but without importing it. Absent desk DB → **demo mode** (synthetic
signals/candles) so the UI is fully explorable.
