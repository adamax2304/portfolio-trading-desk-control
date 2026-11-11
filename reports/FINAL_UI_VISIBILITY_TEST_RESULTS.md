# PART 6 — Final UI visibility test results
**Date:** 2026-06-26 · live locked · final_r untouched.

## Backend endpoint + unit tests — `backend/tests/test_shadow_ab_visibility.py` (6/6 ✅)
- `test_fee_assumptions_default_profile_after_fees` — profile bybit_non_vip, maker<taker, after-fees, override off.
- `test_trades_have_ab_detail_and_delta` — each trade has delta + why + valid_forward; branch has
  side/entry_mode/fill_status/gross_r/net_r/fees_usd.
- `test_forward_rows_surface_before_backfill` — no forward row appears after a backfill row.
- `test_forward_monitor_exposes_maker_block` — maker posted/filled/missed/taker_fallback/fill_rate_pct.
- `test_live_locked` — `auto_live_locked` is True.
- `test_read_model_has_no_write_sql` — `paper_shadow.py` contains no INSERT/UPDATE/DELETE/DROP and never
  writes `final_r` (read-model is SELECT-only).

## Playwright smoke — `scripts/shadow_ab_smoke.py`
```
panel_visible=True  fee_card_visible=True  maker_visible=True  trades_visible=True
trade_detail_opens=True   max_horizontal_overflow_px=0 (Home/Signals/Trades/Market/Risk/System all 0)
console_errors: only transient external-CDN fetches (tabler-icons / fonts); none from app origin
```
A/B panel visible · trade detail opens on click · fee card visible · maker realism visible · no
horizontal overflow on any tab. The only console noise is intermittent external font/icon CDN fetches
(verified gone on a clean single-tab reload) — not application errors.

## Full suites (regression)
- **trading-desk-control backend**: `python -m pytest backend/tests/` → **75 passed, 3 skipped, 0 failed**.
- **crypto-ai-desk shadow + coverage**: `test_paper_shadow_engine` + `test_paper_shadow_operational` +
  `test_stock_intraday_coverage` → **15 passed**.
- Combined: **90 passed, 3 skipped, 0 failed**.

## Guardrails asserted
- No live / no exec path touched (`auto_live_locked` True; read-model SELECT-only).
- `final_r` never written by the control-plane read-model (asserted by source scan).

## VERDICT: `FINAL_UI_VISIBILITY_TESTS_PASS` ✅
