# PART 2 — Previous Paper Features Wired Into the Production Paper Path

**Verdict: `PREVIOUS_PAPER_FEATURES_WIRED_IN_PRODUCTION_PAPER_PATH`**

Each previously-built paper engine is now persisted per-signal and consumed by the production
paper read-model (lifecycle → API → UI) and the 2-hourly scheduler — not left as dead code.

## Feature matrix

| Capability | Engine (crypto-ai-desk) | Persisted table | Scheduler step | Lifecycle/API + UI | Verified |
|---|---|---|---|---|---|
| Structural TP vs ATR ladder (PART 3) | `execution/structural_tp_engine.py` + `signal_paper_tp.py` | `signal_paper_tp` (1123) | `paper-tp-refresh` | `paper_tp` + ladder `TP: STRUCTURAL` | 790/800 structural |
| Breakout/momentum entry modes (PART 4) | `entry_mode_classifier.py` | `signal_entry_mode` (800) | `entry-mode-refresh` | `entry_mode` badge | 610/800 non-pullback |
| Multi-factor stock direction (PART 5) | `stocks/stock_direction_score.py` | `stock_direction_score` (400) | `stock-direction-refresh` | `stock_direction` badge | 400/400 multi-factor; MSTR·BTC |
| Entry-latency root cause (PART 6) | `signals/entry_latency_audit.py` | `entry_latency_audit` (400) | `entry-latency-audit` | `entry_latency` badge | 273 data-gap / 0 detection |
| Structural stop movement (PART 8) | `execution/structural_stop_manager.py` + `signal_stop_plan.py` | `signal_stop_plan` (800) | `paper-stop-refresh` | `stop_protection` badge | 418 structural moves |
| Max-5x safe leverage (PART 9) | `execution/position_sizing.py` + `config/paper_portfolio.yaml` | `paper_portfolio_ledger` (2960) | `paper_portfolio_backfill` | Home `max 5x`, compare `max_5x_safe` | max_leverage=5 |
| Partial-exit lifecycle 33/33/34 (PART 7) | `backend/app/lifecycle.py` | derived live | (read-model) | partials + price ladder | TP1/2/3 fills |
| Maker-first + fee-aware (B-book) | `maker_first_execution.py` + `fee_aware_execution.py` + `structural_maker_backfill.py` | `paper_portfolio_ledger` (B profile) | `structural_maker_backfill` | compare A/B | maker_fills>0 |
| Model-F paper execution R | `execution/paper_execution_accounting.py` | `paper_execution_outcomes` (1681) | `paper-execution-refresh` | `paper_execution_r` | beside legacy final_r |

## Scheduler chain (each 2h cycle, after reports/monitor)
`catalyst label refresh → paper execution refresh → paper structural TP refresh → paper stop plan →
paper entry-mode classify → paper stock direction → entry latency audit → ohlcv archive →
intelligence update`. All steps are `command_nonfatal` (a failure never blocks the cycle).

## Boundary held
Every wired engine is **add-only / read-model**: separate additive tables, consumed by the paper
lifecycle/UI. None mutate `proposed_signals.tp*/entry*/direction` or `signal_outcomes.final_r`,
none place orders, none change scoring/routing/actionability. `live_locked=true`,
`auto_live_locked=true` throughout.
