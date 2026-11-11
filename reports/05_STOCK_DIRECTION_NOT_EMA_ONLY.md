# PART 5 — Stock Direction Not EMA-Only

**Verdict: `STOCK_DIRECTION_NOT_EMA_ONLY`** — verified end-to-end incl. a real-UI screenshot.

## The gap this closes
Production `StockTechnicalAgent` sets direction from the **EMA trend alone**
(`_direction(self._trend(close, ema20, ema50))`). VWAP, prior-day H/L, relative strength, and
sector data are computed or available but never fused into the directional call — and MSTR's
well-known BTC sensitivity was ignored entirely.

## What was built (add-only, paper-only)
- **`src/stocks/stock_direction_score.py`** — per stock signal, loads the real OHLCV (intraday
  15m + daily) + SPY and fuses **six factors**, each casting a −1/0/+1 weighted vote:
  1. **EMA trend** (production factor) · 2. **VWAP** position · 3. **prior-day-high/low break** ·
  4. **momentum** (N-bar return) · 5. **relative strength vs SPY** (20d) ·
  6. **MSTR · BTC** sensitivity (MSTR only — BTC trend from the market-dashboard crypto regime).
  Persists into the additive `stock_direction_score` table: `direction` (fused), `direction_score`
  (signed sum), `dir_label` ∈ **EMA_ONLY / MULTI_FACTOR_CONFIRMED / MULTI_FACTOR_CONFLICT /
  MULTI_FACTOR_WEAK**, per-factor votes, `agreement`, `agrees_with_production`, `rs_spy_20d`.
- **CLI `stock-direction-refresh`** + **scheduler step `stock_direction_refresh_step`** (each cycle).
- **Control-plane lifecycle** surfaces a `stock_direction` block (stocks only).
- **UI** — trade-detail header shows a **`dir: <side> · <label> (<n>f)`** badge (warn tone on conflict).

## Verified
- `stock-direction-refresh` over 400 entry-triggered stock signals: **multi_factor 400/400**
  (zero EMA-only — every call now uses multiple factors), **would_flip_vs_production 74**
  (74 signals where the fused direction differs from the EMA-only production call),
  current `btc_trend=−1`. Labels: MULTI_FACTOR_CONFIRMED 187, MULTI_FACTOR_CONFLICT 201,
  MULTI_FACTOR_WEAK 12.
- **MSTR**: `direction=short, dir_label=MULTI_FACTOR_CONFIRMED, score=−5.6`, **all 6 votes −1**
  (ema/vwap/pdhl/momentum/rs/**mstr_btc**) — the BTC-down regime tilts MSTR short, and every other
  factor agrees. This is exactly the MSTR↔BTC sensitivity the brief asked for.
- Lifecycle API (`sig_098531536c382f84`): `stock_direction.direction=short, dir_label=
  MULTI_FACTOR_CONFIRMED, factors_used=6`.
- **Real UI screenshot**: MSTR SHORT detail header shows **`dir: short · multi factor confirmed
  (6f)`** beside `entry: pullback limit · limit` and the `TP: STRUCTURAL` ladder badge — PART 3+4+5
  all live on one trade.
- **Tests**: `tests/test_stock_direction_score.py` — 5 passed (agree→confirmed, split→conflict,
  MSTR-only BTC factor, neutral-on-no-signal, table roundtrip).

## Scope / safety
A **paper read-model** multi-factor assessment shown beside the production EMA call; it does not
rewrite `proposed_signals.direction` (that routing change needs paper-shadow validation + sign-off,
per the locked rules). `signal_outcomes.final_r` untouched. `live_locked=true` throughout.
