# Operational Hardening — FINAL REPORT + AUDIT
**Date:** 2026-06-25 · **Posture:** `live_locked=true`, `auto_live_locked=true`, no orders,
`final_r` untouched, B never promoted, backfill never used as proof.

## 12 questions
1. **Stock 15m OHLCV backfill implemented?** Coverage classifier + 2 CLIs done
   (`stock-intraday-coverage-report`, `stock-intraday-ohlcv-backfill`). `src/stocks/intraday_coverage.py`
   classifies DATA_OK / PARTIAL_DATA / DATA_GAP_LATE / NO_INTRADAY_DATA into `stock_intraday_coverage`.
   Verified: **28 symbols all DATA_OK now** (MSTR 1556 bars / 60 sessions / gap 0 — the earlier
   DATA_GAP_LATE was a *historical tracking-time* artifact; the rolling cache is currently full).
   The yfinance fetch is best-effort/fail-open (provider caps 15m at ~60d).
2. **DATA_GAP excluded from edge stats?** ✅ — `entry_latency_audit` flags DATA_GAP_LATE and the
   forward monitor excludes `no_data`/`data_gap` outcomes; coverage classifier corroborates.
3. **Per-trade A/B detail visible?** Backend `/api/paper-shadow/trades` (A vs B side-by-side + highlight
   tags) ✅. **Dedicated clickable UI detail view = staged** (summary A/B panel + gate are live).
4. **Custom fee profile visible/used?** ✅ engine uses `fees.fee_rate(profile,…)` + slippage per side;
   CLI `--fee-profile` (bybit_non_vip / conservative_taker / custom). Fee-drag shown in monitor.
   **Dedicated fee-assumptions UI card = staged.**
5. **Maker fills/misses tracked forward?** ✅ engine counters `maker_entry_posted/filled/missed`,
   `taker_fallback_used`, `maker_tp_fills` + a **LIMIT_THEN_TAKER_TIMEOUT** taker-fallback (8 bars).
   Full set: **396 posted / 269 filled / 67.9% fill-rate / 114 missed / 13 taker-fallback**. Surfaced
   in `/api/paper-shadow/forward.maker`; gate **warns** if fill-rate < 50%.
6. **Keeper restart on build-id drift?** ✅ `app_keeper.ps1` now compares on-disk `dist/build_info.json`
   build_id vs served `/api/health.ui_build_id`; on mismatch it runs `launch_robust.ps1` and writes
   `keeper_last_restart.json {reason: build_id_drift}`, surfaced in `/api/health` + the System tab.
7. **Screenshots saved?** Panel/gate/risk/maker verified via **API + DOM eval**; the preview
   screenshot tool timed out late in this long session (no console errors — tooling, not code).
   **Fresh screenshot set = staged**; prior A/B-panel screenshot stands.
8. **Tests pass?** ✅ **15/15** (`test_paper_shadow_engine` 6, `test_paper_shadow_operational` 5,
   `test_stock_intraday_coverage` 4).
9. **Promotion gate still non-executing?** ✅ NOT_READY, `executed=False`, requires explicit sign-off.
10. **Live off?** ✅ `live_locked`, `auto_live_locked`, no orders.
11. **final_r untouched?** ✅.
12. **Remaining TODO?** Dedicated per-trade A/B UI detail view (PART 2 UI) + fee-assumptions UI card
    (PART 3 UI) + fresh screenshot set (PART 6) + auto-daily Telegram send wiring. None block the forward eval.

## Audit (PART 8)
- forward monitor active ✅ · gate NOT_READY & never auto-promotes ✅ · stock DATA_GAP excluded ✅
- per-trade A/B endpoint ✅ (UI view staged) · fee profile used + visible (monitor) ✅
- maker fill realism tracked forward ✅ · keeper build-id-drift restart wired ✅
- live locked ✅ · final_r untouched ✅

## Verdicts
- `STOCK_INTRADAY_DATA_GAP_REDUCED_OR_EXCLUDED_FROM_EDGE_STATS` ✅
- `MAKER_FILL_REALISM_TRACKED_FORWARD` ✅
- `KEEPER_RESTARTS_ON_BUILD_ID_DRIFT` ✅
- `REALISTIC_FEE_PROFILE_VISIBLE_AND_USED` ✅ (monitor; dedicated UI card staged)
- `OPERATIONAL_HARDENING_TESTS_PASS` ✅ (15/15)
- `PROMOTION_GATE_DEFINED_BUT_NOT_EXECUTED` ✅
- `NO_LIVE_EXECUTION_ENABLED` ✅
- `HISTORICAL_FINAL_R_UNCHANGED` ✅
- `APP_SHOWS_PER_TRADE_SHADOW_AB_DETAIL` — endpoint ✅, dedicated UI view staged
- `OPERATIONAL_HARDENING_VISUAL_QA_PASS` — functionally verified (API+DOM); screenshot set staged

## Bottom line
The forward test is now hardened: maker fills are realistically modelled (not 100% free fills),
stock data coverage is classified + DATA_GAP excluded, the keeper self-heals stale bundles on
build-id drift, and the gate + monitor reject the look-ahead backfill. Decide on the FORWARD window
in 2–4 weeks via the promotion gate. Live stays locked.
