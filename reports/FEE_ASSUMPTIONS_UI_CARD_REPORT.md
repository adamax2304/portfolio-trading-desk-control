# PART 2 — Fee assumptions UI card — REPORT
**Date:** 2026-06-26 · live locked · final_r untouched.

## What shipped
A **Fee assumptions** card in the Paper Shadow A/B panel (`[data-testid=shadow-fees]`), fed by
`GET /api/paper-shadow/fees` → `backend/app/paper_shadow.py::fee_assumptions()`.

Shows:
- **active fee profile** badge — `bybit_non_vip_usdt_perp` (the default).
- **maker fee** 0.020% · **taker fee** 0.055% · **slippage estimate** 0.02%.
- **custom_account_override** status (off by default; flips when a custom account profile is configured).
- explicit statement: **"All A/B numbers are after fees."**
- **fee-fragile warning** — shown if B wins gross but not net (driven by the forward monitor's
  fee-fragile warning).

Funding/spread: not separately modelled for USDT-perp paper at this stage (funding ≈ 0 over the short
shadow holds; spread is folded into the slippage estimate). The card states the profile + slippage so
the assumption is visible rather than hidden.

## Evidence
- Screenshot `reports/screenshots/final_fee_card.png` — profile badge + maker/taker/slippage + "after fees".
- API: `{"active_profile":"bybit_non_vip_usdt_perp","maker_fee":0.0002,"taker_fee":0.00055,
  "all_numbers_after_fees":true,"custom_account_override":false}` (verified live).
- Test `test_fee_assumptions_default_profile_after_fees` ✅ (maker < taker, after_fees True, override off).

## Default + after-fees discipline
- Current default = **bybit_non_vip_usdt_perp** unless `custom_account_override` is configured.
- All A/B headline R/$ in the panel are **net of fees + slippage** (the engine applies `fees.fee_rate`
  per side + slippage on every fill).

## VERDICT: `FEE_ASSUMPTIONS_VISIBLE_IN_APP` ✅
