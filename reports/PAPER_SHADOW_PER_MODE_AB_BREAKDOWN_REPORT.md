# PART 1 — Per-mode A/B breakdown — REPORT
**Date:** 2026-06-26 · live locked · final_r untouched · B not promoted · backfill ≠ proof.

## What shipped
`GET /api/paper-shadow/breakdown` + a **By mode** section in the Mini App System → Paper Shadow A/B
panel. Forward (valid) is the default; a toggle reveals backfill **labelled look-ahead/hypothesis**.

Dimensions: **mode** (asset+mode), asset_class, **symbol**, **sector** (stocks), **regime**,
**entry_mode**, **tp_set**, **order_type** (maker/taker). Per group: A/B trades, A/B net R, ΔR,
A/B net $, Δ$, fees, win rate, worst-trade R (DD proxy), maker fill rate, B missed entries, no-chase
skips, dir flips, **DATA_GAP excluded count** (excluded from edge stats but counted). Trades/R/win use
FILLED rows only; skips/misses are reported separately so they don't dilute win-rate.

## Forward (valid) — by mode  *(small sample; accruing since activation)*
| mode | A | B | ΔR | maker fill |
|---|---|---|---|---|
| stocks swing | 17t −0.61R | 16t **+2.00R** | **+2.61** | 100% |
| stocks intraday | 9t −3.74R | 9t −1.49R | **+2.25** | 100% |
| stocks invest | 10t −0.23R | 10t −0.63R | −0.40 | 100% |
| crypto swing | 1t −1.12R | 1t −1.11R | +0.01 | — |
| crypto intraday | 1t −0.83R | 1t −0.83R | 0.00 | 100% |
| crypto scalp | 2t −2.10R | 2t −2.10R | 0.00 | 100% |

## Forward — by entry_mode / order_type
- entry_mode: PULLBACK_LIMIT A 40t −8.65R / B 9t +0.16R · LIMIT_THEN_TAKER_TIMEOUT B 10t −4.29R ·
  BREAKOUT_CONTINUATION B 18t −1.61R · **MOMENTUM_TAKER_NOW B 3t +1.57R**.
- order_type: maker B 18t (fill 100%) · taker B 21t.

## Read
Where B helps so far is **stocks swing** (+2.61R) and **stocks intraday** (+2.25R, less-bad); **stocks
invest** is slightly worse (−0.40R). Crypto modes are ~flat on tiny samples. This is the per-mode lens
that will drive *selective* promotion later — but only on the FORWARD window after the gate, with
sign-off. Samples are still far below the gate's 60-trade threshold.

Evidence: `reports/screenshots/final_shadow_bymode.png`. Tests: `test_paper_shadow_breakdown.py` 4/4.

## VERDICT: `PAPER_SHADOW_PER_MODE_AB_BREAKDOWN_ACTIVE` ✅
