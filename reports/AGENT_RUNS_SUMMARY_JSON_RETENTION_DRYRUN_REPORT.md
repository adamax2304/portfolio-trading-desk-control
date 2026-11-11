# agent_runs.summary_json Retention — DRY-RUN REPORT (prepared, awaiting approval)
**Date:** 2026-06-26 · DB `crypto-ai-desk/db/crypto_ai_desk.sqlite` · **dry-run only, nothing changed.**
No trading data / scoring / final_r / live touched.

## Why this is the real win
The 2 GB DB is dominated by **`agent_runs.summary_json` = 1663.7 MB (83% of the file)** across ~107k
LLM-run log rows. `summary_json` is **write-only** — INSERTed by the run logger, never SELECTed anywhere
in the codebase. The real artifact is the file at `output_path` (kept). So the cached blob of OLD rows is
safe to archive + null.

## Policy (`src/maintenance/agent_runs_retention.py` + CLI `agent-runs-retention`)
For rows older than `--days` N **with** a blob: archive `(id, agent_name, run_at, output_path, asset_class,
summary_json)` → parquet, then `UPDATE … SET summary_json = NULL`. **The metadata row is kept** (you still
know which agent ran when + its `output_path`). Archive-first; UPDATE aborts if archiving fails. Default
DRY-RUN. Reclaiming freed space to the OS needs a follow-up **VACUUM** (operator-gated).

## Dry-run numbers (measured, read-only)
Rows with blob: **106,960 · 1663.7 MB total.**

| window | clearable rows | clearable blob | kept-recent blob |
|---|---|---|---|
| `--days 30` | 18,112 | **260 MB** | ~88.8k |
| `--days 14` | 64,861 | **992 MB** | 42,099 |
| `--days 7` | 87,911 | **1364 MB** | ~19k |

Verified: dry-run mutates nothing (blob rows before == after, cleared = 0).

## Safety
- Tests `test_agent_runs_*` (3): dry-run mutates nothing; real run on synthetic DB nulls old blobs +
  **keeps all metadata rows + output_path** + recent blob; module touches no trading table / no `final_r`.
- Module SQL only references `agent_runs`. No scoring / actionability / final_r / live.

## Recommended plan (awaiting your go)
1. `agent-runs-retention --days 14 --archive --no-dry-run` → archive + null ~992 MB of old blobs (keep
   last 14 days for debugging).
2. **Then** `agent-runs-retention --vacuum` (or a one-off VACUUM) — here VACUUM **is** worth it (returns
   ~1 GB to the OS, vs the 16 MB from the signal_outcomes pass). Cost: full-DB write lock for ~1–3 min
   while the file rebuilds; the live tracker's writes queue during that window.

Pick the window (14d ≈ 992 MB, 7d ≈ 1.36 GB) and whether to VACUUM after, and I'll run it step-by-step
with the same before/after audit as the signal_outcomes pass.

---

## EXECUTED — 14d + VACUUM (operator-approved, 2026-06-26)
Ran `agent-runs-retention --days 14 --archive --no-dry-run`, then a separate VACUUM.

| | |
|---|---|
| **DB size** | **2026.6 MB → 948.7 MB** (reclaimed **~1.08 GB**, file more than halved) |
| Blobs cleared | **66,906** (older than 14d) · recent 41,885 blobs kept |
| Archive | `data/archive/agent_runs/agent_runs_summary_archive_20260626T130913.parquet` — 66,906 rows · 6 cols · 194.1 MB · all blobs non-null |
| Metadata preserved | ✅ all 108,791 rows kept; sample 10/10 `agent_name`+`run_at`+`output_path` intact AND `summary_json` now NULL |
| Recent blobs | ✅ kept (e.g. latest `trade_idea_agent` row still has its blob) |
| **VACUUM** | done in **10.2s** (local SSD); `integrity_check = ok` |
| API / app | ✅ `/api/health` ok, all paper-shadow + signals + status + market-dashboard endpoints 200 |
| Shadow monitor | ✅ `forward_quality` available, gate NOT_READY |
| Tests | ✅ safe-obs 10 + engine 6 + (earlier) 22 — all pass |
| live / exec | ✅ `live_locked=true`, `auto_live_locked=true` |
| `final_r` | ✅ untouched — agent_runs retention references only `agent_runs` (test-asserted) |

### Verdicts
- `AGENT_RUNS_SUMMARY_JSON_RETENTION_COMPLETE` ✅
- `AGENT_RUN_METADATA_AND_ARTIFACT_POINTERS_PRESERVED` ✅
- `ARCHIVE_CREATED_AND_VERIFIED` ✅ (194.1 MB parquet, 66,906 blobs)
- `VACUUM_RECLAIMED_~1.08GB` ✅ (2026.6 → 948.7 MB)
- `API_AND_SHADOW_MONITOR_HEALTHY` ✅
- `NO_LIVE_EXECUTION_ENABLED` ✅ · `HISTORICAL_FINAL_R_UNCHANGED` ✅

**Net result of both retention passes today:** DB **2026 MB → 949 MB** (≈53% smaller); two recoverable
archives written (`signal_outcomes` 0.8 MB + `agent_runs` 194 MB parquet); all final trade summaries,
signal latest-rows, agent metadata + artifact pointers preserved; integrity ok; live locked.
