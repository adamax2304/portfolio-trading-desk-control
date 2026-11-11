# LIVE DB Retention — 14d Archive — REPORT
**Date:** 2026-06-26 · DB `crypto-ai-desk/db/crypto_ai_desk.sqlite` · `--days 14 --archive` (**no VACUUM**).
Live + auto-live locked · `final_r` untouched · executed step-by-step with operator authorization.

## Procedure
1. Dry-run `--days 14` → archivable 73,454 (19.6%).
2. Read-only safety check: archivable set excludes **0** latest-per-signal rows; before-snapshot of 20 signals saved.
3. `signal-outcomes-retention --days 14 --archive --no-dry-run` → archived then deleted (no vacuum).
4. Post-archive audit (below).

## Answers
1. **Rows before?** **374,639** (2,447 signals, 153.1 per-bar rows/signal).
2. **Archived?** **73,454** rows → `data/archive/signal_outcomes/signal_outcomes_archive_20260626T000946.parquet`
   (73,454 rows · 22 cols · 0.8 MB). Archive written **before** delete (delete aborts if archive fails).
3. **Remaining?** **301,185** rows (= 374,639 − 73,454, exact). Distinct signals **2,447 → 2,447 (none lost)**.
4. **Where is the archive?** `crypto-ai-desk/data/archive/signal_outcomes/signal_outcomes_archive_20260626T000946.parquet` (parquet; CSV.gz fallback if pandas absent). Fully recoverable.
5. **Latest rows preserved for all signals?** ✅ **0** latest-per-signal rows were archivable; sample 20/20
   still have `max(id)` == the pre-archive latest id.
6. **Final outcomes preserved?** ✅ sample 20/20 latest rows have **unchanged `final_r` + `final_outcome`**;
   2,112/2,447 latest rows carry `final_outcome` (the other 335 are still-open signals whose latest row is kept).
   `pragma quick_check` = **ok**. (`paper_execution_r` lives in `paper_execution_outcomes` and `close_reason`
   in the shadow/exec tables — **neither table was touched**.)
7. **API / app / shadow monitor healthy after archive?** ✅ `/api/health` ok, `live_locked=true`,
   `auto_live_locked=true`; `/api/paper-shadow/forward|breakdown`, `/api/signals`, `/api/status` all 200;
   `forward_quality()` available (B 39 trades, gate NOT_READY). Tests 18/18 (safe-obs 7 + engine 6 + operational 5).
8. **`final_r` untouched?** ✅ retention only DELETEs whole old intermediate rows; kept rows' `final_r` unchanged
   (sample 20/20); module has no `UPDATE`/`SET final_r`.
9. **live / execution still locked?** ✅ `live_locked=true`, `auto_live_locked=true`.
10. **VACUUM — needed, and how much would it return?**
    - **Without VACUUM:** file size unchanged at **2001 MB**; **16.3 MB** now free *inside* the file (3,976
      freelist pages), reused by future writes (file won't grow for a while).
    - **With VACUUM:** reclaims ≈**16.3 MB** to the OS (→ ~1985 MB). **Small** — because the per-bar rows are
      byte-light (73,454 rows = only 0.8 MB compressed).
    - **The 2 GB is NOT the per-bar tracking rows.** Heavy-column audit: **`agent_runs.summary_json` = 1663.5 MB
      (83% of the DB)** across 107k LLM-run rows. `signal_outcomes` row-count was high but byte-light.
    - **Cost/risk of VACUUM:** rebuilds the whole ~2 GB file (copy on local SSD ≈ 1–3 min) under a **full-DB
      write lock** for that duration → the live tracker's writes would block/queue during the rebuild.
    - **Recommendation: SKIP VACUUM now** — 16 MB isn't worth a multi-minute full-DB lock. The high-value
      follow-up is a **separate `agent_runs.summary_json` retention** (≈1.6 GB), which needs its own dry-run +
      sign-off (different table; it is the LLM agent-run log).

## Verdicts
- `LIVE_DB_RETENTION_14D_ARCHIVE_COMPLETE` ✅
- `FINAL_SIGNAL_SUMMARIES_PRESERVED` ✅
- `ARCHIVE_CREATED_AND_VERIFIED` ✅
- `API_AND_SHADOW_MONITOR_HEALTHY_AFTER_RETENTION` ✅
- `NO_LIVE_EXECUTION_ENABLED` ✅
- `HISTORICAL_FINAL_R_UNCHANGED` ✅

## Bottom line
The 14-day retention is complete and safe: 73,454 old intermediate per-bar rows archived to parquet and
deleted; every signal keeps its latest row + `final_r`/`final_outcome`; DB integrity ok; app/API/shadow
monitor healthy; live locked. **But the real 2 GB disk hog is `agent_runs.summary_json` (1.66 GB), not the
tracking rows — VACUUM here would return only ~16 MB, so it is not recommended.** Awaiting your decision on
VACUUM and, separately, on an `agent_runs` retention that would actually reclaim the bulk.
