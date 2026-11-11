# Audit Fixes — Batch 4 (final)

Date: 2026-07-02 · Scope: paper / read-model only · **Live, auto-live, manual-live remain HARD-LOCKED** ·
`signal_outcomes.final_r` untouched · `paper_execution_r` remains the authoritative paper R.

This batch closes the remaining directive items (#4, #7), mirrors #8 into the control plane,
adds the #9 VP guard, refreshes the #11 A/B book, and ships the **frontend UI** that surfaces the
honest execution-cost model. All 12 audit items are now code-complete, tested, and deployed.

---

## Items completed in this batch

### #4 — Slice-aware exit accounting (maker-TP vs taker-stop)
- `crypto-ai-desk/src/execution/fees.py::trade_costs(..., exit_slices=…)` — when exit slices are given,
  the close fee is the sum over `(fraction, order_type)` slices; a blended close-rate is reported.
- `crypto-ai-desk/src/execution/paper_portfolio.py` — `_PARTIALS={1:.33,2:.33,3:.34}`, `_exit_slices(t)`
  builds `[(frac,"maker") for each TP hit] + [(remaining,"taker")]`; records `exit_maker_fraction`.
- `scripts/paper_portfolio_backfill.py` passes `tp1_hit/tp2_hit/tp3_hit` through to the slicer.
- Effect (verified): winners exit ~maker (cheaper TP limits), stops/expiries exit taker.
  Test: `test_trade_costs_exit_slices_blended`, `test_portfolio_exit_maker_fraction`.

### #7 — Maker fill realism (trade-through, not touch)
- `crypto-ai-desk/src/execution/paper_shadow_engine.py::_entry_fill` — limit entries now require a
  **trade-through** (`_MAKER_TRADE_THROUGH_BPS`), else post-only MISS. Open-inside-zone fills at open.
  Test: `test_maker_fill_requires_trade_through`. Forward maker fill-rate now realistic (<100%).

### #8 (control-plane mirror) — DATA_GAP_LATE excluded from forward edge
- `trading-desk-control/backend/app/paper_shadow.py::forward_monitor` — loads DATA_GAP_LATE signal ids
  from `entry_latency_audit` (column is `cause`, stocks-intraday only), removes them from the forward
  cohort, and returns `data_gap_late_excluded` + `primary_cohort` + a warning.
  Verified live: **116 DATA_GAP_LATE signals excluded**, clean forward B ≈ 69–72 trades.
  (Desk-side twin `paper_shadow_monitor.forward_quality` was done in batch 3.)

### #9 — Volume-profile guard in the lifecycle read-model
- `trading-desk-control/backend/app/lifecycle.py::_read_paper_tp` selects `volume_profile_supported`
  and exposes `vp_active`, so the UI never claims VP support when `volume_profile_supported=0`.
  (Structural stop/TP sanity bound `SANITY_MAX_STOP_R` + `sanity_review` flag were done in batch 3.)

### #11 — Fresh, like-for-like A/B comparison
- Rebuilt the `bybit_structural_maker_first` B-book via `scripts/structural_maker_backfill.py`
  (paper/derived; never touches `signal_outcomes`). 642 B-rows persisted for the same trade set.
- `portfolio.py::portfolio_compare` now attaches `comparison_integrity` (comparable flag, common-trade
  count, per-side trade counts + latest timestamp, staleness/trade-set-mismatch warnings).
  Verified live: **comparable=True, 642 common trades, no warnings**.

### Frontend UI — honest execution-cost model (last directive item)
Files: `frontend/src/types.ts`, `api.ts`, `query.ts`, `screens.tsx`.
- **#1 cost split** — the old single "Fees Paid" card is replaced by an **Execution Cost** card that
  shows `exchange fees / slippage / funding` as **three distinct values**. Slippage is never labeled
  a "fee". Verified in the UI: `Execution Cost $1533 · fees $417 · slippage $1025 · funding $91`.
- **#3 per-asset** — new "Per-asset P&L" block renders crypto vs stocks **separately** with each
  asset's own net + cost split + a cost-model-appropriate flag. Live: crypto +$883 / stocks −$336.
- **#10 funding** — surfaced as its own line (`funding $91`, or `n/a` when `funding_known=false`).
- **#11 integrity** — the A/B panel renders a comparability line (✓ like-for-like / ⚠ warnings).
- **#8 DGL** — the Shadow A/B screen renders the DATA_GAP_LATE-excluded count + clean-cohort note.
- New endpoint `/api/portfolio/by-asset` wired via `usePortfolioByAsset`.

---

## Deploy state
- Frontend rebuilt (`npm run build`, clean tsc+vite). Live backend already serves the new bundle
  (`index-B4gZYV98.js`) **and** the new Python (split fields + `/api/portfolio/by-asset` live).
- Production control plane on `:8000` healthy throughout; **live remains LOCKED** (badge verified).
- UI verified via a throwaway auth-disabled dev instance on `:8011` (read-only against the real desk
  DB, killed after). Screenshots: `reports/audit_batch4_home.png`, `reports/audit_batch4_costsplit.png`.

## Verification
- Audit tests: `crypto-ai-desk/tests/test_audit_fixes_engine.py` **8/8**;
  `backend/tests/test_audit_fixes.py` **6 passed / 1 skipped**.
- Endpoint smoke (live + dev): summary split, by-asset, compare-integrity, forward DGL all correct.

## Regression state
- **backend full suite: 80 passed, 9 skipped, 0 failed.** Two `test_books.py` d7-window tests were
  failing only because they hardcoded `exit_at=2026-06-20`, which aged out of the rolling 7-day
  window by 2026-07-02. Fixed (test-only, zero product risk): anchored to a `now-2d` `_RECENT`
  timestamp so they stay inside the window on any run. `books.py` product code untouched.
- **crypto-ai-desk full suite: 936 passed, 9 failed — pre-existing, NOT caused by this audit.**
  The 9 are in `test_catalyst_layer.py`, `test_entity_aliases.py`, `test_risk_guard_fields.py` —
  subsystems the audit never touched. They import none of the changed modules and fail identically
  in isolation (environment/data-dependent). Left as-is on purpose: out of the paper-accounting
  scope, and the risk-guard circuit-breaker case is live alert-path code that should not be changed
  under this directive. Flagged here for a separate pass.
- Audit-specific tests all green: `tests/test_audit_fixes_engine.py` 8/8, `tests/test_audit_fixes.py`
  6 passed / 1 skipped.
