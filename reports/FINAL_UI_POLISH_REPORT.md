# PART 5 — Final UI polish — REPORT
**Date:** 2026-06-26 · live locked · final_r untouched · no new major features.

## Click-through (Playwright, all 6 tabs)
Home · Signals · Trades · Market · Risk · System — each navigated and rendered.

## Checks + findings
| check | result |
|---|---|
| broken buttons | none — nav (aria-label per tab) + per-trade row toggles + filter chips all work |
| **horizontal overflow** | **0 px on all 6 tabs** (`scrollWidth - innerWidth` = 0 everywhere) |
| unclear labels | A/B blocks labelled "A (old)" / "B (new)"; comparison line states valid-forward vs backfill |
| duplicate numbers | Market crypto vs stocks main-risk cards are distinct (dedup verified prior pass) |
| loading/error states | panel renders `reason`/"not yet populated" when shadow rows absent; sections guard on data |
| stale warnings | look-ahead caveat + fee-fragile + maker-miss warnings are conditional, not hard-coded |
| paper/live labels | "PAPER · LIVE LOCKED" header + Risk tab manual_live/auto_live **LOCKED** badges correct |
| console errors (app) | **none from app origin**; 2 transient external-CDN fetches (tabler-icons webfont / Google Fonts) blipped once in the headless harness, gone on reload — icons still render |

## Polish change made this pass
- **Forward-first ordering** of the per-trade list + a **"fwd only"** filter chip, so the valid
  forward evidence is shown by default instead of being buried under recently-rebuilt backfill rows.

## Known minor (not fixed — pre-existing + global, low-risk to leave)
- The global "+ Manual" floating button overlaps the lower-right of long scroll lists on every tab
  (z-index/FAB), including the new per-trade list. Cosmetic; content is still reachable by scrolling.
- Icon/font CDN is remote (`cdn.jsdelivr.net`, `fonts.googleapis.com`); optional future hardening =
  self-host for full offline robustness.

## VERDICT: `FINAL_UI_POLISHED` ✅
