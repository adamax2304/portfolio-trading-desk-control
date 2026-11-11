# Legacy `final_r` / touch-R purge — USD-net is the authoritative profitability

Date: 2026-07-02 · Scope: paper / read-model / control-plane only · Live/auto-live/manual-live
HARD-LOCKED · `signal_outcomes.final_r` NEVER mutated (it stays the raw source of the legacy
touch metric; only its USE in profitability/PnL/stats was removed).

## Rule enforced
- `final_r` = legacy touch (highest-TP-touched) metric ONLY — optimistic, signal-quality.
- It is **never summed as PnL**, never a headline result, never shown as a "result R" without an
  explicit `legacy_touch_r` label.
- Authoritative profitability: **USD net** (`paper_portfolio_ledger.net_pnl_usdt`, where
  `gross − exchange_fees − slippage − funding = net`). Authoritative paper R: `paper_execution_r`.
- R kept only as auxiliary diagnostics: `paper_execution_r`, `legacy_touch_r`, `touch_minus_paper_r`.

## The one root that mattered (crypto-ai-desk)
`src/signals/analytics.py::_accumulate` summed `final_r` into `sum_r / sum_positive_r /
sum_negative_r_abs`, so `total_r / average_r / profit_factor` — the headline of **every** report,
LLM packet, CLI `signal-stats`, and Obsidian review — were touch-based/optimistic.
- Fixed: `_accumulate` now sums the honest **paper-execution R** (Model F) via a new
  `_paper_execution_r(signal, outcome)` helper (reconstructs R from the recorded path using
  `paper_execution_accounting.compute_paper_execution`; skips not-entered/open). The legacy touch
  total is kept SEPARATELY as `sum_legacy_touch_r` and surfaced as the labelled
  `legacy_touch_total_r`. `avg_r` now averages over `paper_resolved` (paper trades), and the
  summary adds `paper_resolved` + `risk_model`. Winrate (wins/triggered) was already label-based.
- Transitively corrects: `report_section.build_signal_performance_block`, `analysis/packet`,
  `stocks/llm_packet`, `cli signal-stats`, `obsidian_export` review, `analytics.observations()`.

## Direct-display relabels (crypto-ai-desk)
- `notifiers/close_alert.py` — the Telegram close-alert headline no longer leads with the touch R.
  "Result" now points to **Paper exec R (Model F) + Paper $ net** (both already computed below);
  the touch is a single labelled line `(legacy touch … · optimistic · NOT PnL)`; the touch-derived
  `sized_r` was dropped from the headline.
- `status/display_status.py` — terminal labels now read `✅ CLOSED WIN +X.XR (legacy touch)` and
  `format_r_with_lifecycle` returns `…R (legacy touch)`.
- `signals/obsidian_export.py` — per-signal journal line relabelled `Legacy touch R (optimistic,
  NOT PnL)`.
- `cli.py` — outcome-history / updates table columns renamed `final_R`/`final_r` → `touch_R(legacy)`.
- (KEPT: `tracker.py`/`models.py`/`sqlite.py` write & store `signal_outcomes.final_r` — the source;
  `paper_execution_accounting`, `paper_shadow_engine` use their own honest R; `circuit_breaker`
  `day_realized_r` is an alert-only diagnostic.)

## Control-plane (trading-desk-control)
- `books.py::_summ` — dropped the `realized_r` alias and the `touch_r` key; the touch total is
  exposed ONLY as `legacy_touch_r` (+ `touch_minus_paper_r`, `paper_execution_r`). The dashboard
  headline renames `today_touch_r`/`h48_touch_r` → `today_legacy_touch_r`/`h48_legacy_touch_r`,
  adds `authoritative_metric = "usd_net_after_fees_slippage_funding"`, and the label now states
  USD-net is authoritative and Legacy Touch R is "optimistic, NEVER PnL".
- `desk_adapter.py` — per-trade rows drop `realized_r`/`touch_r`; expose `legacy_touch_r` only.
- `portfolio.py` — chart_events `touch_r` key → `legacy_touch_r`.
- `display_status.py` — terminal operator label R relabelled `(legacy touch)`.

## Frontend (trading-desk-control)
- `types.ts` — `Signal.realized_r`/`touch_r` → `legacy_touch_r`; `BookWindow.touch_r`/`realized_r`
  → `legacy_touch_r`; headline `today_touch_r`/`h48_touch_r` → `…legacy_touch_r` + `authoritative_metric`.
- `screens.tsx` — "Recorded Touch R" card → **"Legacy Touch R"** (sub: "optimistic · NOT PnL
  (diagnostic)"); trade rows / near-winner / detail now lead with `paper_execution_r` (fall back to
  "—", never an unlabelled touch); the secondary touch is labelled "legacy touch". Paper Equity /
  Today Net $ (USD) remain the top headline cards.
- `components.tsx` — trade card leads with `paper_execution_r`, not `final_r`.
- The lifecycle event `realized_r` (blended partial-exit R) is untouched — it is not the touch metric.

## Tests
- New: `test_paper_execution_uses_actual_tp2_r_not_nominal` (a TP2 fill worth **+1.6667R** is booked
  as 1.6667, never a nominal 2R) and `test_analytics_sums_paper_execution_not_final_r`.
- New (backend): `test_portfolio_profitability_is_usd_net` (no `realized_r`/`final_r`/`touch_r` keys;
  USD-net present) and `test_dashboard_headline_usd_authoritative_and_legacy_r_renamed`.
- Updated: `test_books.py` (legacy_touch_r keys + `authoritative_metric`), `test_ab_headline_reporting.py`
  fixtures enriched with TP/MFE geometry so paper-execution R reproduces the +5 / PF6 headline (proving
  the numbers now come from paper R, not final_r), `test_display_status.py` labels.

## Acceptance criteria
- Nowhere in profitability/equity/dashboard/cohort stats is `final_r` summed — the only summer
  (`analytics._accumulate`) now sums paper-execution R; cohort stats use `net_pnl_usdt` + paper R.
- Main system evaluation is USD net after fees/slippage/funding (Paper Equity / Net PnL headline).
- `final_r` survives ONLY as a debug/legacy-touch metric under explicit `legacy_touch_r` labels.
- Live / auto-live / manual-live: LOCKED.

## Verification
- Backend suite: **84 passed, 10 skipped, 0 failed** (no PYTHONPATH hack).
- Crypto engine audit tests: **13 passed**; A/B headline **6 passed**.
- Frontend `npm run build`: clean (tsc + vite).
- Full crypto-ai-desk suite: **950 passed, 0 failed** (the only affected tests — display-status
  labels, two close-alert Telegram wordings, and the A/B headline fixtures — were updated for the
  new paper-R headline + legacy labels; confirmed green).
