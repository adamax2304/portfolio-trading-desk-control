# Legacy-R / PnL audit — residual fixes

Date: 2026-07-02 · Scope: paper / read-model / UI / reporting only · **Live/auto-live/manual-live
HARD-LOCKED** · `signal_outcomes.final_r` never mutated historically.

Single contract enforced everywhere:
1. **Authoritative profitability = USD net** (`paper_portfolio_ledger.net_pnl_usdt`,
   `gross − exchange_fees − slippage − funding`).
2. **Auxiliary realistic R = `paper_execution_r`**.
3. **Legacy `final_r`/touch = `legacy_touch_r`** — diagnostic/signal-quality only, never PnL, never
   headline.

## Files changed

### 1 — Backend books contract (`backend/app/books.py`)
- `paper_exec_flags()` emitted `"touch_r"` on every trade row (via `desk_adapter` `s.update(...)`) —
  renamed to `"legacy_touch_r"`. This was the last PnL-facing legacy key.
- `_summ()` already exposes only `legacy_touch_r` / `paper_execution_r` / `touch_minus_paper_r`
  (no `touch_r`/`realized_r`). Headline already carries `today/h48/d7_paper_execution_r`,
  `today/h48_legacy_touch_r`, `today_touch_minus_paper_r`, `authoritative_metric =
  "usd_net_after_fees_slippage_funding"`; back-compat `today_operator_r`/`h48_operator_r` point at
  `paper_execution_r` (not legacy touch). The internal `realized_r()`/`touch_r()` **functions** are
  kept as touch calculators (not output keys).

### 2 — Backend tests
- `test_books.py` already asserts the new contract (`legacy_touch_r`, `authoritative_metric`,
  `"realized_r"/"touch_r" not in` window). New `test_legacy_r_contract.py` (see #7).
- Required trio green: `test_audit_fixes.py + test_shadow_ab_visibility.py + test_books.py` → **33 passed**.

### 3 — Frontend types (`frontend/src/types.ts`)
- Already migrated: `Signal`/`BookWindow`/headline `touch_r`/`realized_r` → `legacy_touch_r`;
  `today/h48_legacy_touch_r`. Lifecycle-event `realized_r` (blended partial-exit R) kept — it is
  not the touch metric.

### 4 — Frontend screens/components
- New `isClosedTrade(s)` helper (in `components.tsx`) determines "closed" from
  `outcome_class`/`display_status`/`close_time`/`paper_execution_r` — **never `final_r`**. Used by
  `TradeCard`, `partialLifecycle`, the "Latest desk events" row, and the signal-detail header.
- `TradeCard` / rows lead with `paper_execution_r` (fall to "—"); tone no longer references
  `final_r`. Book header now labels the number **"Paper Exec R"** and adds a
  **"Legacy Touch R … optimistic · not PnL (diagnostic)"** line. `ClosedRow`/detail main R =
  `paper_execution_r`, secondary = `legacy_touch_r` (faint "legacy touch"). `final_r` remains only
  as an explicitly-labelled "legacy touch" secondary string.
- Frontend `npm run build`: clean (tsc + vite).

### 5 — Legacy report scripts (crypto-ai-desk)
- `scripts/write_obsidian_current_state_dashboard.py` (active via scheduler): "Today/48h P&L (raw R)"
  → "Today/48h **legacy-touch R (optimistic · NOT PnL)**" + a disclaimer pointing to USD net /
  `paper_execution_r`; `fmt_stats` `netR` → `legacyTouchR (… NOT PnL)`; playbook table header
  `netR`→`legacyTouchR` + disclaimer; per-trade "R:"/"Current R" → "Legacy touch R (not PnL)".
- `scripts/refresh_obsidian_dashboard.py` (active via scheduler): metric **legend** now defines
  Avg R/Total R as **legacy touch R (optimistic, NOT PnL)** and states authoritative PnL = USD net;
  headline cohort `netR` column relabelled + disclaimer.
- `scripts/build_live_shadow_journal.py`: **NOT in the active scheduler** (`run_default_market_schedule`
  does not call it) — left unchanged and documented here as a manual/one-off diagnostic (see
  "remaining legacy refs"). Both edited scripts syntax-checked OK.

### 6 — Fee/profile labelling bug (`backend/app/portfolio.py::portfolio_by_asset`)
- `fee_profile_used` was hard-set to the passed `fee_profile` (bybit) for both assets. Now derived
  from the ledger's `fee_source`: **stocks → `stock_etf_default`** + `fee_model_label =
  "US equity/ETF paper model (commission-free + ~1bp; no perp funding)"`, funding 0; crypto → perp
  profile. Verified live: stocks `fee_profile_used='stock_etf_default'`, funding $0; crypto
  `bybit_non_vip_usdt_perp`, funding $92.98. Stale "placeholder crypto-perp" note removed.

### 7 — Guardrail tests (`backend/tests/test_legacy_r_contract.py`, 10 tests)
- TestClient: `/api/dashboard/summary` returns `*_paper_execution_r` + `*_legacy_touch_r` +
  `authoritative_metric`, and **no** `today_touch_r`/`realized_r`; book window has `legacy_touch_r`
  but not `touch_r`/`realized_r`.
- `/api/portfolio`, `/portfolio/compare`, `/portfolio/by-asset`, `/paper-shadow/summary|forward|fees`
  all return **200** and assert `live_locked` / `auto_live_locked` true where present.
- by-asset stocks: not a bybit label + `funding_usdt == 0`.
- Unit: a trade with **legacy touch +1R but paper-exec 0R** → headline `today_paper_execution_r == 0.0`
  (main) and `today_legacy_touch_r == 1.0` (secondary); `paper_exec_flags` has no `touch_r`.
- `BookWindow` (all books/windows) has no `realized_r`/`touch_r`.

## Verification
- `python -m pytest backend/tests/test_audit_fixes.py backend/tests/test_shadow_ab_visibility.py backend/tests/test_books.py -q` → **33 passed**.
- Full backend suite: **93 passed, 11 skipped, 0 failed** (no PYTHONPATH hack).
- Frontend `npm run build`: clean. Backend redeployed on :8000 (healthy).

## Acceptance criteria
- ✅ Backend targeted tests green · ✅ frontend build green · ✅ API endpoints 200.
- ✅ No user-facing headline/card/book-row uses `final_r`/`realized_r`/`touch_r` as PnL.
- ✅ Active Obsidian reports no longer present `final_r` as profitability (labelled legacy touch,
  not PnL; authoritative USD net referenced).
- ✅ Live remains LOCKED.

## Remaining legacy `final_r` references (justified)
- `scripts/build_live_shadow_journal.py` — sums `final_r` for a manual shadow-journal; **not in the
  active scheduler / monitoring**, so left unchanged. Should it be reactivated, relabel its R as
  `legacy_touch_r` first.
- `books.realized_r()` / `books.touch_r()` **functions** and `signal_outcomes.final_r` writes
  (tracker/models/sqlite) — the SOURCE of the legacy metric; kept by design.
- Lifecycle event `realized_r` (control-plane + UI) — the blended partial-exit execution R, not the
  touch metric; kept.
- Static narrative commentary strings in the Obsidian scripts (e.g. "+84R / PF 2.17") — historical
  annotations, not live sums.
