# PART 8 — Structural Stop Movement Prefers Chart Structure

**Verdict: `STRUCTURAL_STOP_MOVEMENT_PREFERS_CHART_STRUCTURE`** — verified end-to-end incl. a
real-UI screenshot.

## The gap this closes
`src/execution/structural_stop_manager.py` already implemented `structural_stop_after_tp()` (move
the stop to a higher-low / lower-high / support / resistance / VWAP after a partial TP, else BE/lock),
but it was **never fed chart data** — and the control-plane lifecycle moved the stop with a pure
**R-based placeholder** (`source="model_f"`, "structural fallback: BE/lock"). So the displayed
"moved stop" never actually used chart structure.

## What was built (paper read-model, add-only)
- **`src/execution/signal_stop_plan.py`** — per signal, loads the **real OHLCV** and runs
  `structural_stop_after_tp()` for the post-TP1 and post-TP2 stops, persisting into the additive
  `signal_stop_plan` table: `stop_after_tp1/2`, their `_r` and `_basis`
  (higher_low/lower_high/support/resistance/vwap/be/lock/none), and `prefers_structure`.
- **CLI `paper-stop-refresh`** + **scheduler step `paper_stop_refresh_step`** (each cycle).
- **Control-plane lifecycle** (`backend/app/lifecycle.py`) now **drives the moved stop from the
  plan** — preferring the structural stop, falling back to BE/lock only when no structure protects —
  and tags each `stop_moved_structural` event with `stop_basis` + `source=structural_stop_plan`.
  Adds a `stop_protection` block to the response.
- **UI** — the price-ladder footer shows a **`stop: structural`** badge + "after TP1 → lower high
  (+0.66R) · after TP2 → …".

## Verified
- `paper-stop-refresh` over 800 signals: **candles_hit 800/800, structure_moves 418** — bases:
  higher_low 239, lower_high 178, support 1 (structural) vs be 382 / lock 511 (fallback).
- ENA: `stop_protection.prefers_structure=true`, after TP1 → **lower_high +0.66R**; the lifecycle's
  first stop-move event is now `source=structural_stop_plan, basis=lower_high,
  reason="after TP1 → lower high at +0.66R (structural protection)"` (was the model_f placeholder).
- **Real UI screenshot**: ENA price-ladder footer shows **`stop: structural`** +
  "after TP1 → lower high (+0.66R)", with the TP rows tagged `· swing` / `· round` (PART 3).
- **Tests**: `tests/test_signal_stop_plan.py` — 3 passed (structure preferred when present,
  BE/lock fallback without candles, persist roundtrip).

## Safety
Read-model / accounting only — never places an order, never moves a production stop, never touches
`signal_outcomes` / `final_r`. The structural manager already guarantees the stop never moves worse
than current protection. `live_locked=true` throughout.
