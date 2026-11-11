# PART 4 — Catalyst linkage shadow audit — REPORT (diagnostic only)
**Date:** 2026-06-26 · NO scoring / actionability / news_supported / final_r change.

## Method
`src/signals/catalyst_linkage_shadow_audit.py` + CLI `catalyst-linkage-shadow-audit`. Re-runs the SAME
exact, word-boundary `detected_symbols_json` match the collector trusts (never a title substring), at
the **current** (~5h scan-time proxy), **24h** and **48h** windows around each signal's creation time.
Records candidate labels into the NEW additive table `catalyst_shadow_audit`. Asset-aware (crypto vs
stocks). Does **not** touch `proposed_signals.news_supported`, `signal_catalyst_labels`, scoring, or tier.

## Findings (last 7d, 396 signals)
| window | coverage | uplift | newly linked |
|---|---|---|---|
| current (~5h, production) | **26.3%** | — | — |
| 24h | **46.0%** | +19.7 pp | 86 |
| 48h | **55.1%** | +28.8 pp | 116 |

Widening to **48h roughly doubles** catalyst coverage (26% → 55%); 218 of 396 signals had a 48h hit.

## False-positive risk
**Negligible for symbol-misattribution.** Matching is exact `detected_symbols_json` membership — the
same source-of-truth the integrity monitor trusts — so "Ordinals" never fabricates `ORDI`. The residual
risk is temporal: a real symbol-tagged catalyst being *coincidental* rather than causal. That is exactly
why this stays a SHADOW label and is **not** fed to scoring without a separate, approved evaluation.

## Boundary
`scoring_changed=false`, `actionability_changed=false`. The candidate labels live only in
`catalyst_shadow_audit`. Promoting any of this into `news_supported`/scoring is a separate, explicitly
approved change (it would alter actionability). Tests: `test_catalyst_shadow_audit_no_scoring_change`.

## VERDICT: `CATALYST_LINKAGE_SHADOW_AUDIT_COMPLETE_NO_SCORING_CHANGE` ✅
