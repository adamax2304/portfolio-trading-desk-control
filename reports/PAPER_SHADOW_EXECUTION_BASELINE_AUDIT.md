# PART 1 — Paper-Shadow Execution Baseline Audit

**Verdict: `BASELINE_CONFIRMED_NEW_LOGIC_NOT_YET_EXECUTED`**

| Check | Result |
|---|---|
| Production paper executes OLD logic | ✅ `signal_outcomes.entry_triggered` comes from the tracker's pullback/zone walk (`_evaluate_signal_walk`); TP = `proposed_signals.tp*` (mechanical ATR); stop = `invalidation`; direction = production. |
| New overlays exist + fresh | ✅ `signal_entry_mode` (800), `signal_paper_tp` (1123), `signal_stop_plan` (800), `stock_direction_score` (400). |
| Structural TP/stop affect paper R | ✅ the control-plane lifecycle `blended_r` reads `signal_paper_tp` (ladder) + `signal_stop_plan` (moved stop, `source=structural_stop_plan`). |
| Entry-mode + stock-direction affect paper R | ❌ **No** — they are read-model *labels* only. The tracker still fills at the pullback band and trades the production direction. The breakout/momentum + direction-flip upside is **not yet measured in R**. |
| live locks | ✅ `live_locked=true`, `auto_live_locked=true`. |
| `final_r` untouched | ✅ never written by any overlay. |
| B-book / portfolio compare exists | ✅ `paper_portfolio_ledger` (A/B/C fee profiles) + `/api/portfolio/compare`. |
| Current fee profile | `bybit_non_vip_usdt_perp` (maker 0.0002 / taker 0.00055) + slippage. |

**Conclusion:** structural TP/stop already flow into paper R, but entry-mode and stock-direction
do not. The shadow lane is required to measure the breakout-entry + direction upside in actual R.
`live remains locked`.
