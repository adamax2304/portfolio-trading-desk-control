# V1 Full Test & QA Report (PART 10)

**Date:** 2026-06-17

## Backend tests
```
cd backend && python -m pytest tests/ -q
33 passed, 2 warnings in ~3.4s
```
Coverage: auth (valid/bad-hash/non-whitelisted/missing), read-only safety, shadow gating,
unknown/confirm-token/range command validation, scalp-enable lock, manual-live lock,
set-mode live lock, emergency pause, paper-order on shadow vs actionable, audit-written,
**+ v1:** max-positions (set + enforce), weekly-loss range, enable-mode-paper alias + scalp lock,
missing-stop, custom-order + close idempotent, cancel-pending, daily-risk budget, add-note,
acknowledge-alert, sanity endpoint+command, recent endpoints, health components,
bot-token pause, production auth guard. Warnings are pre-existing FastAPI `on_event` deprecation.

## Frontend build
```
cd frontend && npm install && npm run build
tsc -b && vite build → 92 modules, 0 TypeScript errors, dist built (~2.8s)
index.js 392 KB (gz 123) · index.css 16.4 KB
```

## Frontend tests
No JS test runner is configured. Decision for v1: not adding vitest/jsdom — the safety-critical
gating is enforced and tested **server-side** (the backend is the authority), and the UI gating
is a thin reflection (`canManual = actionable && status==="actionable"`). Frontend verified by
type-check + live preview QA. Adding component tests is a Phase-3 nicety, noted as a limitation.

## Manual QA (live preview, demo backend)
This session (390px):
- **Risk** — tap value → RiskEditModal (old→new, impact) → Confirm → **"Applied & audited"**;
  backend recorded `SET_RISK_PER_TRADE` applied + audit row. ✅
- **System** — richer health cards incl. **OHLCV "stale — warning" CHECK** + "All clear" errors;
  **Run Sanity Check → 8/8**; **Recent commands** (1 applied); Add-note + Emergency Pause present. ✅
- **ManualTradeModal (custom)** — FAB opens custom form; **Review disabled** until symbol+stop
  (client guard) with "stop required" hint. ✅
- **Command submit flow** — verified end-to-end via the Risk edit. ✅
- Console: **no errors**.

Prior pass (same build pipeline, 390 + 430, no horizontal overflow): Home, Signals (full
actionability gating incl. DO NOT CHASE / BLOCKED / SHADOW / CLOSED), Trades, Trade Detail/Chart
(overlays + autoscale + exit marker), Market, ManualTradeModal (dialog a11y + Escape + paper
confirm / live-locked). Desktop renders via the same responsive ≤480 container.

## Real-DB integration (read-only)
Adapter reads the live 1.4 GB desk DB: signals load, health 9 components green (1 telegram
timeout flagged CHECK), sanity 9/9. No writes to the trading DB.

## Issues found & fixed during v1
1. `max_positions or 5` fallback treated `0` as falsy → max-positions guard bypassed. Fixed with
   explicit None check (caught by `test_max_open_positions_enforced`).
2. `os` not imported in `desk_adapter` (only hit on the real-DB OHLCV-freshness path; demo/tests
   skipped it). Fixed; re-verified against the real DB.

## Remaining known limitations
- Paper trade actions are control-plane bookkeeping, not core-engine executions (by design).
- Polling (15–30s), not push.
- No per-trade sparkline (no equity series in the desk API).
- No frontend unit-test runner; CORS open; owner-only (no RBAC); no rate limiting.
