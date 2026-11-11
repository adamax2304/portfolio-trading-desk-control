# PART 4 — Breakout & Pullback Entry Modes Active in Paper

**Verdict: `BREAKOUT_AND_PULLBACK_ENTRY_MODES_ACTIVE_IN_PAPER`** — verified end-to-end incl. a
real-UI screenshot.

## The gap this closes
The production `technical_setup_agent` only ever builds a **pullback-limit band**
(`close − 0.65..0.20·ATR` for longs / mirrored for shorts), and when price is **> 2.5 ATR
extended it converts the idea to "watchlist — wait for pullback"** — discarding every
breakout/momentum entry. There was no breakout-continuation, structural-retest, momentum-taker,
or limit-then-taker path.

## What was built (add-only, paper-only)
- **`src/execution/entry_mode_classifier.py`** — per signal, loads the **real OHLCV the tracker
  uses** and classifies the entry mode from chart structure (swing H/L, range, round numbers) +
  momentum (N-bar return / ATR) + extension (distance from SMA20 / ATR). Persists into a new
  additive table `signal_entry_mode`:
  - `entry_mode` ∈ **PULLBACK_LIMIT / STRUCTURAL_RETEST / BREAKOUT_CONTINUATION /
    MOMENTUM_TAKER_NOW / LIMIT_THEN_TAKER_TIMEOUT / NO_CHASE_SKIP**
  - `entry_style` (limit / stop / taker / limit_then_taker / none), `suggested_entry`,
    `extension_atr`, `momentum_atr`, `near_level` + `dist_to_level_atr`, `confidence`, `reason`.
- **CLI `entry-mode-refresh`** + **scheduler step `entry_mode_refresh_step`** (each 2h cycle,
  right after the structural-TP refresh). Idempotent.
- **Control-plane lifecycle** (`backend/app/lifecycle.py`) surfaces an `entry_mode` block.
- **UI** (`frontend/src/screens.tsx`) — the trade-detail header shows an **`entry: <mode> · <style>`**
  badge (accent when non-pullback).

## Decision logic (long; mirrored for short)
1. coiled ≤ 0.5 ATR under a level with +momentum → **BREAKOUT_CONTINUATION** (stop entry beyond it)
2. a level just broke (≤ 0.5 ATR below) with momentum → **STRUCTURAL_RETEST** (limit the retest)
3. > 2.5 ATR extended with strong (> 1.5 ATR) momentum → **MOMENTUM_TAKER_NOW** (no pullback)
4. > 2.5 ATR extended, weak continuation → **NO_CHASE_SKIP**
5. clean pullback band beneath price → **PULLBACK_LIMIT** (production default)
6. otherwise → **LIMIT_THEN_TAKER_TIMEOUT**

## Verified
- `entry-mode-refresh` over 800 entry-triggered signals: **candles_hit 800/800**,
  **non_pullback 610** — BREAKOUT_CONTINUATION 254, LIMIT_THEN_TAKER_TIMEOUT 283,
  PULLBACK_LIMIT 190, NO_CHASE_SKIP 28, MOMENTUM_TAKER_NOW 26, STRUCTURAL_RETEST 19.
  (Production = pullback-only.)
- Real closed breakout examples (momentum ATR): XOM 3.41, EDEN/USDT 4.17, XLV 2.61, MSFT 2.21,
  JPM 1.66, PORTAL/USDT 1.62, META 1.39 — all `BREAKOUT_CONTINUATION · stop`.
- Lifecycle API (ENA): `entry_mode=PULLBACK_LIMIT, style=limit, momentum_atr=0.867` (a genuine
  pullback — not extended), shown beside `paper_tp=STRUCTURAL`.
- **Real UI screenshot**: ENA detail header shows the **`entry: pullback limit · limit`** badge
  alongside the **`TP: STRUCTURAL`** ladder badge.
- **Tests**: `tests/test_entry_mode_classifier.py` — 5 passed.

## Scope / safety
This is a **paper read-model classification** — it labels which mode the paper book should use and
exposes it; it does not yet rewrite the tracker's entry-fill detection (that fill-logic change
needs its own paper-shadow validation + sign-off, per the locked rules). `proposed_signals.entry_*`
and `signal_outcomes.final_r` are untouched. `live_locked=true` throughout.
