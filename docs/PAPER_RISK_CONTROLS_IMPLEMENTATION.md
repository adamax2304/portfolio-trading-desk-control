# Paper / Risk Control Flow (PART 1)

**Date:** 2026-06-17 · paper-only, audited, reversible. Live/auto-live remain locked.

## UI flow
Risk screen ([screens.tsx](../frontend/src/screens.tsx) `Risk`) shows tap-to-edit metric
cards. Tapping one opens [RiskEditModal](../frontend/src/RiskEditModal.tsx):

old value → new value → impact note → **Confirm** → `POST /api/command` (with confirm token)
→ backend validates + gates + applies to the control DB + writes an audit row → modal shows
**"Applied & audited"** or **"Rejected: …"**, then queries refetch.

Editable: paper balance, risk/trade, daily loss cap, weekly loss cap, max open positions,
and the allowed paper modes (enable/disable). Max sector exposure is shown read-only.
A **"Recent risk changes"** panel renders the latest audit rows.

## Backend commands ([commands.py](../backend/app/commands.py))
| Command | Validation |
|---|---|
| `SET_PAPER_BALANCE` | 0 ≤ v ≤ 1,000,000 |
| `SET_RISK_PER_TRADE` | 0 < v ≤ 0.05 (5%) |
| `SET_DAILY_LOSS_LIMIT` | 0 < v ≤ 0.5 |
| `SET_WEEKLY_LOSS_LIMIT` | 0 < v ≤ 0.8 |
| `SET_MAX_OPEN_POSITIONS` | integer 1–50 |
| `ENABLE_MODE_PAPER` / `DISABLE_MODE_PAPER` | scalp can NEVER be enabled; unknown mode rejected |
| `EMERGENCY_PAUSE` / `RESUME_PAPER` | always-safe flag |
| `ADD_NOTE` / `ADD_TRADE_NOTE` | text required, ≤ 2000 chars |
| `SET_LIVE_BALANCE`, `MANUAL_LIVE_ORDER`, `SET_MODE manual_live/auto_live` | **hard-rejected** |

Legacy aliases `ENABLE_MODE`/`DISABLE_MODE`/`RESUME` still work.

## Runtime overrides (no YAML writes)
All editable state lives in the control DB `control_settings` table (the runtime-override
store), seeded from `DEFAULT_SETTINGS` in [control_db.py](../backend/app/control_db.py).
**The crypto-ai-desk trading YAML/DB is never written.** The control plane is the source of
truth for paper/risk overrides; core-engine consumption of these overrides is Phase 3.

## Tests
`SET_MAX_OPEN_POSITIONS` (valid + out-of-range), `SET_WEEKLY_LOSS_LIMIT` range,
`ENABLE_MODE_PAPER` alias + scalp lock, plus the pre-existing risk-range and live-lock tests.
All pass (see [V1_FULL_TEST_AND_QA_REPORT.md](V1_FULL_TEST_AND_QA_REPORT.md)).
