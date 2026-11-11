# Audit fixes — Batch 3 (#3-compute asset-aware cost model + #10 funding)
**Date:** 2026-07-01 · paper/read-model only · live+auto+manual-live **hard-locked** · `signal_outcomes.final_r` **untouched**.

## Done this batch (crypto-ai-desk engine + control-plane + tests)

### #3 (compute) — Stocks priced with a stock/ETF model, NOT crypto perps
`src/execution/paper_portfolio.py::simulate_portfolio` now selects the cost model **per trade by
asset_class**: stocks use a new `stock_etf_default` fee profile (commission-free + ~1bp effective) +
wider stock slippage + a large-cap "majors" list; crypto keeps the perp profile; `zero` stays no-cost.
New profile in `config/fee_profiles.yaml`. Ledger rebuilt.

**Impact (active book):** stocks exchange fees **$761.81 → $146.82** (crypto-perp taker 0.055% → stock
~1bp); stocks net **−$878.97 → −$343.48**; overall book **net +$213 → +$548 (+10.97%)** — stocks were
being over-charged crypto-perp fees. The ledger row keeps the book id in `fee_profile` (for backend
grouping) while the real model is in `fee_source`; the control-plane `portfolio_by_asset` now judges
`cost_model_appropriate` from `fee_source` → **stocks now `True`** (were flagged `False` in Batch 1).

### #10 — Approximate funding/carry for crypto perps
Config `funding` (`default_rate_per_interval` 1bp / 8h; `intervals_by_mode` scalp 0 / intraday 1 /
swing 6 / invest 0). Crypto-perp trades now carry a modelled funding cost; stocks = 0 (known-zero);
crypto with unknown mode → `funding_known=false`. **Live: crypto funding $90.51** (was $0; 252 rows).
Split surfaced everywhere: `portfolio_summary` + `portfolio_by_asset` now expose
`exchange_fees_usdt` / `slippage_usdt` / `funding_usdt` separately (ties #1 through to the engine).

## Tests
- crypto `tests/test_audit_fixes_engine.py` +2 (stocks use stock profile & lower fee vs crypto; crypto
  funding > 0, stocks funding == 0) → **5/5**; regression shadow+coverage+safe-obs **30 passed**.
- control-plane `tests/test_audit_fixes.py` updated (`test_per_asset_cost_model_correct`: crypto+stocks
  both appropriate now) → **7/7**. compileall both clean.

## Files changed
- `crypto-ai-desk/src/execution/paper_portfolio.py` (#3-compute + #10)
- `crypto-ai-desk/config/fee_profiles.yaml` (`stock_etf_default`)
- `crypto-ai-desk/scripts/paper_portfolio_backfill.py` (trade dict `mode`)
- `trading-desk-control/backend/app/portfolio.py` (`portfolio_by_asset` flag → `fee_source`)

## Status across all 12
✅ **Done:** #1, #2, #3 (display + compute), #5, #6, #8, #9 (stop bound), #10, #11.
⏳ **Remaining:** **#4** slice-aware accounting (biggest — entry type / TP partials / stop & expired
remainders / maker-TP vs taker-stop, reusing `paper_shadow_engine` slice events); **#7** maker fill on
bps/ticks trade-through (not touch) + post-only miss; sub-parts: control-plane `forward_monitor`
DATA_GAP_LATE mirror, #9 vp_supported display guard, frontend rendering of the split fees / per-asset /
integrity warnings.
