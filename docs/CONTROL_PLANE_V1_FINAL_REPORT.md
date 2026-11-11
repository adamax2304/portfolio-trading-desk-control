# Control Plane v1 — Final Report (PART 12)

**Date:** 2026-06-17

> ## ✅ Verdict: `CONTROL_PLANE_V1_READ_ONLY_PLUS_PAPER_READY`
>
> A safe, launch-ready control plane: read-only monitoring of the real desk + audited paper
> risk/order controls + emergency pause. Live trading, auto-live, and exchange execution remain
> fully locked. (`CONTROL_PLANE_V1_LAUNCH_READY` is true *as a control plane*; the precise tag
> reflects that "paper trades" are control-plane records, not core-engine executions.)

### 1. What is implemented?
- **Read-only desk:** signals, trades, charts (entry/stop/TP overlays + entry/exit markers,
  autoscale), market narratives/funding-OI, system health — over the real crypto-ai-desk DB
  (read-only) with a full demo fallback.
- **Paper/risk controls:** tap-to-edit Risk screen → confirm → audited command queue:
  paper balance, risk/trade, daily & weekly loss caps, max positions, enable/disable paper modes.
- **Paper orders:** manual-from-signal (gated) + custom (paper-only, stop required); close /
  cancel / notes / acknowledge as audited control-plane actions; honest queued/applied/rejected.
- **Command queue + audit:** full lifecycle, idempotent actions, `/commands/recent`,
  `/audit/recent`, `/orders/recent`, surfaced in System & Risk.
- **System health & sanity:** rich health endpoint (DB reachability, freshness, queue health,
  schema check), `/system/errors`, `/system/sanity-check` + `RUN_SANITY_CHECK`, Run-Sanity button.
- **Telegram:** server-side initData auth + whitelist; thin bot (`/start`, `/help`, Open Mini App,
  emergency pause via server-to-server token).
- **Ops:** `.env.example`, README, PowerShell launch scripts, 12 docs, 33 backend tests.

### 2. What is safe?
Single write path (command queue) — validated, gated, audited, reversible. Trading DB opened
read-only; trading YAML never touched. Production refuses unsafe config (`AUTH_DISABLED`).
No secrets/keys in the frontend.

### 3. What remains locked?
Live trading, auto-live, exchange order placement, crypto scalp enable, stocks scalp production,
C-tier→live/manual, live balance, direct config writes, unlogged commands.

### 4. What can the user do now?
Monitor the desk from Telegram; view signals/trades/charts/market/health; tune paper risk &
modes; place/close/cancel paper orders; record notes; run a sanity check; emergency-pause —
all audited.

### 5. What is still NOT allowed?
Anything that places real orders or moves funds; enabling scalp; promoting C-tier; changing
strategy/scoring/TP-SL/thresholds; writing to the desk DB/YAML.

### 6. How to run it?
See [LOCAL_LAUNCH_RUNBOOK.md](LOCAL_LAUNCH_RUNBOOK.md): configure `.env` → `start_backend.ps1`
→ `start_frontend.ps1` → (`start_bot.ps1`) → open Mini App → verify → stop.

### 7. What should be tested manually?
[V1_LAUNCH_CHECKLIST.md](V1_LAUNCH_CHECKLIST.md): auth (whitelist + 401), live/scalp locks,
sanity 9/9, a paper risk edit (applied & audited), a paper order + close, emergency pause,
charts, no console/backend errors, 390/430 layout.

### 8. Phase 3 / Live (future)
Wire control-plane paper actions into the core paper engine; live-readiness audit (30d forward
validation) before any live unlock; SSE/WebSocket push; per-trade equity sparklines; RBAC +
rate limiting + CORS tightening; frontend component tests.

### 9. Known limitations
Paper actions are control-plane bookkeeping (not core executions); polling not push; no per-trade
sparkline; no frontend test runner; CORS open; owner-only.

---
**Build:** frontend 0 TS errors (92 modules). **Tests:** backend 33 passed. **Real DB:**
read-only verified (signals + health 9/9 + sanity 9/9). **Console:** clean.

> ## `CONTROL_PLANE_V1_READ_ONLY_PLUS_PAPER_READY`
