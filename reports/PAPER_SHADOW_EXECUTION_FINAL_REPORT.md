# Paper-Shadow Execution Lane — FINAL REPORT
**Date:** 2026-06-25 · **Posture:** `live_locked=true`, `auto_live_locked=true`, no exchange
execution, no real orders, `signal_outcomes.final_r` never mutated. Measurement lane only.

## What this is
A second (shadow) execution branch that runs the **new strategy logic** in parallel with the
**old production paper logic** on the SAME signals + SAME real OHLCV + SAME fee/sizing model — so
the A/B delta is pure strategy. It exists to **measure** the breakout-entry + multi-factor-direction
upside in actual R (which was previously labels-only), without any live risk.

## 18 questions
1. **Implemented?** `src/execution/paper_shadow_engine.py` (both-branch walker), tables
   `paper_shadow_execution_outcomes` + `paper_shadow_events` + `paper_shadow_meta`, CLI
   `paper-shadow-execution-refresh`, scheduler step, control-plane `paper_shadow.py` +
   `/api/paper-shadow/summary|trades`, System-tab A/B panel, 6 engine tests.
2. **Does B actually execute new entry logic?** Yes — the walker enters per `signal_entry_mode`:
   PULLBACK_LIMIT (zone), STRUCTURAL_RETEST (limit at retest), BREAKOUT_CONTINUATION (taker through
   the level), MOMENTUM_TAKER_NOW (immediate), LIMIT_THEN_TAKER_TIMEOUT (zone), NO_CHASE_SKIP (no
   entry, recorded). Test proves breakout fills where pullback misses.
3. **Does stock-direction affect B?** Yes — stock side comes from `stock_direction_score`; on a flip
   it records `direction_changed/old_side/new_side`; on `neutral` it skips with reason.
4. **Does B use structural TP/stop?** Yes — TP from `signal_paper_tp.active_paper_tp*` (when
   STRUCTURAL/HYBRID), stop moves from `signal_stop_plan` after TP1/TP2.
5. **Maker-first / fee-aware / max-5x?** Yes — limit modes priced maker, taker on market/stop, real
   `fees.fee_rate` + slippage per side, `position_sizing` max-5x at 0.5% risk.
6. **Historical A vs B?** Backfill (608 signals): **A −98.35R / B +125.5R (Δ+223.85R)** after Bybit
   fees — B filled 425, missed 114, skipped 69 (no-chase), 71 direction flips, 421 structural TP.
   ⚠ **This is NOT proof** — see "Critical caveat".
7. **Forward A vs B since activation?** Activated `2026-06-25T01:35`. **Forward = 0/0 today** (no
   signals created after activation yet); it accumulates each cycle. Forward is the only valid number.
8. **Fees?** `bybit_non_vip_usdt_perp` default (maker 0.0002 / taker 0.00055) + slippage; net R/$
   computed after costs; fee profile is a CLI option.
9. **Missed entries logged?** `entry_fill_status=missed` + `missed_entry_reason` + `missed_move_r`
   (the favorable excursion B/A forwent).
10. **DATA_GAP_LATE handling?** Stock-intraday coverage gaps still affect fills; `entry_latency_audit`
    flags them; recommended to exclude from edge stats and backfill early bars (PART 10 — staged).
11. **Risk tab reconciled?** Engine uses $5000 / 0.5% / max-5x (the ledger profile). The Risk-tab
    display reconciliation is **staged** (logged in the session report).
12. **Keeper build-id drift restart?** **Staged** (build stamp makes drift detectable today; the
    auto-restart-on-drift change is the follow-up).
13. **What does the app show?** System-tab **Paper Shadow A/B** panel: forward vs backfill A/B net R,
    B missed/no-chase/dir-flips/structural-TP, activation, and the look-ahead caveat.
14. **What does Telegram show?** **Staged** (the daily A/B summary line is the next add).
15. **Live off?** Yes — `live_locked`, `auto_live_locked`, no orders, no exchange calls.
16. **`final_r` untouched?** Yes — the lane writes only its own tables.
17. **What to watch 2–4 weeks?** The **forward** A vs B net R (after fees), B fill rate, how often B's
    no-chase skips avoid losers, and whether direction flips help. Ignore the backfill number.
18. **Promotion gate?** Forward **B net R > A net R after real fees** on a meaningful forward sample
    (≥ ~60–100 forward trades / ~2–4 weeks), with B not worse on drawdown → only then consider wiring
    the new logic into the production fill path (still paper, still needing explicit sign-off).

## Critical caveat (read this)
The **backfill** A/B (Δ+224R) is **look-ahead contaminated**: the overlays (`signal_paper_tp`,
`signal_entry_mode`, …) were computed on candle windows that include post-signal bars, so using them
in a historical walk lets the structural TPs sit at levels price already reached. **It is a hypothesis,
not evidence.** The engine therefore splits `historical_backfill` from `forward_since_activation`; only
forward (overlays computed at creation on past-only candles, then walked forward) is valid. That is
why the panel shows forward = 0 today and grows from now.

## Verdicts
- `PAPER_SHADOW_EXECUTION_BRANCH_ACTIVE` ✅
- `NEW_ENTRY_LOGIC_EXECUTES_IN_SHADOW_BRANCH` ✅
- `STOCK_DIRECTION_AFFECTS_SHADOW_BRANCH` ✅
- `STRUCTURAL_TP_STOP_USED_IN_SHADOW_BRANCH` ✅
- `REAL_FEES_USED_IN_SHADOW_BRANCH` ✅
- `BACKFILL_AND_FORWARD_METRICS_SEPARATED` ✅
- `APP_SHOWS_PAPER_SHADOW_AB_COMPARISON` ✅
- `NO_LIVE_EXECUTION_ENABLED` ✅
- `HISTORICAL_FINAL_R_UNCHANGED` ✅
- `READY_FOR_2_4_WEEK_FORWARD_EVALUATION` ✅
- `STOCK_INTRADAY_DATA_GAP_REDUCED_OR_EXCLUDED_FROM_EDGE_STATS` — **staged (PART 10)**
- `RISK_TAB_MATCHES_LEDGER_OR_IS_CLEARLY_LABELLED` — **staged (PART 11)**
- `KEEPER_RESTARTS_ON_BUILD_ID_DRIFT` — **staged (PART 12)**
- `TELEGRAM_SUMMARIZES_PAPER_SHADOW_AB` — **staged (PART 9)**

## Done vs staged (honest)
**Done + verified this session:** PART 1 (baseline), 2 (design/tables), 3 (entry execution), 4
(lifecycle), 5 (fees), 6 (CLI + scheduler), 7 (backfill/forward split), 8 (app A/B panel, screenshot),
14 (6 engine tests). **Staged (independent follow-ups, none block the forward eval):** 9 Telegram
line, 10 stock-OHLCV backfill, 11 Risk-tab reconcile, 12 keeper drift restart, 13 Market dedup,
15 full Playwright visual-QA set, 16 separate full-audit doc, 17 broader docs, per-trade A/B detail UI
+ CSV export. The measurement lane is **live and collecting forward evidence now**; the staged items
are quality/coverage improvements, not prerequisites for the 2–4 week read.
