# PART 9 — Max-5x Safe Leverage Active in Production Paper

**Verdict: `MAX_5X_SAFE_LEVERAGE_ACTIVE_IN_PRODUCTION_PAPER`**
Date: 2026-06-25 · caught by **visual QA**, fixed, and **re-verified in the real UI**.

---

## The bug visual QA caught

The 5x leverage policy was set in `config/paper_portfolio.yaml` in a prior task, but the **real UI
still showed 2x** — a textbook "configured but not actually active" stale state:

| Field (real UI, BEFORE) | Value |
|---|---|
| Leverage card | `1.26x avg · max 2x · 9 risk-capped` |
| Exec-model note | `leverage max_2x_safe` |
| Paper equity | `$5186 · +3.72%` |

Two independent causes:
1. **Stale ledger** — `paper_portfolio_ledger` was last built under the old 2x cap, so
   `max(leverage_used)=2`; the Home leverage card reads that ledger.
2. **Hardcoded label** — `backend/app/portfolio.py` returned a literal `"leverage_policy":
   "max_2x_safe"` that could never track the config.

## Fix

- **`backend/app/portfolio.py`** — `leverage_policy` is now **data-driven**:
  `f"max_{max(a.max_leverage, b.max_leverage)}x_safe"`. It reflects the actual max leverage in the
  ledger, so the label can never go stale vs the data again.
- **Rebuilt both ledgers** under the live 5x config:
  `python -m scripts.paper_portfolio_backfill` + `python -m scripts.structural_maker_backfill`.
  `max(leverage_used)` is now **5** across all five fee profiles
  (`bybit_non_vip_usdt_perp`, `bybit_structural_maker_first`, `mexc_default_futures`,
  `conservative_taker`, `zero`).

## Re-verified in the real UI (AFTER)

| Field (real UI, AFTER) | Value |
|---|---|
| Leverage card | `1.68x avg · max 5x · 0 risk-capped · leverage ≠ risk` |
| Exec-model note | `leverage max_5x_safe` |
| Paper equity | `$5331 · +6.62%` |
| Today net | `+$314.1 · +13.47R` |
| Max drawdown | `18.3%` (risk still 0.5%/trade) |

`/api/portfolio` → `max_leverage=5, avg_leverage=1.68, return_pct=6.62`.
`/api/portfolio/compare` → `leverage_policy=max_5x_safe`.

**Risk is unchanged** — still 0.5% equity per trade, structural stop sets size; 5x is only the
notional cap that lets tighter-stop setups use their risk budget (the "9 risk-capped" trades that
were being clamped at 2x are now `0`). Leverage ≠ risk.

Screenshots (Home BEFORE 2x / AFTER 5x, System build stamp) captured via the preview QA harness.
`live_locked=true` throughout; `final_r` untouched.
