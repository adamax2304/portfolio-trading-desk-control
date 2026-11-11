# PART 4 — Final UI visual QA (real screenshots) — REPORT
**Date:** 2026-06-26 · live locked · final_r untouched.

## Method
The preview screenshot tool was unreliable, so screenshots were taken with **Playwright directly**
(`scripts/shadow_ab_screenshots.py`): headless Chromium (cached ms-playwright build 1208) pointed at the
production backend `http://127.0.0.1:8000`, which serves the built `dist` + real data. Mobile viewport
420×880 (Telegram Mini App size). Read-only; no live, no orders.

## Screenshots saved (reports/screenshots/)
| file | content | verified |
|---|---|---|
| `final_shadow_ab_panel.png` | A/B panel: FORWARD vs backfill rows, gate NOT_READY, fwd-first per-trade list + chips, look-ahead caveat | ✅ |
| `final_trade_ab_detail.png` | expanded per-trade A/B detail (SMCI: A vs B branch blocks + comparison) | ✅ |
| `final_fee_card.png` | fee assumptions card (bybit_non_vip, maker 0.020%/taker 0.055%, after-fees) | ✅ |
| `final_maker_realism.png` | maker realism line (posted/filled/missed/taker-fallback/fill-rate) | ✅ |
| `final_risk_tab.png` | Risk tab: **$5,000 / 0.50%**, max positions 5, manual_live + auto_live **LOCKED** | ✅ |
| `final_system_build_id.png` | System tab: build_id fresh + keeper restart row | ✅ |
| `final_market_dedup.png` | Market tab: distinct crypto ("Risk Off"/Bitcoin Sell-Off) vs stocks ("Chop") risk cards | ✅ |

## Notes
- All 7 PNGs are real renders (6.7 KB–292 KB).
- Risk tab shows the reconciled paper profile ($5,000 / 0.50%); the max-5x **leverage** cap is a
  sizing-engine constant (not a Risk-tab field) — balance + per-trade risk are the visible reconciled values.

## VERDICT: `FINAL_UI_VISUAL_QA_PASS` ✅
