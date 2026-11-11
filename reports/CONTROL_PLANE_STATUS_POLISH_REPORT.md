# Control Plane Status Polish Report (PART 6)

**Date:** 2026-06-19 · **Type:** display polish. **No backend logic / actionability / commands changed.**

## Checks
- **Backend tests:** `pytest tests/test_display_status.py tests/test_control_plane.py` → **38 passed**.
- **Frontend typecheck:** `tsc -b` → **exit 0**.
- **Optional display fields don't crash:** `derive_display_status({})` returns a valid dict; missing-field test passes. Adapter attaches `display_*` via a fail-open `try/except` (`backend/app/desk_adapter.py`).
- **Sign bug:** the Control-Plane mirror (`backend/app/display_status.py`) got the same sign-aware fix — `CLOSED_WIN`/`CLOSED_LOSS` use `:+.1f` and contradiction-guards → never `+-1.0R`; the unsafe module-level `_LABELS` mutation was removed (label built locally).

## Bucket sanity
The existing buckets already separate the right things (computed `actionability.status`, not raw status):
- **open** = `entry_triggered_at && !final_outcome && actionability!="closed"`
- **pending** = `actionability=="actionable" && !entry_triggered_at`
- **shadow** = `actionability=="shadow"`
- **closed** = `final_outcome` set
The new `display_group` field is now available alongside for richer labels (OPEN_ACTIVE / WAITING / ENTERED_UNRESOLVED_EXPIRED / REVIEW_ONLY_SHADOW / NO_ENTRY_EXPIRED / CLOSED_*), without changing the existing bucket logic.

## Safe UI text fix (no redesign)
`frontend/src/screens.tsx` empty-state copy clarified so an empty Open tab is never read as "nothing happening":
- open: **"No open actionable trades"** — "Check Pending (waiting for entry) and Shadow/Review for non-actionable setups."
- shadow: **"No shadow / review trades"** — "Scalp / C-tier / sector-capped (not actionable by policy) would show here."
- pending sub clarified to "waiting for entry".

No structural UI change; tabs/cards/metrics untouched. (Full dev-server preview not started: this is static copy gated behind an empty-bucket runtime state that needs backend+DB+auth to reproduce; `tsc` + tests cover the change.)

## Verdict
**CONTROL_PLANE_STATUS_POLISH_READY**
