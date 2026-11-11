# Control Plane — Risk Fields Display Plan (PART 3)

**Date:** 2026-06-17 · **Status:** plan only — backend pass-through is live; frontend display is **not** built yet (no frontend break).

## What's already live (safe)
- `backend/app/desk_adapter.py` reads the new diagnostic fields from `signal_alerts.payload_json` via `.get()` and includes them in the normalized signal dict (`circuit_breaker_state`, `day_realized_r`, `stops_today`, `btc_intraday_risk_off`, `regime_context`, `lifecycle_label`, `held_hours`, `next_day_revalidation_required`, `carryover_warning`, `would_bind_sector_cap`, `profit_protection_hint`, `catalyst_integrity_status`, `direct_news_items_checked`, `catalyst_mapping_confidence`).
- `frontend/src/types.ts` `Signal` declares them as optional → existing components compile and ignore them.

## Proposed display (additive, read-only — do NOT change commands/locks/routing)
1. **Signal card badge row** (`components.tsx`): small chips when present —
   - `🛡 cb:would_pause` (red) / `cb:watch` (amber) when `circuit_breaker_state ≠ ok`.
   - `regime: btc_risk_off` chip when `btc_intraday_risk_off`.
   - `lifecycle: carryover` chip when `next_day_revalidation_required`.
   - `cap: shadow` chip when `would_bind_sector_cap ∈ {shadow_sector_cap, half_size}`.
   - `catalyst-backed` chip when `catalyst_integrity_status = catalyst_backed_confirmed`.
2. **Trade detail panel** (`screens.tsx`): a read-only "Risk Guards (diagnostic)" section listing `day_realized_r`, `stops_today`, `consecutive_stops`, `crypto_long_streak_count`, `held_hours`, `position_advisor_status` + `suggested_notional` + `max_safe_leverage_estimate`.
3. **System health** (`/api/system/health`): an optional "circuit breaker today" line aggregated from the latest alerts' `day_realized_r` / `stops_today` (display only).

## Hard constraints
- All chips/sections are **display-only**; none feed `actionability.classify` or any command.
- Every field is optional → render `?? "—"`; never throw on absence.
- No change to the live/auto-live lock, command queue, or paper/disabled trading mode.

## Sequencing
Ship the badge chips first (lowest effort, highest glance-value), then the trade-detail Risk Guards section. Each is independently revertible by removing the component block.
