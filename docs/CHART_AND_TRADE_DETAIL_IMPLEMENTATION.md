# Chart & Trade Detail (PART 6)

**Date:** 2026-06-17 · honest data only — missing values render as "not available", never faked.

## Chart ([Chart.tsx](../frontend/src/Chart.tsx))
lightweight-charts candlesticks (transparent bg) with overlay price lines and markers:
- **entry band** (entry↑ / entry↓, cyan), **entry trigger**, **stop** (red), **TP1/TP2/TP3** (violet)
- markers: **signal** (created_at), **entry** (entry_triggered_at, arrow up),
  **exit** (exit_at, square — green/red by outcome) — new in v1
- **autoscaleInfoProvider** widens the visible price range to include all overlay levels
  (entry/stop/TP) with 4% padding, so the stop/TP never sit off-screen (PART-polish fix)
- graceful resize; cleaned up on unmount

The exit timestamp (`exit_at`) is derived in the adapter from `signal_outcomes`
(stop/tp hit times) and exposed in chart overlays.

## Trade detail ([screens.tsx](../frontend/src/screens.tsx) `TradeDetail`)
- header: symbol · direction · asset/mode/tier/score · **created {relative time}**
- closed trades: result hero with **final R**, outcome, hold time, **MFE / MAE**
- chart panel, or honest **"Chart data unavailable"** when no candle cache
- **Setup analysis** rows (check/warn icons): Catalyst, Funding/OI, Concentration, **Freshness**,
  RR (TP1), Invalidation, **Manually actionable** (with the blocked reason when not actionable)
- Manual Entry button only when actionable; otherwise disabled with the reason

## Per-trade sparkline
The `Sparkline` component ships and `TradeCard` degrades gracefully. The desk API does not
expose a per-trade equity series, so v1 does **not** render per-card sparklines (it would
require a per-card chart fetch or a new read-only adapter series). Documented as a Phase-3
follow-up rather than faking a series. Trade cards show real Entry/Stop/Next-TP + R instead.

## Data honesty
If candles, overlays, MFE/MAE, or exit time are unavailable, the UI shows "—" / "not
available" / "Chart data unavailable". No synthetic precision is invented.
