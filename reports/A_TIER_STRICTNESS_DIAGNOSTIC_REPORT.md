# PART 5 — A-tier strictness diagnostic — REPORT (diagnostic only)
**Date:** 2026-06-26 · NO threshold change · `src/diagnostics/a_tier_strictness.py`.

## Mechanism
A-tier requires `score >= a_tier_threshold (=80) AND no cap reasons` (scoring_agent). So A is rare for
**two** reasons: few signals reach 80, AND high scorers are often *capped* (earnings active / partial
data / macro-event) and demoted.

## Findings (last 30d — bigger sample than the 7d "A=1")
**All assets: 2,276 signals · 86 actual A (3.78%) · score p50/p90/max = 66.1 / 76.5 / 97.5.**

| threshold | score ≥ thr | actually A | demoted by caps |
|---|---|---|---|
| 80 (current) | 106 | 86 | **20** |
| 78 (−2) | 160 | 86 | **74** |
| 75 (−5) | 273 | 86 | **187** |
| 70 (−10) | 636 | 86 | **550** |

- **crypto:** 528 signals, **1 A (0.19%)**, max score 80.2 — crypto almost never reaches 80.
- **stocks:** 1,748 signals, **85 A (4.86%)**.

## Interpretation
Lowering the bar barely adds A-tiers because the **cap gate** blocks the extra candidates: at threshold
70, 550 of 636 high scorers are already capped. So **A-tier is correctly rare, not mis-tuned** — the bar
is not the bottleneck; the caps are (and they exist for good reasons: earnings/data/macro risk). The
earlier "1 in 7d" was a short-window artifact; the steady-state A rate is ~3.8%. No threshold change
recommended; if more A-tier flow is ever wanted, revisit the *caps*, not the number — as a separate
approved change.

`threshold_changed=false`. Tests: `test_a_tier_diagnostic_read_only` (no UPDATE/INSERT/DELETE; threshold const 80).

## VERDICT: `A_TIER_DIAGNOSTIC_COMPLETE_NO_THRESHOLD_CHANGE` ✅
