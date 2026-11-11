# Audit fixes — Batch 1 (paper/read-model only)
**Date:** 2026-07-01 · live + auto-live + manual-live remain **hard-locked** · `signal_outcomes.final_r` **untouched**.

## Done this batch (backend + tests)

### #1 — Split exchange fees vs slippage (`trading-desk-control/backend/app/portfolio.py`)
`portfolio_summary` previously summed `fees_usdt + slippage_usdt` into one `fees_paid_usdt`. Now exposes:
`exchange_fees_usdt`, `slippage_usdt`, `funding_usdt` (+ `funding_known`), `total_execution_cost_usdt`.
`fees_paid_usdt` kept as a **DEPRECATED alias = total execution cost** (back-compat). Live numbers:
exchange fees **$1027.0**, slippage **$899.65**, funding $0 → total $1926.65 (previously shown as one "fees" figure).

### #2 — Actionability terminal statuses (`backend/app/actionability.py`)
Added `stale_before_entry` and `entry_moved_away` to `_TERMINAL`. Such signals now return
`actionable=False, status="closed"` → the frontend gates (`a.actionable && a.status === "actionable"` in
`components.tsx:96`, `screens.tsx:732`; `ManualTradeModal` `blocked=!a.actionable`) correctly block Manual Entry.

### #3 (display half) — Per-asset cost split (`portfolio.py::portfolio_by_asset` + `/api/portfolio/by-asset`)
Ledger has no `asset_class`, so we join `proposed_signals`. Returns crypto-only vs stocks-only net P&L +
per-asset `exchange_fees/slippage/funding`, and a **`cost_model_appropriate` flag**: stocks under the
crypto-perp profile are flagged `False` with a note "STOCKS priced under crypto-perp fees — placeholder".
Live: **crypto +$973.6 (ok)** vs **stocks −$878.97 (mispriced under crypto-perp)**. This surfaces the bug;
the engine-side recompute is staged (see #3 compute below).

### #5 — Forward vs backfill separation (verified, already correct)
`paper_shadow_monitor.forward_quality` queries `window='forward_since_activation'` ONLY; `promotion_gate`
uses it (never backfill); output carries `activated_at` (2026-06-25), `forward_days`=5, `forward_signals`=210,
`executed=False`. No change needed.

### #11 — A/B comparison integrity (`portfolio.py::portfolio_compare`)
Added `comparison_integrity`: per-profile trade count + latest_ts + common-trade count + warnings.
Live finding: **A=639 trades (06-30) vs B=592 trades (06-24, 145h stale)** → `comparable=False`, warns
"trade sets differ (A-only 48)" + "profiles last updated 145.0h apart — one ledger is stale; rebuild both".

## Tests — `backend/tests/test_audit_fixes.py` (7/7 ✅)
fee/slippage split + total identity + deprecated alias; actionability `stale_before_entry`/`entry_moved_away`
→ not actionable; stocks flagged under crypto-perp; compare integrity present; read-model has no write SQL.
Full backend suite: **78 passed, 9 skipped, 2 pre-existing date-dependent failures** in `test_books.py`
(`test_books_totals_differ_intentionally` hardcodes `exit_at=2026-06-20` + asserts d7 inclusion; now that
it's 07-01, 06-20 is 11d out → out of the 7-day window. Unrelated to these changes — `books.py` has its own
`_TERMINAL_REALIZED`).

## Files changed
- `trading-desk-control/backend/app/portfolio.py` (#1, #3-display, #11 + `_profile_meta`)
- `trading-desk-control/backend/app/actionability.py` (#2)
- `trading-desk-control/backend/app/main.py` (+`/api/portfolio/by-asset`)
- `trading-desk-control/backend/tests/test_audit_fixes.py` (new)

## Staged (next batches — heavier / engine-side; left honest, not half-done)
- **#3 compute** — stock/ETF cost model in `crypto-ai-desk/src/execution/paper_portfolio.py` so stocks are
  priced with stock fees (not `bybit_non_vip_usdt_perp`), then rebuild ledger.
- **#4** — slice-aware portfolio accounting (entry type, TP partials, stop remainder, expired remainder,
  maker-TP vs taker-stop) reusing `paper_shadow_engine` slice events; keep `paper_execution_r` authoritative.
- **#6** — look-ahead audit of `signal_paper_tp.py` / `signal_stop_plan.py` / `entry_mode_classifier.py`
  (context candles ≤ created_at, outcome candles ≥ created_at).
- **#7** — maker trade-through fill model (not touch=fill; bps/ticks trade-through + post-only miss; the
  timeout-to-taker + posted/filled/missed counters already exist).
- **#8** — exclude `entry_latency_audit.status='DATA_GAP_LATE'` from primary edge metrics + dirty cohort +
  high-share warning (the `data_gap` close-reason exclusion already exists; the DATA_GAP_LATE join does not).
- **#9** — structural stop/TP sanity bounds (flag absurd >20R `stop_after_tp`; don't show VP support when `vp_supported=0`).
- **#10** — approximate funding/carry for crypto perps across funding intervals (+ `funding_known=false`).
- **Frontend** — render the split fees / per-asset / integrity-warning labels (don't call slippage a fee).

## Criteria check
- Paper/read-model only ✅ · live/auto/manual-live locked ✅ · `final_r` untouched ✅
- exchange fees vs slippage no longer confusable in API ✅ (UI render staged)
- stocks vs crypto reported separately ✅ (display; compute staged)
- promotion/gate uses forward evidence only ✅ · tests + report ✅
