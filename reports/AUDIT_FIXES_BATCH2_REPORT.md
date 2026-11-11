# Audit fixes — Batch 2 (engine correctness / look-ahead / dirty-cohort)
**Date:** 2026-07-01 · paper/read-model only · live+auto+manual-live **hard-locked** · `signal_outcomes.final_r` **untouched**.

## Done this batch (crypto-ai-desk engine + tests)

### #6 — Look-ahead-safe overlay context (`src/execution/signal_paper_tp.py`, `signal_stop_plan.py`)
**Bug:** `_candles_for` did `.tail(200)` on the rolling OHLCV cache with **no `created_at` filter** →
structural TP/stop levels were placed using candles that appeared **after** the signal was created
(look-ahead contamination in backfilled overlays). **Fix:** `_candles_for` now accepts `created_at` and
keeps only `timestamp <= created_at` (the mirror of the tracker's `_filter_candles_after`, which walks
OUTCOMES on `>= created_at`). Threaded `created_at` through `_entry_triggered_signals` → both the TP and
stop overlays. After recompute: TP set = STRUCTURAL 493 / HYBRID 63 / **ATR_FALLBACK 244** (some old
signals honestly fall back to ATR because look-ahead-free pre-signal candles aren't in the rolling cache).

### #8 — Exclude DATA_GAP_LATE from primary edge metrics (`src/execution/paper_shadow_monitor.py`)
`forward_quality` now joins `entry_latency_audit.cause='DATA_GAP_LATE'` and **excludes that cohort** from
the A/B edge books; reports `data_gap_late_excluded_signals` + `forward_signals_total` + a `primary_cohort`
label, and warns when the cohort share > 20%. **Live finding: 116 of 215 forward signals (54%) are
DATA_GAP_LATE** (stock intraday coverage gaps) — previously polluting the edge; now the primary cohort is
99 clean signals (B 66 trades). Warning fires. (Data_gap close-reason exclusion already existed; this adds
the entry_latency_audit cohort.)

### #9 — Structural stop sanity bound (`src/execution/signal_stop_plan.py`)
Added `SANITY_MAX_STOP_R = 15.0` + a `sanity_review` column (with migration). A `stop_after_tp` that
"locks" > 15R is not a plausible structural level → flagged `sanity_review=1` + `[REVIEW: …]` appended to
`reason`, instead of silently trusting absurd structure detection. Current data: **0 flagged** (all sane) —
the guard stands for the future.

## Tests — `tests/test_audit_fixes_engine.py` (3/3 ✅)
`#6` future bars dropped when `created_at` given (kept when None); `#9` 25R protection → `sanity_review=1`,
2R → 0; `#8` synthetic DB — DATA_GAP_LATE signal excluded, clean B net_r reflects only the clean trade.
Regression: crypto shadow+operational+coverage+safe-obs **25 passed**. compileall clean.

## Files changed
- `crypto-ai-desk/src/execution/signal_paper_tp.py` (#6)
- `crypto-ai-desk/src/execution/signal_stop_plan.py` (#6 + #9 + migration)
- `crypto-ai-desk/src/execution/paper_shadow_monitor.py` (#8)
- `crypto-ai-desk/tests/test_audit_fixes_engine.py` (new)

## Status across all 12 audit items
| # | Item | State |
|---|---|---|
| 1 | fees vs slippage split (API) | ✅ Batch 1 |
| 2 | actionability stale_before_entry / entry_moved_away | ✅ Batch 1 |
| 3 | crypto/stocks split — **display** | ✅ Batch 1 · **compute (stock fee profile) staged** |
| 4 | slice-aware portfolio accounting | ⏳ staged (largest rewrite) |
| 5 | forward vs backfill separation | ✅ verified |
| 6 | look-ahead in overlays | ✅ Batch 2 |
| 7 | maker trade-through fill model | ⏳ staged (timeout→taker + counters exist; trade-through pending) |
| 8 | DATA_GAP_LATE exclusion | ✅ Batch 2 (crypto monitor + digest) · **control-plane forward endpoint mirror pending** |
| 9 | structural stop/TP sanity | ✅ Batch 2 (stop bound) · vp_supported display-guard pending |
| 10 | funding/carry for crypto perps | ⏳ staged (with #3-compute in paper_portfolio.py) |
| 11 | A/B compare freshness/integrity | ✅ Batch 1 |
| — | frontend render of splits/warnings | ⏳ staged |

## Remaining plan (each deserves a focused pass)
- **#3-compute + #10** — asset-aware cost model in `crypto-ai-desk/src/execution/paper_portfolio.py`
  (stock/ETF commission+slippage; approximate funding across intervals for crypto perps; `funding_known`),
  then rebuild ledger.
- **#4** — slice-aware accounting reusing `paper_shadow_engine` slice events (entry type, TP partials,
  stop/expired remainders, maker-TP vs taker-stop). Biggest, most careful change.
- **#7** — maker fill on bps/ticks trade-through (not touch) + post-only miss.
- **control-plane #8 mirror** + **#9 vp_supported display guard** + **frontend** labels.
