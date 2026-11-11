# Security Hardening (PART 9)

**Date:** 2026-06-17

## Verified controls
| Control | Status | Evidence |
|---|---|---|
| `AUTH_DISABLED` cannot be used in production | ✅ | `Settings.assert_safe_for_env()` raises if `APP_ENV=production` + `AUTH_DISABLED=1`; called at startup. Test: `test_production_forbids_auth_disabled` |
| Allowed Telegram user ids required in prod | ✅ | `assert_safe_for_env()` requires `ALLOWED_TELEGRAM_USER_IDS` + `TELEGRAM_BOT_TOKEN` in production |
| initData validation active | ✅ | HMAC-SHA256 + freshness + whitelist ([telegram_auth.py](../backend/app/telegram_auth.py)). Tests: valid passes, bad hash rejected, non-whitelisted rejected, missing-auth → 401 |
| Command payload validation | ✅ | Per-command range/type checks in [commands.py](../backend/app/commands.py); unknown type rejected + audited |
| Live commands rejected server-side | ✅ | `MANUAL_LIVE_ORDER`, `SET_MODE manual_live`, `SET_LIVE_BALANCE` hard-rejected. Tests assert it |
| Auto-live rejected server-side | ✅ | `SET_MODE auto_live` rejected; `auto_live_locked=True` |
| Crypto/stocks scalp enable rejected | ✅ | `ENABLE_MODE[_PAPER] crypto_scalp/stocks_scalp` rejected. Tests assert it |
| C-tier manual order rejected | ✅ | actionability gate (`blocked`); manual paper order on non-actionable signal rejected |
| Command audit always written | ✅ | Every path (applied/rejected/failed/unknown) writes `control_audit_log`. Test: `test_command_writes_audit_row` |
| No secrets in frontend | ✅ | Bot token / whitelist / `CONTROL_BOT_TOKEN` are backend-env only; frontend bundle carries none |
| No exchange keys anywhere | ✅ | No exchange execution / keys in this app at all |
| No dangerous endpoint unauthenticated | ✅ | Only `/api/health` (liveness, no data) is unauthenticated; all reads/commands require initData. `/api/emergency-pause` accepts a verified user OR the `CONTROL_BOT_TOKEN` secret |
| Trading DB read-only | ✅ | `mode=ro` connection; no write path to desk DB or YAML |
| Confirm token required for state changes | ✅ | `/api/command` requires `confirm_token` except always-safe (note/ack/sanity) |

## Bot pause path
The bot authenticates the emergency-pause call with `X-Control-Bot-Token` (constant-time
compared to `CONTROL_BOT_TOKEN`). This is limited to the single safest command (pause). If the
token is unset or wrong and no valid initData is supplied, the call is rejected (401).

## Residual notes (acceptable for v1, tighten for public prod)
- CORS `allow_origins=["*"]` — fine for same-origin / Telegram; restrict for a public API.
- Owner-only model (no per-role RBAC); the `approved` command state is reserved for a future
  maker/checker flow.
- Rate limiting is not implemented (single-owner tool); add a reverse-proxy limit if exposed.

## Tests added/confirmed
Auth (4), live/auto-live locks (3), scalp locks (2), risk-range (3), manual-order gating (3),
audit-written (1), production guard (1), bot-token pause (1). Full suite: **33 passed**.
