# Command Queue & Audit (PART 3)

**Date:** 2026-06-17

## Lifecycle
Every state change flows through `commands.process_command` → control DB. Command rows
(`control_commands`) carry: `command_id`, `created_at`, `applied_at`, `telegram_user_id`,
`username`, `source` (`mini_app`), `type`, `payload_json`, `status`, `result_json`, `error`.

Statuses: **pending → applied | rejected | failed** (the `approved` state exists in schema
for a future maker/checker flow; v1 owner-only auto-approves valid commands). Each command
also writes a row to `control_audit_log` (`old_value`, `new_value`, `confirmation_status`,
`result`, `error`, `command_id`).

Unknown command types and missing confirm tokens are rejected **before** apply and still
audited. Notes / acks / sanity-check are "always-safe" and need no confirm token.

## Idempotency
- Close/cancel paper actions detect terminal states and return `{idempotent:true}`.
- `RESUME_PAPER`, `EMERGENCY_PAUSE`, mode toggles are naturally idempotent (set-to-value).
- `ACKNOWLEDGE_ALERT` on an already-acked / missing id is a no-op success.

## Endpoints ([main.py](../backend/app/main.py))
- `GET /api/commands/recent?limit=` → `{commands:[…]}`
- `GET /api/audit/recent?limit=` → `{audit:[…]}`
- `GET /api/orders/recent?limit=` → `{orders:[…]}` (paper ledger)
- `GET /api/notes/recent?limit=&ref=` → `{notes:[…]}`
- `GET /api/audit` (combined, legacy) still present
- `POST /api/command` (the one write path) + thin wrappers (`/api/risk/update`, `/api/emergency-pause`)

## Frontend surfacing
- **System** screen: a **"Recent commands"** list with per-command status badges
  (applied/rejected/failed) + relative time; a **"Command queue"** health card
  (`N applied · N rejected · N failed (last 200)`).
- **Risk** screen: a **"Recent risk changes"** list filtered to `SET_*`/`ENABLE_*`/
  `DISABLE_*`/`EMERGENCY`/`RESUME` audit rows.
- **Manual order ticket**: shows the command result inline (queued/rejected/failed).

## Tests
`test_recent_endpoints` (commands/audit/orders/errors), `test_command_writes_audit_row`,
`test_health_components_present` (command-queue card) — all pass.
