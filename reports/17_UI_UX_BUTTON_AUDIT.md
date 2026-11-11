# PART 17 — UI/UX Polished + Buttons Audited

**Verdict: `APP_UI_UX_POLISHED_AND_BUTTONS_AUDITED`** — every tab navigated, every button
exercised, no console errors, no dead controls.

## Navigation (bottom nav — all functional)
`Home · Signals · Trades · Market · Risk · System` — all 6 present and switch correctly.
No console errors at `error` level across the whole walk.

## Per-screen button inventory
| Screen | Controls | Status |
|---|---|---|
| Home | header pause/FAB, `+ Manual` | render + clickable |
| Signals | asset chips `All/Crypto/Stocks`, status chips `All/Actionable/Shadow/Late/Closed`, per-card `Chart` / `Not actionable` | all filter; no overflow at 375/430 |
| Trades | bucket tabs `Open/Pending/Closed/Shadow`, book tabs `Operator/Paper/Shadow`, window `Today/48h/7d`, outcome chips, trade rows → detail | all navigate |
| Trade detail | `← Back`, chart, ladder | back works; chart-first |
| Market | scroll dashboard (no actions — read-only) | renders |
| Risk | tap-to-edit `Paper balance / Risk·trade / Daily cap / Weekly cap / Max positions / Max sector`, mode toggles `disabled/paper/manual_live/auto_live`, allowed-mode toggles | editable; **live & auto-live locked** with reason shown |
| System | build-stamp card, health rows | renders; `BUILD: fresh` |
| Manual (FAB) | manual-trade entry | opens |

## Safety surfacing (good)
- Risk tab: *"Live & auto-live are locked — require a 30-day forward-validation readiness audit."*
- Allowed modes (paper): crypto intraday/swing/short + stocks intraday **enabled**; stocks swing/invest
  **paused** — matches the locked policy.
- Global `LIVE LOCKED` badge in the header on every screen.

## Issues found (logged)
1. **Paper-balance/risk mismatch (real)** — the Risk tab shows **$10,000 / 0.25%** (editable
   control-DB settings) while Home + the derived portfolio use **$5,000 / 0.5%** (the Model-F ledger
   assumptions). Two different "paper balance / risk per trade" surfaces can confuse the operator;
   they should be reconciled or cross-labelled ("display sizing" vs "ledger assumption").
2. **Market "Main Risk Now"** repeats the same BTC headline for both Crypto and Stocks (selection/
   dedup) — cosmetic.
3. **Trade-detail chart overlay labels** crowd at narrow width (legibility, not correctness).

None are dead/broken controls; (1) is the only substantive UX inconsistency and is a labelling/
config-reconciliation item, not a logic bug. `live_locked=true` throughout.
