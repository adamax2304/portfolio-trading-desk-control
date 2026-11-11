"""FastAPI control-plane API.

Auth: every request carries Telegram initData (header `X-Telegram-Init-Data`), verified
server-side. Read endpoints are GET; the single state-changing path is POST /api/command
(plus thin typed wrappers that forward to it). Dangerous commands are gated in commands.py.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import commands, control_db, crypto_overlay, desk_adapter, stocks_position
from .config import get_settings
from .telegram_auth import AuthError, verify_init_data

app = FastAPI(title="AI Trading Desk — Control Plane", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    get_settings().assert_safe_for_env()  # refuse unsafe production config (AUTH_DISABLED etc.)
    control_db.init_db()


def current_user(x_telegram_init_data: str = Header(default="")) -> dict:
    try:
        return verify_init_data(x_telegram_init_data)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ----------------------------------------------------------------- reads ----
@app.get("/api/status")
def api_status(user: dict = Depends(current_user)):
    return desk_adapter.system_status()


# --- Stocks Position Framework (SHADOW ONLY) — read-only; never in the operator/paper book ---
@app.get("/api/stocks-position/summary")
def api_stocks_position_summary(user: dict = Depends(current_user)):
    return stocks_position.summary()


@app.get("/api/stocks-position/candidates")
def api_stocks_position_candidates(limit: int = 25, user: dict = Depends(current_user)):
    return stocks_position.candidates(limit=limit)


# --- Crypto Quality Overlay (READ-ONLY diagnostics) — soft PAPER sizing/routing breaker read-model.
#     Never triggers a trade / config change / live unlock; live stays LOCKED. ---
@app.get("/api/crypto-overlay/report")
def api_crypto_overlay_report(user: dict = Depends(current_user)):
    """Decision mix (FULL/HALF/SHADOW/BLOCK), top reduce/shadow reasons, active session + symbol
    cooldowns (current weak sessions), worst current symbols, and the avoided-loss vs missed-profit
    counterfactual windows (d2/d7/d14/all). Reads the desk read-model tables; never writes."""
    return crypto_overlay.overlay_report()


@app.get("/api/crypto-overlay/signal/{signal_id}")
def api_crypto_overlay_signal(signal_id: str, user: dict = Depends(current_user)):
    """Per-signal overlay decision: quality_action + verdict + score + reasons + cooldown state +
    BTC regime + session bucket + whether the overlay changed the action/size (read-only)."""
    return crypto_overlay.signal_decision(signal_id)


@app.get("/api/signals")
def api_signals(user: dict = Depends(current_user)):
    return {"signals": desk_adapter.list_signals()}


@app.get("/api/signals/{signal_id}")
def api_signal(signal_id: str, user: dict = Depends(current_user)):
    sig = desk_adapter.get_signal(signal_id)
    if not sig:
        raise HTTPException(404, "signal not found")
    return sig


@app.get("/api/trades/{bucket}")
def api_trades(bucket: str, user: dict = Depends(current_user)):
    if bucket not in {"open", "pending", "closed", "shadow"}:
        raise HTTPException(400, "bad bucket")
    return {"bucket": bucket, "trades": desk_adapter.trades(bucket)}


@app.get("/api/dashboard/summary")
def api_dashboard_summary(user: dict = Depends(current_user)):
    """Canonical, deduped, book-separated dashboard summary (Operator/Paper/Shadow).
    Today R = Operator Book, deduped, terminal realized only, shadow excluded."""
    return desk_adapter.dashboard_summary()


@app.get("/api/closed/{book}")
def api_closed(book: str, hours: float | None = None, user: dict = Depends(current_user)):
    if book not in {"operator", "paper", "shadow", "research"}:
        raise HTTPException(400, "bad book")
    return {"book": book, "hours": hours,
            "trades": desk_adapter.closed_trades_book(book, hours)}


@app.get("/api/closed/{book}/analytics")
def api_closed_analytics(book: str, hours: float | None = None,
                         fee_profile: str | None = None,
                         user: dict = Depends(current_user)):
    if book not in {"operator", "paper", "shadow", "research"}:
        raise HTTPException(400, "bad book")
    return desk_adapter.closed_trades_analytics(book, hours, fee_profile)


@app.get("/api/near-winners")
def api_near_winners(book: str = "operator", hours: float | None = 168.0,
                     user: dict = Depends(current_user)):
    return desk_adapter.near_winners(book, hours)


@app.get("/api/chart/{symbol:path}")
def api_chart(symbol: str, tf: str = "5m", user: dict = Depends(current_user)):
    return desk_adapter.chart(symbol, tf)


@app.get("/api/market/summary")
def api_market(user: dict = Depends(current_user)):
    return desk_adapter.market_summary()


@app.get("/api/risk/config")
def api_risk_config(user: dict = Depends(current_user)):
    s = control_db.all_settings()
    s["_locked"] = {"crypto_scalp": True, "stocks_scalp": True,
                    "manual_live": True, "auto_live": True}
    return s


@app.get("/api/paper-features")
def api_paper_features(user: dict = Depends(current_user)):
    """Active/shadow/archived/dangerous PAPER feature flags (read-only)."""
    from app import paper_features
    return paper_features.paper_features_summary()


@app.get("/api/portfolio")
def api_portfolio(fee_profile: str | None = None, user: dict = Depends(current_user)):
    """Paper portfolio summary ($5000 start, 0.5% risk, fees) — read-only."""
    from app import portfolio
    return portfolio.portfolio_summary(fee_profile)


@app.get("/api/portfolio/compare")
def api_portfolio_compare(user: dict = Depends(current_user)):
    """A (mechanical taker) vs B (structural + maker-first + fee-aware + 2x) — read-only."""
    from app import portfolio
    return portfolio.portfolio_compare()


@app.get("/api/portfolio/by-asset")
def api_portfolio_by_asset(fee_profile: str | None = None, user: dict = Depends(current_user)):
    """Crypto-only vs stocks-only P&L contribution + per-asset execution-cost split (read-only)."""
    from app import portfolio
    return portfolio.portfolio_by_asset(fee_profile)


@app.get("/api/portfolio/trades")
def api_portfolio_trades(limit: int = 100, fee_profile: str | None = None, user: dict = Depends(current_user)):
    from app import portfolio
    return {"trades": portfolio.portfolio_trades(limit, fee_profile)}


@app.get("/api/trades/{signal_id}/chart-events")
def api_chart_events(signal_id: str, user: dict = Depends(current_user)):
    """Entry/stop/TP/moved-stop/exit markers for one trade's chart."""
    from app import portfolio
    return portfolio.chart_events(signal_id)


@app.get("/api/trades/{signal_id}/lifecycle")
def api_trade_lifecycle(signal_id: str, user: dict = Depends(current_user)):
    """Full paper position lifecycle: entry, partial TP fills, moved/structural stops,
    remainder exit, blended R + $ — read-only, live-derived."""
    from app import lifecycle
    return lifecycle.position_lifecycle(signal_id)


@app.get("/api/market-dashboard")
def api_market_dashboard(user: dict = Depends(current_user)):
    """Market risk/news dashboard (fear&greed, regime, risk-now, curated news)."""
    from app import market_dashboard
    return market_dashboard.latest_snapshot()


@app.get("/api/missed-opportunities")
def api_missed_opportunities(limit: int = 30, user: dict = Depends(current_user)):
    """Journal of signals whose entry never triggered (missed/late)."""
    from app import lifecycle
    return lifecycle.missed_opportunities(limit)


@app.get("/api/paper-shadow/summary")
def api_paper_shadow_summary(user: dict = Depends(current_user)):
    """Paper-shadow A/B (old paper vs new-logic shadow), split forward vs backfill — read-only."""
    from app import paper_shadow
    return paper_shadow.summary()


@app.get("/api/paper-shadow/trades")
def api_paper_shadow_trades(limit: int = 60, user: dict = Depends(current_user)):
    """Per-signal A vs B side-by-side — read-only."""
    from app import paper_shadow
    return paper_shadow.trades(limit)


@app.get("/api/paper-shadow/forward")
def api_paper_shadow_forward(user: dict = Depends(current_user)):
    """Forward-window quality monitor + promotion-gate evaluation (read-only, never executes)."""
    from app import paper_shadow
    return paper_shadow.forward_monitor()


@app.get("/api/paper-shadow/fees")
def api_paper_shadow_fees(user: dict = Depends(current_user)):
    """Active fee profile + assumptions (read-only)."""
    from app import paper_shadow
    return paper_shadow.fee_assumptions()


@app.get("/api/paper-shadow/breakdown")
def api_paper_shadow_breakdown(user: dict = Depends(current_user)):
    """Forward A/B by mode/asset/symbol/sector/regime/entry_mode/tp_set/maker-taker (read-only)."""
    from app import paper_shadow
    return paper_shadow.breakdown()


@app.get("/api/news-source-health")
def api_news_source_health(user: dict = Depends(current_user)):
    """READ-ONLY News Source Health (per-source OK/STALE/DEAD/DISABLED, stale warnings, rows +
    symbol-match). Reads the desk's diagnostics artifact; never fetches network or changes anything."""
    from app import news_health
    return news_health.source_health()


@app.get("/api/news-entity-health")
def api_news_entity_health(user: dict = Depends(current_user)):
    """READ-ONLY News Entity Resolver Health (trusted-symbol resolver freshness/coverage).
    Reads the desk's diagnostics artifact; never resolves news or changes trading state."""
    from app import news_health
    return news_health.entity_health()


@app.get("/api/news-catalysts")
def api_news_catalysts(user: dict = Depends(current_user)):
    """READ-ONLY production news catalysts + RISK-ONLY warnings (block_requires_operator_review /
    do_not_chase / risk_warning / freshness / source_quality / conflicting_news) plus the
    normalized-event summary. Reads the desk's diagnostics artifact; NEVER a buy/sell, never a
    score/tier change, never fetches network, live locked."""
    from app import news_catalysts
    return news_catalysts.catalysts()


@app.get("/api/paper-shadow/readiness")
def api_paper_shadow_readiness(user: dict = Depends(current_user)):
    """Per (asset_class, mode) promotion-readiness with the 3-verdict scale (NOT_READY / WATCH /
    READY_FOR_OPERATOR_REVIEW), fee-profile integrity, and DATA_GAP_LATE warnings. Read-only,
    evaluation-only — NEVER auto-promotes; live / auto-live / manual-live remain locked."""
    from app import paper_shadow
    return paper_shadow.readiness_by_mode()


@app.get("/api/system/health")
def api_health(user: dict = Depends(current_user)):
    return desk_adapter.system_health()


@app.get("/api/audit")
def api_audit(user: dict = Depends(current_user)):
    return {"audit": control_db.recent_audit(), "commands": control_db.recent_commands()}


@app.get("/api/audit/recent")
def api_audit_recent(limit: int = 50, user: dict = Depends(current_user)):
    return {"audit": control_db.recent_audit(limit)}


@app.get("/api/commands/recent")
def api_commands_recent(limit: int = 50, user: dict = Depends(current_user)):
    return {"commands": control_db.recent_commands(limit)}


@app.get("/api/orders/recent")
def api_orders_recent(limit: int = 50, user: dict = Depends(current_user)):
    return {"orders": control_db.recent_manual_orders(limit)}


@app.get("/api/notes/recent")
def api_notes_recent(limit: int = 50, ref: str | None = None, user: dict = Depends(current_user)):
    return {"notes": control_db.recent_notes(limit, ref)}


@app.get("/api/system/errors")
def api_system_errors(user: dict = Depends(current_user)):
    return desk_adapter.system_errors()


@app.get("/api/system/sanity-check")
def api_system_sanity(user: dict = Depends(current_user)):
    return desk_adapter.sanity_check()


# --------------------------------------------------------------- commands ---
class Command(BaseModel):
    type: str
    payload: dict[str, Any] = {}
    confirm_token: str | None = None


_ALWAYS_SAFE_COMMANDS = {"ACK_ERROR", "ACKNOWLEDGE_ALERT", "ADD_NOTE", "ADD_TRADE_NOTE", "RUN_SANITY_CHECK"}


def _require_confirm(command_type: str, confirm_token: str | None) -> None:
    """Shared confirm-gate: state-changing commands need a NON-EMPTY confirm token.
    A blank/whitespace token is treated as missing (400) so no state-changing path can be
    entered without an explicit confirmation."""
    if command_type in _ALWAYS_SAFE_COMMANDS:
        return
    if not (confirm_token or "").strip():
        raise HTTPException(400, "confirm_token required for this action")


@app.post("/api/command")
def api_command(cmd: Command, user: dict = Depends(current_user)):
    # state-changing commands (except always-safe ones) require an explicit confirm token
    _require_confirm(cmd.type, cmd.confirm_token)
    result = commands.process_command(cmd.type, cmd.payload, user)
    return result


# thin typed wrappers (all funnel into the command processor)
class RiskUpdate(BaseModel):
    key: str
    value: float
    confirm_token: str


@app.post("/api/risk/update")
def api_risk_update(req: RiskUpdate, user: dict = Depends(current_user)):
    mapping = {"risk_per_trade": "SET_RISK_PER_TRADE", "paper_balance": "SET_PAPER_BALANCE",
               "daily_loss_limit": "SET_DAILY_LOSS_LIMIT", "weekly_loss_limit": "SET_WEEKLY_LOSS_LIMIT"}
    ctype = mapping.get(req.key)
    if not ctype:
        raise HTTPException(400, f"risk key '{req.key}' not settable")
    # SAME confirm gate as /api/command — a blank confirm_token must NOT slip through this
    # typed wrapper (it is a state-changing risk edit, never always-safe).
    _require_confirm(ctype, req.confirm_token)
    return commands.process_command(ctype, {"value": req.value}, user)


@app.post("/api/emergency-pause")
def api_emergency_pause(x_telegram_init_data: str = Header(default=""),
                        x_control_bot_token: str = Header(default="")):
    """Safe pause path. Accepts a verified Mini App user OR the server-to-server bot token
    (the bot cannot mint initData). Only EMERGENCY_PAUSE — the single safest command."""
    s = get_settings()
    if s.control_bot_token and x_control_bot_token and \
            hmac.compare_digest(x_control_bot_token, s.control_bot_token):
        user = {"id": 0, "username": "bot", "_auth": "bot_token"}
    else:
        try:
            user = verify_init_data(x_telegram_init_data)
        except AuthError as e:
            raise HTTPException(401, str(e))
    return commands.process_command("EMERGENCY_PAUSE", {}, user)


import json as _json  # noqa: E402
from pathlib import Path as _PathH  # noqa: E402
from datetime import datetime as _dt, timezone as _tz  # noqa: E402

_BACKEND_START = _dt.now(_tz.utc).isoformat()


def _served_ui_build() -> dict:
    """Read the served bundle's build stamp (frontend/dist/build_info.json) so health
    can prove which UI is live — kills 'stale frontend' ambiguity (PART 0)."""
    try:
        p = _PathH(__file__).resolve().parents[2] / "frontend" / "dist" / "build_info.json"
        if p.is_file():
            return _json.loads(p.read_text())
    except Exception:
        pass
    return {}


def _keeper_last_restart() -> dict:
    """Keeper's last restart reason (health_fail / build_id_drift) for the System tab (PART 5)."""
    try:
        p = _PathH(__file__).resolve().parents[2] / "scripts" / "keeper_last_restart.json"
        if p.is_file():
            return _json.loads(p.read_text())
    except Exception:
        pass
    return {}


@app.get("/api/health")
def health():  # unauthenticated liveness probe (no sensitive data)
    s = get_settings()
    ui = _served_ui_build()
    kr = _keeper_last_restart()
    return {"ok": True, "demo_mode": s.demo_mode, "live_locked": True,
            "auto_live_locked": s.auto_live_locked, "app_env": s.app_env,
            "has_desk_db": s.has_desk_db,
            "version": app.version, "backend_start_time": _BACKEND_START,
            "ui_build_id": ui.get("build_id"), "ui_build_time": ui.get("build_time"),
            "keeper_last_restart_reason": kr.get("reason"), "keeper_last_restart_at": kr.get("at")}


# --- Serve the built Mini App (frontend/dist) at "/" so the whole app is one
#     HTTPS origin behind the tunnel — no Vite dev server / HMR websocket, which
#     is what Telegram's mobile webview chokes on. All /api routes above are
#     registered first and take precedence; this static mount is the SPA fallback.
#     Read-only static files; never touches trading logic.
from pathlib import Path as _Path  # noqa: E402
from fastapi.staticfiles import StaticFiles as _StaticFiles  # noqa: E402

_DIST = _Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", _StaticFiles(directory=str(_DIST), html=True), name="frontend")
