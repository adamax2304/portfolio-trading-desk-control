# System Health & Sanity Checks (PART 5)

**Date:** 2026-06-17

## Endpoints ([main.py](../backend/app/main.py))
- `GET /api/system/health` — components + errors + schema status
- `GET /api/system/errors` — recent errors (failed/rejected commands + telegram delivery errors)
- `GET /api/system/sanity-check` — read-only assertions
- `POST /api/command {type:"RUN_SANITY_CHECK"}` — runs + records a notification (audited)

## Health components ([desk_adapter.py](../backend/app/desk_adapter.py) `system_health`)
Always (from control DB): **Backend API**, **Control DB**, **Command queue**
(`N applied · N rejected · N failed`, last 200).

Real-DB mode adds: **Trading DB (read-only)**, **Monitor / tracker** (last `signal_outcomes`
tick, ok < 30m), **Latest signal** (`MAX(created_at)`), **Latest alert** (`MAX(sent_at)`),
**Telegram alerts (24h)** (sent + timeout count; timeouts → CHECK), **OHLCV freshness**
(newest cached csv mtime, bounded scan, ok < 180m).

`schema_ok=false` + `schema_error` is returned (not a 500) if the trading DB is unreachable or
its schema doesn't match — the System screen renders a clear banner.

Verified against the **live 1.4 GB desk DB** (read-only): monitor tick 1m ago, latest signal
1.3h, latest alert 20m, 1 telegram timeout flagged CHECK, OHLCV 1m — schema_ok=true.

## Sanity check ([desk_adapter.py](../backend/app/desk_adapter.py) `sanity_check`)
Read-only assertions (never mutates): Control DB reachable · **Live trading locked** ·
**Auto-live locked** · **Crypto scalp not enabled** · **Stocks scalp not enabled** ·
Trading mode ∈ {paper, disabled} · Trading DB reachable + recent signal (or demo) ·
No failed commands (last 200). Returns `{ok, passed, total, checks[]}`. Demo → 8/8;
real DB → 9/9 in verification.

## Frontend (System screen)
Health cards with live dots + OK/CHECK badges, schema-problem banner, 24h error list, a
**"Run Sanity Check"** button rendering the checks inline, a **"Recent commands"** list, an
**"Add note"** quick action, and **Emergency Pause** (with "no destructive restart in v1" note).
No destructive restart control is exposed.
