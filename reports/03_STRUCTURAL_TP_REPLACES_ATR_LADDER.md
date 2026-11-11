# PART 3 — Structural TP Replaces ATR Ladder When Levels Exist

**Verdict: `STRUCTURAL_TP_REPLACES_ATR_LADDER_WHEN_LEVELS_EXIST`** — CORE change (paper
signal-generation path, not display), verified end-to-end incl. a real-UI screenshot.

## The gap this closes
A structural TP engine already existed (`src/execution/structural_tp_engine.py`), but it was
only ever called with **`candles=None`** (the B-book backfill passed no chart data), so it could
never find swing/range/round-number levels — it always fell through to the ATR ladder. The
B-book diagnostic literally read **`structural_tp_used=0`**. So "structural TP" was configured but
inert.

## What was built (add-only, paper-only)
- **`src/execution/signal_paper_tp.py`** — for every entry-triggered signal, loads the **same
  OHLCV the tracker uses** (`file_store.load_ohlcv`, last 200 candles, crypto + stocks paths) and
  runs the structural engine with **real candles**. Persists into a new additive table
  `signal_paper_tp`:
  - `mechanical_tp1/2/3` — the production ATR-ladder TPs, **copied unchanged**
  - `active_paper_tp1/2/3` — the TPs the paper book uses (structural when levels exist)
  - `tp_set_type` — **STRUCTURAL | HYBRID | ATR_FALLBACK | NO_VALID_TP**
  - `tp{1,2,3}_source` (swing / range_bound / round_number / volume_profile / atr_extension),
    `confidence`, `volume_profile_supported`, `candles_used`, `reasons`, `warnings`.
  Keyed by the **real signal_id** (no economic-key dedup) so every trade the UI can open has its
  own record.
- **CLI `paper-tp-refresh`** + **scheduler step `paper_tp_refresh_step`** (runs each 2h cycle
  right after the paper-execution refresh). Idempotent.
- **Control-plane lifecycle** (`backend/app/lifecycle.py`) now reads `signal_paper_tp` and, when
  `tp_set_type ∈ {STRUCTURAL, HYBRID}`, drives the price ladder + chart TP lines from
  `active_paper_tp*` while keeping `mechanical_price` for reference; adds a `paper_tp` block.
- **UI** (`frontend/src/screens.tsx`) — the price ladder shows a **`TP: STRUCTURAL`** badge and a
  per-TP source tag (e.g. `TP1 (33%) · swing`).

## Verified
- `paper-tp-refresh` over 800 entry-triggered signals: **candles_hit 800/800**,
  **structural_used 790** (STRUCTURAL 717 + HYBRID 73), ATR_FALLBACK 10, NO_VALID_TP 0.
  (Was `structural_tp_used=0`.)
- Structural ≠ mechanical, real levels: MSTR `swing 111.70` (mech 112.31), WLD `round 0.60`
  (mech 0.5888), ENA `swing 0.0854` (mech 0.08457).
- Lifecycle API for the ENA trade: `paper_tp.tp_set_type=STRUCTURAL, applied=true, candles=200`;
  ladder TP1 `price=0.0854 src=swing mechanical=0.08457`.
- **Real UI screenshot**: ENA detail shows `PRICE LADDER · OUTCOMES` with a **`TP: STRUCTURAL`**
  badge and the chart TP lines at the structural R (`+0.658 / +0.928 / +1.378R`), replacing the
  old mechanical `+1.2 / +2.2 / +3.2R`.
- **Tests**: `tests/test_signal_paper_tp.py` — 4 passed (label-mapping total, structural≠mechanical,
  graceful no-candles fallback, persist/read idempotent roundtrip).

## Safety
`proposed_signals.tp1/2/3` and `signal_outcomes.final_r` are **never written**. The structural set
is a separate additive table consumed by the paper read-model / UI. `live_locked=true` throughout.
