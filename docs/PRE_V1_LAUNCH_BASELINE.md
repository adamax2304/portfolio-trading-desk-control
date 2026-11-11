# Pre-v1 Launch Baseline — Current State Audit (PART 0)

**Date:** 2026-06-17
**Project:** `C:\Users\adama\Documents\trading-desk-control`
**Sibling system (read-only source):** `C:\Users\adama\Documents\crypto-ai-desk`

This documents the state **before** the v1 finishing pass. Subsequent PART docs describe
what was added.

## Verification commands used

```bash
# backend tests
cd backend && python -m pytest tests/ -q          # → 18 passed, 2 warnings

# real-DB read-only adapter smoke (DEMO_MODE=0, real desk DB)
CONTROL_DB_PATH=... DESK_DB_PATH=.../crypto_ai_desk.sqlite DEMO_MODE=0 AUTH_DISABLED=1 \
  python -c "from app import desk_adapter as a; print(len(a.list_signals(5)))"   # → 5

# frontend build (confirmed green in prior pass)
cd frontend && npm install && npm run build       # → 0 TS errors, dist built
```

## Confirmed working

| Item | Status | Evidence |
|------|--------|----------|
| Backend starts | ✅ | FastAPI app imports; `init_db()` on startup; TestClient boots in tests |
| Frontend builds | ✅ | `npm run build` green (0 TS errors) in prior pass |
| Bot stub exists | ✅ | `bot/bot.py` (aiogram): `/start`, "Open Trading Desk" Web App button, Emergency Pause callback |
| Control DB | ✅ | `control.sqlite` auto-created on startup with full schema + default settings |
| Adapter reads **real** desk DB | ✅ | read-only `mode=ro` connection; `list_signals(5)` returned real signals (e.g. PORTAL/USDT intraday B → actionable). Real DB is 1.4 GB, actively written (WAL); we open **read-only only** |
| Real DB schema matches adapter | ✅ | `proposed_signals` (1944 rows), `signal_outcomes` (130 958), `signal_alerts` (1149) — all columns the adapter queries are present |
| Mini App → backend | ✅ | Vite proxy `/api → 127.0.0.1:8000`; typed client in `api.ts` sends `X-Telegram-Init-Data` |
| Live + auto-live locked | ✅ | `config.enable_live_commands=False`, `auto_live_locked=True`; `commands.py` HARD-rejects `MANUAL_LIVE_ORDER`, `SET_MODE manual_live/auto_live`; tests assert it |
| Crypto/stocks scalp locked | ✅ | `actionability.classify` → shadow; `ENABLE_MODE crypto_scalp/stocks_scalp` rejected; tests assert it |
| Paper command flow | ✅ | `POST /api/command` → `commands.process_command` → control DB; confirm-token required |
| Command queue + audit | ✅ | `control_commands` (pending/applied/rejected/failed) + `control_audit_log` tables + helpers |
| Tests pass | ✅ | 18 passed |

## Architecture (as-is)

- **backend/app**: `config.py` (env, safe defaults), `telegram_auth.py` (HMAC initData verify +
  freshness + whitelist), `control_db.py` (control SQLite: commands/audit/settings/runtime_overrides/
  manual_orders/notifications), `commands.py` (the only state-change path, with hard safety gates),
  `desk_adapter.py` (read-only adapter over the real desk DB + demo fallback),
  `actionability.py` (single source of truth for "can the operator take this"), `main.py` (FastAPI).
- **frontend/src**: Vite+React+TS Telegram Mini App — `api.ts`, `query.ts` (TanStack),
  `types.ts`, `shell.tsx`, `components.tsx`, `screens.tsx` (Home/Signals/Trades/TradeDetail/
  Market/Risk/System), `Chart.tsx` (lightweight-charts), `ManualTradeModal.tsx`, `App.tsx`.
- **bot/bot.py**: thin aiogram launcher/notifier (no trading logic).

## What is missing for v1 (addressed in PART 1–12)

1. **Risk controls are read-only in the UI** — no tap-to-edit → confirm → command flow. Missing
   `SET_MAX_OPEN_POSITIONS`; spec command aliases (`ENABLE_MODE_PAPER`, `DISABLE_MODE_PAPER`,
   `RESUME_PAPER`). (PART 1)
2. **Paper trade actions are stubs** — `CLOSE_PAPER_TRADE`/`CANCEL_PENDING_ORDER` return `{ok}`
   without updating `manual_orders`; no `ADD_TRADE_NOTE`, `ACKNOWLEDGE_ALERT`; no custom (no-signal)
   paper order UI; missing-stop and daily-risk guards absent. (PART 2)
3. **Command/audit not surfaced** — combined `/api/audit` only; no `/api/commands/recent`,
   `/api/audit/recent`; UI doesn't show command status / recent commands / latest risk changes. (PART 3)
4. **Bot** — no `/help`; pause button posts empty initData (401 in prod) — needs a safe
   server-to-server path. (PART 4)
5. **System health is thin** — 3 components only; no `/api/system/errors`, `/api/system/sanity-check`,
   `RUN_SANITY_CHECK`; no DB-reachability / freshness / queue-health detail; no Run-Sanity button. (PART 5)
6. **Chart/trade detail** — missing close (exit) marker; sparkline component unused. (PART 6)
7. **Demo coverage** — missing an *actionable crypto swing* example and an explicit *system warning*
   state; real-DB schema-mismatch handling not graceful. (PART 7)
8. **Launch ergonomics** — no run scripts; `.env.example`/README incomplete for full launch. (PART 8)
9. **Security** — `AUTH_DISABLED` not guarded against production use. (PART 9)
10. Frontend has no test runner. (PART 10)

## Known limitations (by design, remain in v1)

- **Paper trade actions are control-plane bookkeeping** — recorded + audited in the control DB,
  **not** executed inside the crypto-ai-desk core engine (no core API exists for that). The UI is
  honest about this (queued/applied). Wiring to the core paper engine is Phase 3.
- **No live execution / no exchange keys** — by design.
- **Polling, not push** — 15–30s refresh; SSE/WebSocket is a future upgrade.
- Real desk DB is opened **read-only**; the control plane never writes to it or to the trading YAML.
