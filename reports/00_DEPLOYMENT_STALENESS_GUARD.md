# PART 0 — Deployment / Stale-Frontend Guard

**Verdict: `NO_STALE_FRONTEND_OR_BACKEND_RUNNING`**
Date: 2026-06-25 · Project: `trading-desk-control` (control plane for `crypto-ai-desk` paper desk)

---

## 1. What was shipped

A **build stamp** now flows end-to-end so the operator can prove which UI bundle and which
backend are actually live — this kills the "I edited code but the UI still shows the old bug"
ambiguity that has recurred across prior tasks.

| Layer | Change | File |
|---|---|---|
| Build | `BUILD_ID` (UTC, per-build) + `BUILD_TIME` computed at config load; `closeBundle` plugin writes `dist/build_info.json` | `frontend/vite.config.ts` |
| Build | `__BUILD_ID__` / `__BUILD_TIME__` injected via `define` | `frontend/vite.config.ts` |
| Types | declarations for the injected globals | `frontend/src/vite-env.d.ts` |
| Backend | `/api/health` now returns `version`, `backend_start_time`, `ui_build_id`, `ui_build_time` (read from the **served** `dist/build_info.json`) | `backend/app/main.py` |
| UI | **System tab** build-stamp card: `UI BUILD` (compiled-in) vs `UI SERVED` (from backend health) + `fresh`/`STALE` badge + `PAPER · LIVE LOCKED` | `frontend/src/screens.tsx` |

The card compares the bundle's compiled-in `__BUILD_ID__` against `health.ui_build_id`. If a
stale bundle is ever served (CDN/Telegram webview cache, or an old backend process), the badge
flips to **STALE** instead of silently lying.

## 2. Clean deploy — recorded facts

| Item | Value |
|---|---|
| Build id (live bundle) | `b-20260624-214244` |
| Served `index.html` references | `assets/index-C7ziuEJE.js` (hash-busted) |
| Backend PID | `21532` |
| Backend serves | built `frontend/dist` + `/api/*` on `:8000`, single origin |
| Operator / tunnel URL | `https://edges-protection-gaps-sentences.trycloudflare.com` (cloudflared quick-tunnel, rotating) |
| `/api/health` | `ok=true`, `ui_build_id=b-20260624-214244`, `live_locked=true`, `auto_live_locked=true` |
| Frontend process | none separate — backend serves the static bundle (no Vite/HMR in prod; that is what Telegram's mobile webview chokes on) |
| Visual confirmation | System tab renders `BUILD: fresh`, `UI BUILD: b-20260624-214244`, `PAPER · LIVE LOCKED` (screenshot captured via preview QA) |

`health.ui_build_id` **matches** the bundle hash served at `/` → frontend and backend are the
same generation. No stale frontend, no stale backend.

## 3. Root cause of the recurring "stale backend" (new finding)

While redeploying, the canonical race reproduced and was diagnosed:

- The CP keeper **`CryptoAIDeskApp` → `scripts/app_keeper.bat`** only relaunches the backend
  when a health probe **fails**. A long-running backend process started *before* a code edit keeps
  passing health, so the keeper never replaces it — **the old in-memory code keeps serving on
  `:8000` until the process is manually killed.** That is the mechanism behind "I changed the code
  but the app still shows the old behavior."
- Killing the `:8000` owner and starting a detached uvicorn is unreliable in this shell (port
  `TIME_WAIT` race); the keeper would also re-grab the port. The reliable path is
  **`scripts/launch_robust.ps1`** (scoped kill of backend/tunnel/bot/vite → fresh backend serving
  fresh `dist` → fresh tunnel).
- The new build stamp makes this **detectable** (System tab → STALE badge; `health.ui_build_id`
  vs bundle). A follow-up enhancement is to make the keeper restart on **build-id drift**, not
  only on health failure.

Watchdog tasks `CryptoAIDeskApp` and `CryptoAIDeskHeartbeat` were briefly disabled to clear the
stale process, then **re-enabled** (persistence restored). Post-enable check: `:8000` still owned
by the fresh backend `pid 21532`, `ui_build_id=b-20260624-214244`, `live_locked=true`.

## 4. Safety posture (unchanged)

`live_locked=true`, `auto_live_locked=true`. No live, no exchange execution, no real orders.
`signal_outcomes.final_r` untouched. All work is on the paper/read-model path.
