# PART 19 + 20 — Tests + Full Production-Paper Audit

**Verdict: `FULL_PRODUCTION_PAPER_UI_EXECUTION_AUDIT_PASS`**

## Tests (PART 19)
- **New paper-module suites: 22/22 passed** (deterministic, no network) —
  `test_signal_paper_tp` (4) · `test_entry_mode_classifier` (5) · `test_stock_direction_score` (5) ·
  `test_entry_latency_audit` (5) · `test_signal_stop_plan` (3).
- **Full crypto-ai-desk suite: 910 passed, 2 failed** (25m45s). The 2 failures are in
  `tests/test_risk_guard_fields.py` and are **pre-existing + data/date-dependent**, NOT caused by
  this upgrade: they hard-assert `circuit_breaker_state == "would_pause"` but the live account state
  currently computes `"watch"` (the trading day rolled over 06-24→06-25, resetting day-realized-R).
  `circuit_breaker_state` is produced by `src/risk/circuit_breaker.py` + `src/notifiers/paper_entry.py`
  — **neither file was touched this session**; all five new modules are entirely separate. Fix is to
  make those two tests seed account state instead of asserting against live data (flagged, separate
  cleanup; not part of this paper read-model change).
- Backend (`app.lifecycle`, `app.main`) imports clean; frontend builds clean each deploy.

## Data integrity audit
| Table | Rows | Note |
|---|---|---|
| `signal_paper_tp` | 1123 | structural TP, 790/800 structural on the recent window |
| `signal_entry_mode` | 800 | 610 non-pullback |
| `stock_direction_score` | 400 | 400 multi-factor |
| `entry_latency_audit` | 400 | 273 data-gap / 0 detection |
| `signal_stop_plan` | 800 | 418 structural moves |
| `paper_portfolio_ledger` | 2960 | max_leverage=5 all profiles |
| `paper_execution_outcomes` | 1681 | Model-F paper_execution_r |

## Deploy + safety audit
- Health: `ui_build_id` present + matches served bundle; `live_locked=true`, `auto_live_locked=true`.
- All 5 new scheduler steps registered + `command_nonfatal` (never block a cycle).
- Invariants held across every change: `proposed_signals.tp*/entry*/direction` and
  `signal_outcomes.final_r` **never written**; no orders; no scoring/routing/actionability change;
  stocks swing/invest remain paused; C-tier/scalp/stocks-swing-invest not made actionable.

## UI audit (PART 17)
- All 6 nav tabs + bucket/book/window/outcome filters + value-editors + mode-toggles + Manual FAB
  functional; **no dead controls, no console errors**.

## Residual issues (logged, non-blocking)
1. Risk-tab settings ($10k/0.25%) vs derived portfolio ($5k/0.5%) mismatch — reconcile/label.
2. Market "Main Risk Now" repeats the BTC headline for stocks — dedup.
3. Trade-detail chart overlay labels crowd at narrow width — legibility.
4. Stock-intraday early-session OHLCV coverage gap (root of PART 6) — backfill recommended.
5. Edge is fee-fragile (prior finding) — paper-validate before any live consideration.

None block paper operation. `live remains locked`.
