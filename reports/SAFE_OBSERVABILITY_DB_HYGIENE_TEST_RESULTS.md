# PART 7 — Safe observability + DB hygiene test results
**Date:** 2026-06-26 · live locked · final_r untouched.

## New tests
**crypto-ai-desk `tests/test_safe_observability.py` — 7/7 ✅**
- `test_retention_dry_run_mutates_nothing` — dry-run deletes 0, row count unchanged.
- `test_retention_keeps_latest_per_signal_and_recent` — on a synthetic DB, after a real run every
  signal keeps its latest row + `final_r`; only old intermediate rows archived+deleted; archive file exists.
- `test_retention_module_never_updates_final_r` — module has no `UPDATE` / `SET final_r`.
- `test_catalyst_shadow_audit_no_scoring_change` — no `UPDATE proposed_signals`, no write to
  `signal_catalyst_labels`; only writes the additive `catalyst_shadow_audit`.
- `test_a_tier_diagnostic_read_only` — no UPDATE/INSERT/DELETE; threshold constant 80.
- `test_stocks_readiness_read_only` — no UPDATE/INSERT/DELETE.
- `test_digest_compose_has_required_fields` — composer includes gate + "NOT proof" caveat.

**trading-desk-control `backend/tests/test_paper_shadow_breakdown.py` — 4/4 ✅**
- dimensions present (mode/entry_mode/order_type/regime/symbol/sector/tp_set) + forward/backfill split;
  per-group A/B shape (trades/net_r/net_usd/fees/win_rate/maker_fill_rate/missed/no_chase/dir_flips +
  delta_r + data_gap_excluded); filled-only trade counts ≥ 0; read-model has no write SQL.

## Regression suites
- **trading-desk-control backend**: `pytest backend/tests/` → **76 passed, 6 skipped, 0 failed**
  (includes the 4 breakdown + 6 visibility tests).
- **crypto-ai-desk shadow + coverage + safe-obs**: engine 6 + operational 5 + coverage 4 + safe-obs 7
  → **22 passed**.
- compileall both projects → exit 0 (all files parse). frontend `npm run build` → clean.

## Guardrails asserted
- No live / no exec path touched. `final_r` values that are kept are never rewritten (retention deletes
  whole old rows only; the latest/final row per signal is always kept).
- Catalyst audit + A-tier + stocks-readiness are read-only w.r.t. scoring / threshold / actionability.

## VERDICT: `SAFE_OBSERVABILITY_DB_HYGIENE_TESTS_PASS` ✅
