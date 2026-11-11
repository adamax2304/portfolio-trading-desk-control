# SAFE OBSERVABILITY + DB HYGIENE PASS — FINAL REPORT
**Date:** 2026-06-26 · **Posture:** `live_locked=true`, `auto_live_locked=true`, no orders,
`final_r` untouched, strategy/actionability/scoring unchanged, A-tier threshold unchanged, B not promoted,
backfill never used as proof.

## 13 questions
1. **Is per-mode A/B breakdown active?** ✅ `/api/paper-shadow/breakdown` + Mini App *By mode* section
   across mode/asset/symbol/sector/regime/entry_mode/tp_set/maker-taker; forward-emphasized, backfill
   labelled look-ahead. (`final_shadow_bymode.png`).
2. **Is Telegram daily digest active?** ✅ `paper-shadow-digest-send` CLI + scheduler step (idempotent
   once-daily) + `config/paper_shadow_digest.yaml`; includes best/worst mode, maker fill, gate, caveat.
3. **Is DB retention safe and ready?** ✅ `signal-outcomes-retention` (dry-run default; latest-row-per-signal
   + final outcomes + recent N days always kept; archive-then-delete to parquet). Synthetic-DB test proves
   no final outcome is lost. **Ready; not yet run on the live DB — awaiting your choice of window.**
4. **How much DB bloat exists?** ≈**1994 MB**; `signal_outcomes` = **371,246 rows / 2,446 signals
   (151.8 per-bar rows each)**. Archivable: 0.5% @30d, **19.6% @14d**, 45.8% @7d (latest 2,446 always kept).
5. **Is catalyst shadow audit complete?** ✅ `catalyst-linkage-shadow-audit` → `catalyst_shadow_audit`;
   396 signals (7d).
6. **How much could catalyst coverage improve at 24h/48h?** current ~5h **26.3%** → 24h **46.0%**
   (+19.7pp, 86 newly) → 48h **55.1%** (+28.8pp, 116 newly). Widening to 48h ~doubles coverage. FP risk
   negligible (exact `detected_symbols_json`). **Diagnostic only — not fed to scoring.**
7. **Was scoring unchanged?** ✅ no scoring/routing/actionability change; catalyst audit writes only the
   additive shadow table.
8. **Was A-tier threshold unchanged?** ✅ still 80. Diagnostic: 86 A over 30d (**3.78%**); lowering the bar
   barely helps (at 70, 550/636 high scorers are cap-demoted) → A is **correctly rare**.
9. **Are stocks scalp/swing/invest still non-actionable?** ✅ unchanged. Readiness: swing & intraday =
   *paper_shadow_candidate*, scalp & invest = *research_only*. No mode enabled.
10. **Did tests pass?** ✅ new 11 (crypto safe-obs 7 + backend breakdown 4); regression backend 76/6-skip,
    crypto shadow+coverage+obs 22; compileall both = 0; frontend build clean.
11. **Did live remain off?** ✅ `live_locked` + `auto_live_locked`.
12. **Was `final_r` untouched?** ✅ retention keeps the final row per signal and never rewrites `final_r`
    (asserted by test + source scan).
13. **What should the operator monitor for the next 2–4 weeks?**
    - **Forward** B vs A net R/$ overall **and per mode** (swing leads at +2.61R; invest lags); only the
      forward window counts.
    - Promotion-gate criteria (n/6) + forward trade count toward 60-trades / 14-days.
    - Maker fill rate (edge mustn't depend on optimistic fills) + DATA_GAP excluded share.
    - DB size / `signal_outcomes` rows (run retention `--dry-run`; apply `--days 14` when ready).
    - The daily Telegram digest is the at-a-glance feed.

## Final verdicts
- `PAPER_SHADOW_PER_MODE_AB_BREAKDOWN_ACTIVE` ✅
- `TELEGRAM_DAILY_SHADOW_AB_DIGEST_ACTIVE` ✅
- `DB_RETENTION_POLICY_READY_AND_SAFE` ✅
- `CATALYST_LINKAGE_SHADOW_AUDIT_COMPLETE_NO_SCORING_CHANGE` ✅
- `A_TIER_DIAGNOSTIC_COMPLETE_NO_THRESHOLD_CHANGE` ✅
- `STOCKS_MODE_READINESS_DIAGNOSTIC_COMPLETE_NO_ACTIONABILITY_CHANGE` ✅
- `SAFE_OBSERVABILITY_DB_HYGIENE_TESTS_PASS` ✅
- `NO_LIVE_EXECUTION_ENABLED` ✅
- `HISTORICAL_FINAL_R_UNCHANGED` ✅

## Bottom line
Observability is now per-mode (you can see *where* B beats A — swing leads), the daily digest pushes the
forward delta to Telegram, DB hygiene is ready behind a safe dry-run, and three diagnostics quantify the
catalyst-linkage gap (26%→55% at 48h), A-tier rarity (correct, cap-driven), and stocks-mode readiness
(swing first) — all without touching strategy, scoring, thresholds, actionability, or `final_r`. Live
stays locked; decide on the forward window via the gate.
