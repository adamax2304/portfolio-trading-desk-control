# PART 1 — Per-trade A/B detail UI — FINAL REPORT
**Date:** 2026-06-26 · live locked · final_r untouched · B not promoted · backfill ≠ proof.

## What shipped
Mini App **System → Paper Shadow A/B** now has a full per-trade list (`[data-testid=shadow-trades]`):
- **Filter chips**: all · **fwd only** · B better · B worse · A missed · B skipped · dir flip · data gap.
- **Forward-first ordering** — the backend fetches `window='forward_since_activation'` rows first
  (the only valid evidence) then fills with recent backfill, so valid trades are not buried.
  Verified: top-20 of `/api/paper-shadow/trades` = 20/20 forward rows (CELO/USDT, UNH, TSLA…).
- **Click a row → inline A/B detail** with two branch blocks + a comparison line.

### A branch block
side · entry mode · entry order type (maker/taker) · fill status · TP set · stop type ·
gross R · **net R** · fees $ · close reason.

### B branch block
side (+ `flip old→new` when direction changed) · entry mode · order type · fill status
(+ no-chase/missed reason) · structural TP · structural stop · gross R · **net R** · fees $ ·
**maker filled/posted · taker-fallback**.

### Comparison block
ΔR (`delta.net_r`) · Δ$ · Δfees · **why** (e.g. "B +0.532R vs A (structural TP/stop)") ·
**valid forward vs backfill (look-ahead, not proof)** · data-gap flag.

## Evidence
- Screenshot `reports/screenshots/final_trade_ab_detail.png` — expanded SMCI: A short PULLBACK_LIMIT·maker
  TP ATR_LADDER gross −0.34R/net −0.3622R/fee $0.24 ; B short LIMIT_THEN_TAKER_TIMEOUT·taker TP STRUCTURAL
  gross 0.1804R/net 0.1693R/fee $0.1565 maker 0/1·taker-fb ; "B +0.532R vs A (structural TP/stop) ·
  backfill (look-ahead, not proof)".
- Screenshot `reports/screenshots/final_shadow_ab_panel.png` — fwd-first list + chips.
- Backend: `backend/app/paper_shadow.py::trades()` (enriched fields + delta + why + forward-first fetch);
  endpoint `GET /api/paper-shadow/trades`. Tests: 6/6 in `test_shadow_ab_visibility.py`.

## VERDICT: `APP_SHOWS_PER_TRADE_SHADOW_AB_DETAIL` ✅
