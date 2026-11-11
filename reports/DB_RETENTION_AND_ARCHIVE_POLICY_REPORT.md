# PART 3 — DB retention / archive policy — REPORT
**Date:** 2026-06-26 · safe, DRY-RUN by default · never deletes final outcomes / touches scoring / final_r values kept.

## Problem (measured)
`db/crypto_ai_desk.sqlite` ≈ **1994 MB**. `signal_outcomes` = **371,246 rows / 2,446 signals = 151.8
per-bar rows per signal**. The tracker appends one row per evaluation; `final_outcome` is copied onto
~all per-bar rows of a closed signal (e.g. one signal: 158 rows, 145 carrying `final_outcome`).

## Policy (`src/maintenance/signal_outcomes_retention.py` + CLI `signal-outcomes-retention`)
A row is **archivable** iff it is older than `--days` N **and** is NOT the latest row for its signal.
- **Always kept:** the latest row per signal (carries `final_r`/`final_outcome` — the summary), and
  every row newer than N days. So no closed-trade outcome is ever lost.
- **Archived first, then deleted:** older intermediate per-bar PATH rows → compressed **parquet**
  (CSV.gz fallback) under `data/archive/signal_outcomes/`, recoverable. Delete is aborted if archiving
  fails (rows never lost).
- `--vacuum` optional (reclaim disk; slow).

## Headroom (dry-run, read-only — measured)
| window | archivable | share | kept (latest/sig always kept) |
|---|---|---|---|
| `--days 30` | 1,730 | 0.5% | 369,516 |
| `--days 14` | 72,748 | 19.6% | 298,498 |
| `--days 7` | 169,918 | 45.8% | 201,328 |

Most rows are recent, so a 30-day window frees little *today* but grows as data ages; **14d** is the
balanced default for a real reclaim. The latest 2,446 rows (one final summary per signal) are always
kept.

## Safety proof
- Default `--dry-run` mutates nothing (verified: 0 deleted).
- Synthetic-DB test (`test_safe_observability.py`): after a real run, every signal still has its latest
  row + `final_r`, only old intermediate rows archived+deleted, archive file present.
- Source scan: the module contains **no `UPDATE` / no `SET final_r`** — it only DELETEs old rows.

CLI: `signal-outcomes-retention --dry-run` · `--no-dry-run --days 30 --archive` · `--vacuum`.

## VERDICT: `DB_RETENTION_POLICY_READY_AND_SAFE` ✅  (ready; not executed on the live DB — awaiting your go on the window)
