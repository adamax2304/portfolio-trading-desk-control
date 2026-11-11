# Demo & Real-DB Modes (PART 7)

**Date:** 2026-06-17

## Mode selection
`DEMO_MODE=1` forces synthetic data. With `DEMO_MODE` unset, demo auto-enables only if the
desk DB is missing; otherwise the read-only adapter reads the real crypto-ai-desk DB.
The trading DB is **never written** (opened `mode=ro`).

## Demo mode coverage ([desk_adapter.py](../backend/app/desk_adapter.py) `_demo_signals`)
Every requested state is present:

| State | Demo fixture |
|---|---|
| actionable crypto intraday | ZEC/USDT, WLD/USDT |
| **actionable crypto swing** | **ETH/USDT** (waiting for entry, Tier A) |
| crypto scalp shadow | RIF/USDT (`SHADOW ONLY`) |
| sector-cap shadow | AMD (`SHADOW ONLY`, semis bucket) |
| late "DO NOT CHASE" | ARB/USDT (very late 22m) |
| C-tier BLOCKED | DOGE/USDT (`BLOCKED`) |
| closed trade | SUI/USDT (win +2.0R, exit marker) |
| **system warning** | health `OHLCV freshness` = CHECK (stale) |
| **no-error system state** | errors list empty (all clear) |

Verified live: Signals shows 8 cards with correct gating (2 actionable → Manual Entry; the
rest "Not actionable"); System shows the OHLCV warning + empty error list + sanity 8/8.

## Real-DB mode (verified read-only against the live 1.4 GB DB)
- `list_signals` reads `proposed_signals` (1944 rows) → e.g. PORTAL/USDT intraday B → actionable.
- `system_health` reads `signal_outcomes` (130 958) + `signal_alerts` (1149): monitor tick
  1m ago, latest signal 1.3h, latest alert 20m, 1 telegram timeout (CHECK), OHLCV 1m,
  `schema_ok=true`.
- `sanity_check` → 9/9 ok.

## Failure handling
- **DB missing** → demo mode auto-on (UI fully explorable); `/api/health` reports `has_desk_db=false`.
- **DB unreachable** (locked/permission) → health component "Trading DB (read-only): cannot open",
  `schema_ok=false`, System screen banner.
- **Schema mismatch** → adapter catches `sqlite3.OperationalError`, returns
  `schema_ok=false` + `schema_error`, System banner — **no 500**.

## Safety
No write path to the trading DB or YAML exists in this app. All mutations target the separate
control DB only.
