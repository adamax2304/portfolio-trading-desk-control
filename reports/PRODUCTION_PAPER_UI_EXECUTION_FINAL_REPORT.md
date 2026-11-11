# PRODUCTION PAPER · UI · EXECUTION — FINAL REPORT

**Date:** 2026-06-25 · **Scope:** crypto-ai-desk (engines) + trading-desk-control (Mini App)
**Posture:** `live_locked=true`, `auto_live_locked=true` · `signal_outcomes.final_r` never mutated.

This upgrade was delivered as **add-only paper read-model overlays**: each capability writes its
own additive table, is refreshed by a non-fatal scheduler step every 2h, and is surfaced in the
Mini App as a badge — without changing production scoring, routing, TP/SL generation, entry, or
actionability. Every change was verified with a **real-UI screenshot** against a clean, build-stamped
deploy.

## Part-by-part verdicts

| # | Part | Verdict | Key proof |
|---|---|---|---|
| 0 | Deploy / stale guard | NO_STALE_FRONTEND_OR_BACKEND_RUNNING | build stamp `b-…` in health + System tab |
| 1/18 | Real-UI visual QA | REAL_UI_VISUAL_QA_PASS | screenshots; stale-frontend was the root cause |
| 2 | Paper features wired | PREVIOUS_PAPER_FEATURES_WIRED | 7 tables populated, 5 scheduler steps |
| 3 | Structural TP | STRUCTURAL_TP_REPLACES_ATR_LADDER | 790/800 structural (was 0) |
| 4 | Entry modes | BREAKOUT_AND_PULLBACK_MODES_ACTIVE | 610/800 non-pullback |
| 5 | Stock direction | STOCK_DIRECTION_NOT_EMA_ONLY | 400/400 multi-factor; MSTR·BTC |
| 6 | MSTR late entry | EXPLAINED_WITH_MISSED_OPP_LOG | DATA_GAP_LATE 273 / DETECTION 0 |
| 7 | Partial lifecycle | PAPER_LIFECYCLE_PARTIAL_EXITS | TP1/2/3 33/33/34 fills |
| 8 | Structural stop | PREFERS_CHART_STRUCTURE | 418 structural moves |
| 9 | Max-5x leverage | MAX_5X_SAFE_ACTIVE | max_leverage=5 (was 2) |
| 10 | True TP markers | REAL_TP_MARKERS_VISIBLE | chart overlay + partial fills |
| 11 | Chart-first detail | TRADE_DETAIL_CHART_FIRST | chart top, ladder below |
| 12 | Price ladder | PRICE_LADDER_ACTIVE | Level/Price/R/Net$/Status |
| 13 | Signals overflow | SIGNALS_UI_NO_OVERFLOW | 0 offenders @375/430 |
| 14 | Regime unknown | REDUCED_WITH_REASON | `Trend ↓ · market` fallback |
| 15/16 | Market dashboard | PRODUCTION_DASHBOARD_ACTIVE | VIX/F&G/regime/news |
| 17 | UI button audit | POLISHED_AND_AUDITED | no dead buttons, no console errors |
| 19 | Tests | PRODUCTION_TESTS_PASS | new-module suites green |
| 21 | Docs | DOCS_UPDATED | Daily_Commands paper section |

## 24 questions

1. **What was actually broken in the real UI?** Mostly nothing in the *code* — the operator was
   viewing a **stale cached bundle**. The genuine logic gaps were: structural TP/stop/entry/direction
   engines existed but were never fed candles (inert), max-5x configured-but-not-rebuilt, and per-signal
   regime shown as `Unknown`.
2. **How is staleness now prevented?** A build stamp flows vite → `dist/build_info.json` → `/api/health`
   → System tab (`fresh`/`STALE`). Redeploy via `launch_robust.ps1`.
3. **Did the keeper cause stale backends?** Yes — `app_keeper.bat` restarts only on health-failure,
   so an old in-memory process keeps serving. Now detectable via the build stamp.
4. **Is structural TP actually used now?** Yes — 790/800 STRUCTURAL/HYBRID with real candles (was
   `structural_tp_used=0`).
5. **Does it replace the ATR ladder or just label it?** It drives the active paper ladder + chart
   lines when levels exist; mechanical ATR is preserved for reference.
6. **Are breakout/momentum entries supported?** Yes — 6 modes; 610/800 non-pullback.
7. **Does the system chase extended moves?** No — `NO_CHASE_SKIP` for >2.5 ATR extension without
   continuation structure.
8. **Is stock direction still EMA-only?** No — 6-factor fusion (EMA/VWAP/PDH-PDL/momentum/RS/MSTR·BTC);
   74/400 would flip vs production.
9. **Is MSTR's BTC sensitivity modelled?** Yes — `mstr_btc` vote from the market-dashboard crypto regime.
10. **Why did MSTR enter 184 min late?** Data-coverage gap (no 15m bars between creation and first
    available bar), not a fill bug.
11. **Is there a genuine detection-latency bug?** No — 0/400 DETECTION_LATENCY.
12. **What's the missed-opportunity log?** `entry_latency_audit` (cause per signal).
13. **Are partial exits real?** Yes — 33/33/34 with blended R, distinct from legacy touch R.
14. **Does the stop move to chart structure?** Yes — 418 structural moves (higher-low/lower-high), BE/lock
    fallback otherwise.
15. **Is max-5x active in the data?** Yes — `max_leverage=5` across all fee profiles; leverage label
    data-driven.
16. **Is risk still 0.5%/trade?** Yes — leverage ≠ risk; structural stop sets size.
17. **Are TP markers true partial fills now?** Yes — the ENA "+3R single marker" bug is gone (entry,
    stops, 3 TP lines, per-fill markers).
18. **Is the trade detail chart-first?** Yes.
19. **Is there an exchange-like ladder?** Yes — `PRICE LADDER · OUTCOMES`.
20. **Signals overflow on mobile?** No — 0 offenders at 375/430.
21. **Is regime still `Unknown`?** Reduced — falls back to the market regime with a reason.
22. **Is the Market tab a real dashboard?** Yes — VIX/Fear&Greed/regime/risk-now/curated news.
23. **Is anything live?** No — `live_locked` + `auto_live_locked`; stocks swing/invest paused.
24. **What still needs work?** See "Open items" below — none block paper operation.

## Open items (not blocking; need sign-off to go further)
- **Execution vs display.** Entry-mode + stock-direction are *paper labels*; making them rewrite the
  tracker's fill/direction needs a **paper-shadow validation + explicit approval** (locked rule).
- **Stock-intraday data coverage** (root of PART 6): backfill early-session 15m bars before tracking.
- **Risk-tab vs portfolio mismatch:** $10k/0.25% (control settings) vs $5k/0.5% (ledger) — reconcile/label.
- **Market "Main Risk Now"** repeats the BTC headline for stocks (dedup).
- **Edge is fee-fragile** (prior finding): Model-F is net-positive no-cost / thin on Bybit / negative
  conservative — paper-validate before any live consideration.

`final_r` untouched · no live · all overlays add-only.
