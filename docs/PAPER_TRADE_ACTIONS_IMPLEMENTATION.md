# Paper Order / Trade Actions (PART 2)

**Date:** 2026-06-17 · all paper-only, recorded + audited in the control DB. **Honest:** these
are control-plane bookkeeping records, NOT executions in the crypto-ai-desk core engine.

## Manual paper order from a signal
[ManualTradeModal](../frontend/src/ManualTradeModal.tsx) prefills symbol/direction/entry/stop/
TP/risk from the signal. `MANUAL_PAPER_ORDER` ([commands.py](../backend/app/commands.py)
`_manual_paper_order`) is **rejected** when any of these hold:

- crypto scalp / stocks scalp (shadow / research) — via `actionability`
- C-tier / rejected — via `actionability`
- shadow (proxy or **sector cap**) — via `actionability`
- late / very_late ("DO NOT CHASE") — via `actionability`
- **missing stop** (signal stop used as fallback; if still none → reject)
- **daily paper risk budget exceeded** (`Σ committed risk today + risk > daily_loss_limit`)
- **max open paper positions reached** (`open queued/filled ≥ max_positions`)
- **emergency-paused**, or trading mode ≠ paper
- direction not long/short

Front-end mirrors the gate (no "Manual Entry" on non-actionable cards); the backend is the
final authority. Order requires explicit **Confirm Paper**; live is a disabled
**"Hold to Confirm Live · LOCKED"**.

## Custom (no-signal) paper order
Opening the modal from the global FAB shows a **custom order** form (symbol, long/short,
entry, stop, TP1, risk). **Review is disabled until a symbol + valid stop are entered**
(client guard); the backend re-validates the same rules. Paper mode only — no live route.

## Paper trade actions ([commands.py](../backend/app/commands.py) `_paper_trade_action`)
| Command | Effect (control DB `manual_orders`) |
|---|---|
| `CLOSE_PAPER_TRADE` | queued/filled → `closed` (idempotent; rejects from terminal states) |
| `CANCEL_PENDING_PAPER` (`CANCEL_PENDING_ORDER`) | queued → `cancelled` (only queued) |
| `ADD_TRADE_NOTE` | appends to `trade_notes` (optional `ref` = signal/order id) |
| `ACKNOWLEDGE_ALERT` (`ACK_ERROR`) | marks an `app_notifications` row acked |

Idempotency: acting on an already-terminal order returns `{idempotent:true}` instead of erroring.

## Honest status in the UI
The order ticket shows the real outcome: **queued** (applied), **Rejected: …**, or
**Failed: …** — never a fake "executed". `recent_manual_orders` / `recent_notes` /
notifications back these views.

## Tests
`test_paper_order_missing_stop_rejected`, `test_paper_order_custom_ok_then_close_idempotent`,
`test_cancel_pending_paper`, `test_max_open_positions_enforced`,
`test_daily_paper_risk_budget_enforced`, `test_add_trade_note_no_confirm_needed`,
`test_acknowledge_alert`, plus the pre-existing shadow/actionable order tests — all pass.
