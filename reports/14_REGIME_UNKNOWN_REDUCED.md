# PART 14 — Regime "Unknown" Reduced With Reason

**Verdict: `REGIME_UNKNOWN_REDUCED_WITH_REASON`**

## Problem
Trade-detail header read `… Tier B · 69 · Unknown · created 1d ago`. The header binds to
`/api/trades/{id}/lifecycle` → `regime.label`, which called `normalize_regime(market_regime)`.
When a signal's `market_regime` was empty, this returned a bare `Unknown` with no context.

## Fix (`backend/app/lifecycle.py`)
Added `_regime_with_market_fallback(raw, asset_class)`:
1. normalize the per-signal `market_regime`;
2. if it resolves to `unknown` (empty), fall back to the **current market-dashboard regime**
   for the signal's asset class — `crypto_regime` for crypto, `stocks_regime` for stocks —
   labelled `… · market`, `source=market_snapshot`, with
   `reason="per-signal regime empty; using current market regime"`;
3. only show `Unknown` if neither the signal nor the market snapshot has a regime.

Read-only display field; never consumed by actionability/commands.

## Verified
- API: `/api/trades/sig_3adf229fcf30923a/lifecycle` →
  `regime.label="Trend ↓ · market"`, `source="market_snapshot"`,
  `reason="per-signal regime empty; using current market regime"`.
- Real UI (screenshot): ENA/USDT detail header now reads
  `crypto · swing · Tier B · 69 · Trend ↓ · market · created 1d ago` — no `Unknown`.

`live_locked=true` · `final_r` untouched.
