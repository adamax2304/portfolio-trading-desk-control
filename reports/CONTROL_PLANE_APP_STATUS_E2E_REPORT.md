# Control Plane / App Status E2E Report (PART 4)

**Date:** 2026-06-19 · **Type:** display E2E. **No backend logic / actionability / commands changed.**

## Backend
- `desk_adapter._normalize` attaches the optional `display_*` fields (fail-open `try/except`) after `actionability.classify` — API responses now carry `display_status / display_group / display_reason / operator_label / entry_touched / is_shadow_or_review / is_active_for_operator / r_display_policy`.
- Sign-aware + contradiction-guarded mirror in `backend/app/display_status.py` (no `+-`; win/-R or loss/+R → `UNKNOWN_INCONSISTENT`; flat → `CLOSED FLAT 0R`).
- **Backend tests: 38 passed** (incl. `test_display_status` missing-field / sign / bucket cases) — no crash when fields are absent.

## Buckets (unchanged, logic-based)
`open` = entered & not closed · `pending` = actionable & not entered · `shadow` = actionability shadow · `closed` = final_outcome set. The new `display_group` enriches labels without altering these.

## Frontend
- `tsc -b` → **exit 0**.
- Empty-state copy clarified (`screens.tsx`): **"No open actionable trades"** (+ "Check Pending / Shadow/Review"), "No shadow / review trades" (scalp / C-tier / sector-capped), pending sub = "waiting for entry". So an empty Open tab is never read as "nothing happening".
- Optional `display_*` fields are typed (`types.ts`) and available to cards; existing rendering already uses computed `actionability.status` (pretty labels, never raw DB strings).

## Visual QA scope
Full dev-server visual QA was **not** run: the Control Plane needs backend + the crypto-ai-desk DB + Telegram-auth to render, and the empty-state strings only appear behind a zero-rows runtime condition that can't be forced cheaply. `tsc` + backend tests + the typed pass-through are the appropriate verification at this layer; richer card-level display of `display_group` remains a UI-only enhancement.

## Verdicts
- **CONTROL_PLANE_DISPLAY_FIELDS_OK** ✅
- **CONTROL_PLANE_EMPTY_STATES_OK** ✅
- **CONTROL_PLANE_UI_VISIBILITY_PARTIAL_BUT_SAFE** (backend fields + typed + empty-state copy live; full card-level surfacing of display_group is optional UI work, no crash risk).
