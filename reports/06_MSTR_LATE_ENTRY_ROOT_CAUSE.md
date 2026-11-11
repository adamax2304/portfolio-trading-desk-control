# PART 6 — MSTR Late Entry: Root Cause + Missed-Opportunity Log

**Verdict: `MSTR_LATE_ENTRY_FIXED_OR_EXPLAINED_WITH_MISSED_OPPORTUNITY_LOG`** — EXPLAINED (it is
not a fill/detection bug) with a per-signal cause classifier as the missed-opportunity log.

## Root cause (proven, not a fill bug)
The flagged MSTR late entry is **`sig_18369a970f78886f`** (SHORT, entry band 116.41–117.83):

| field | value |
|---|---|
| created_at | 2026-06-18 **09:35** |
| recorded entry | 2026-06-18 **13:30** (≈ 234 min later) |
| first 15m bar after creation | **13:30** (L 113.72 / H 117.75 — already in band) |
| in-band bar *before* the recorded fill? | **No** (`in_band_before_recorded = 0`) |

There are **no 15m bars at all between 09:35 and 13:30** in the OHLCV the tracker reads. The
tracker recorded entry at the **first bar it had**, which was already in the band. So the lateness
is a **data-coverage gap** — yfinance intraday is delayed and the rolling-window cache had already
dropped the early-session bars by the time tracking ran — **not** a monitor-tick miss or a fill-logic
defect. (Consistent with the known rolling-window OHLCV coverage limit.)

## Fleet-wide confirmation (`entry_latency_audit`, 400 recent stock entries)
| cause | count | meaning |
|---|---|---|
| **DATA_GAP_LATE** | **273** | first available bar is > 30 min after creation (coverage) |
| LEGITIMATE_LATE | 28 | continuous data; price genuinely reached the band late |
| FAST | 99 | filled ≤ 30 min after creation |
| **DETECTION_LATENCY** | **0** | a fillable in-band bar existed before the recorded fill — a real bug |

**Zero DETECTION_LATENCY** across 400 signals → the entry-fill logic is not missing fillable
prices. The "late entries" are overwhelmingly a data-coverage artifact.

## What was built (read-only diagnostic, add-only)
- **`src/signals/entry_latency_audit.py`** — `classify(...)` compares the recorded fill to the
  first available bar + whether price was in-band earlier, labelling
  **DATA_GAP_LATE / DETECTION_LATENCY / LEGITIMATE_LATE / FAST / NO_DATA** into the additive
  `entry_latency_audit` table (the missed-opportunity log).
- **CLI `entry-latency-audit`** + **scheduler step `entry_latency_audit_step`** (each cycle).
- **Control-plane lifecycle** surfaces an `entry_latency` block; **UI** shows an `entry latency:
  <cause> · <Nm>` badge on the trade detail (warn tone for coverage, danger tone if ever
  DETECTION_LATENCY) — so a "234-min late" entry reads as *coverage*, not a bug.
- **Tests**: `tests/test_entry_latency_audit.py` — 5 passed (data-gap, detection-latency,
  legitimate-late, fast, no-data).

## Recommendation (no fill-logic change needed)
1. The tracker fill logic is correct — **do not** touch it (0 detection-latency).
2. To reduce *recorded* lateness, the lever is **data freshness for stock intraday**: fetch/backfill
   the early-session 15m bars (yfinance allows ~60d intraday history) before tracking, and/or run
   the stock entry-detection pass sooner after the open.
3. `DATA_GAP_LATE` entries should be **excluded from latency/edge stats** and their recorded entry
   time treated as a lower bound — now possible via the `entry_latency_audit.cause` label.

`signal_outcomes.final_r` and production logic untouched. `live_locked=true` throughout.
