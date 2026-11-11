# PART 3 — Maker realism UI — REPORT
**Date:** 2026-06-26 · live locked · final_r untouched · engine math unchanged.

## What shipped
A **Maker realism** line in the Paper Shadow A/B panel (`[data-testid=shadow-maker]`), fed by
`GET /api/paper-shadow/forward.maker` → `paper_shadow_monitor` / `paper_shadow_engine` counters.

Metrics shown:
- **maker_entry_posted** · **maker_entry_filled** · **maker_entry_missed**
- **maker_fill_rate** (%) — highlighted in warn colour when < 50%
- **taker_fallback_used** (LIMIT_THEN_TAKER_TIMEOUT falls back to a taker market after 8 bars)
- maker_tp_fills are tracked in the engine (`maker_tp_fills`) and surfaced per-trade in the detail view.

Warnings:
- **fill-rate < 50%** → inline ⚠ "many limits missed — B edge may lean on optimistic fills".
- the forward promotion gate also carries a maker-miss warning (criteria/verdict in the gate block).

`missed_move_after_maker_miss` is **not yet a separate forward counter** — noted as a follow-up; the
current taker-fallback + missed counters already expose the realism cost.

## Evidence
- Screenshot `reports/screenshots/final_maker_realism.png` — posted/filled/missed/taker-fallback + fill-rate.
- Full-set realism (backfill, for scale): 396 posted / 269 filled / **67.9% fill-rate** / 114 missed /
  13 taker-fallback. Forward window accrues from activation.
- Per-trade detail shows `maker filled/posted · taker-fb` on the B branch.
- Test `test_forward_monitor_exposes_maker_block` ✅.

## VERDICT: `MAKER_REALISM_VISIBLE_IN_APP` ✅
