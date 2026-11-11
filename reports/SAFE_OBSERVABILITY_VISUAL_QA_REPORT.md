# PART 8 — Safe observability visual QA — REPORT
**Date:** 2026-06-26 · screenshots via Playwright (cached chromium-1208) against prod backend :8000.

## Screenshots
| file | content | verified |
|---|---|---|
| `reports/screenshots/final_shadow_bymode.png` | **By-mode A/B** section: "BY MODE · FORWARD (VALID)", forward/backfill toggle, dimension chips (mode/entry/maker-taker/regime/symbol/sector/TP), rows stocks swing Δ+2.61 / intraday Δ+2.25 / invest Δ−0.40 / crypto ~flat with maker fill % | ✅ |
| `reports/screenshots/final_shadow_ab_panel_v2.png` | full Paper Shadow A/B panel incl. the new by-mode section in place | ✅ |
| `reports/DB_RETENTION_AND_ARCHIVE_POLICY_REPORT.md` | retention dry-run table (0.5%/19.6%/45.8% by window) | ✅ (CLI text) |
| `reports/CATALYST_LINKAGE_SHADOW_AUDIT_REPORT.md` | catalyst coverage 26.3→46.0→55.1% | ✅ (CLI text) |
| `reports/A_TIER_STRICTNESS_DIAGNOSTIC_REPORT.md` | A-tier 3.78% + cap-demotion table | ✅ (CLI text) |

## Telegram digest preview
The daily digest is a Telegram *message* (not a UI element); the verified composed text is captured in
`TELEGRAM_DAILY_SHADOW_AB_DIGEST_REPORT.md` (forward window, A/B R/$, best/worst mode, maker fill, gate,
caveat). Retention / catalyst / A-tier are CLI diagnostics — their verified console output is captured in
the respective reports above.

## Notes
By-mode forward-emphasis confirmed (default shows FORWARD; backfill is behind an explicit toggle and
labelled look-ahead). No app-origin console errors; layout fits the 420px mobile viewport.

## VERDICT: `SAFE_OBSERVABILITY_VISUAL_QA_PASS` ✅
