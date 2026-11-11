"""Command queue processor — the ONLY path that changes control state.

Every command is validated, gated by hard safety rules, applied to the control DB
(never the trading YAML/DB), and audited. Live + auto-live + scalp-enable + C-tier→live
are HARD-blocked in v1 regardless of payload.
"""

from __future__ import annotations

from typing import Any

from . import control_db, desk_adapter
from .config import get_settings

COMMAND_TYPES = {
    "SET_MODE", "SET_PAPER_BALANCE", "SET_LIVE_BALANCE", "SET_RISK_PER_TRADE",
    "SET_DAILY_LOSS_LIMIT", "SET_WEEKLY_LOSS_LIMIT", "SET_MAX_OPEN_POSITIONS",
    "ENABLE_MODE", "DISABLE_MODE", "ENABLE_MODE_PAPER", "DISABLE_MODE_PAPER",
    "EMERGENCY_PAUSE", "RESUME", "RESUME_PAPER",
    "MANUAL_PAPER_ORDER", "MANUAL_LIVE_ORDER",
    "CANCEL_PENDING_ORDER", "CANCEL_PENDING_PAPER", "CLOSE_PAPER_TRADE",
    "ADD_NOTE", "ADD_TRADE_NOTE", "ACK_ERROR", "ACKNOWLEDGE_ALERT",
    "RUN_SANITY_CHECK",
}
# Modes that can NEVER be enabled from the control plane (research/shadow only).
LOCKED_MODES = {"crypto_scalp", "stocks_scalp"}
# Trading modes that are locked in v1.
LOCKED_TRADING_MODES = {"manual_live", "auto_live"}


class CommandRejected(Exception):
    pass


def _user(u: dict | None):
    u = u or {}
    return u.get("id"), u.get("username")


def process_command(ctype: str, payload: dict[str, Any], user: dict | None) -> dict:
    """Validate → gate → apply → audit. Returns the command row (status applied/rejected/failed)."""
    s = get_settings()
    uid, uname = _user(user)
    payload = payload or {}

    if ctype not in COMMAND_TYPES:
        cmd = control_db.create_command(ctype, payload, user_id=uid, username=uname, status="rejected")
        control_db.update_command(cmd["command_id"], status="rejected", error="unknown command type")
        control_db.audit(ctype, user_id=uid, username=uname, error="unknown command type",
                         result="rejected", command_id=cmd["command_id"])
        return control_db.get_command(cmd["command_id"])

    cmd = control_db.create_command(ctype, payload, user_id=uid, username=uname, status="pending")
    cid = cmd["command_id"]
    try:
        result = _apply(ctype, payload, uid, uname, cid)
        control_db.update_command(cid, status="applied", result=result)
        control_db.audit(ctype, user_id=uid, username=uname, new=payload,
                         confirmation="confirmed", result="applied", command_id=cid)
    except CommandRejected as e:
        control_db.update_command(cid, status="rejected", error=str(e))
        control_db.audit(ctype, user_id=uid, username=uname, new=payload,
                         result="rejected", error=str(e), command_id=cid)
    except Exception as e:  # pragma: no cover - defensive
        control_db.update_command(cid, status="failed", error=str(e))
        control_db.audit(ctype, user_id=uid, username=uname, new=payload,
                         result="failed", error=str(e), command_id=cid)
    return control_db.get_command(cid)


# --------------------------------------------------------------- appliers ---
def _apply(ctype, payload, uid, uname, cid) -> dict:
    s = get_settings()

    # ---- always-safe ----
    if ctype == "EMERGENCY_PAUSE":
        old = control_db.get_setting("emergency_paused")
        control_db.set_setting("emergency_paused", True)
        control_db.audit("EMERGENCY_PAUSE", user_id=uid, username=uname, old=old, new=True,
                         result="paused", command_id=cid)
        return {"emergency_paused": True, "note": "engine paused via flag (no process killed)"}
    if ctype in ("RESUME", "RESUME_PAPER"):
        control_db.set_setting("emergency_paused", False)
        return {"emergency_paused": False}
    if ctype in ("ADD_NOTE", "ADD_TRADE_NOTE"):
        text = str(payload.get("text") or payload.get("note") or "").strip()
        if not text:
            raise CommandRejected("note text required")
        if len(text) > 2000:
            raise CommandRejected("note too long (max 2000 chars)")
        ref = payload.get("ref") or payload.get("signal_id") or payload.get("order_id")
        nid = control_db.add_trade_note(text, ref=ref, user_id=uid, username=uname, command_id=cid)
        return {"note_id": nid, "ref": ref}
    if ctype in ("ACK_ERROR", "ACKNOWLEDGE_ALERT"):
        nid = payload.get("notification_id") or payload.get("id")
        if nid is None:
            return {"ok": True, "note": "no notification id — nothing to ack"}
        ok = control_db.ack_notification(nid)
        return {"ok": ok, "acked": nid}
    if ctype == "RUN_SANITY_CHECK":
        report = desk_adapter.sanity_check()
        control_db.add_notification(
            "info" if report.get("ok") else "warning",
            "Sanity check", f"{report.get('passed',0)}/{report.get('total',0)} checks ok")
        return report

    # ---- live / auto-live HARD lock ----
    if ctype == "MANUAL_LIVE_ORDER":
        raise CommandRejected("manual-live orders are locked in v1 (requires live readiness audit)")
    if ctype == "SET_MODE":
        mode = str(payload.get("mode", "")).lower()
        if mode in LOCKED_TRADING_MODES:
            raise CommandRejected(f"trading mode '{mode}' is locked in v1")
        if mode not in {"disabled", "paper"}:
            raise CommandRejected(f"unknown trading mode '{mode}'")
        control_db.set_setting("trading_mode", mode)
        return {"trading_mode": mode}

    # ---- mode enable/disable for the PAPER layer (scalp can never be enabled) ----
    if ctype in ("ENABLE_MODE", "DISABLE_MODE", "ENABLE_MODE_PAPER", "DISABLE_MODE_PAPER"):
        m = str(payload.get("mode", "")).strip()
        enable = ctype in ("ENABLE_MODE", "ENABLE_MODE_PAPER")
        if enable and m in LOCKED_MODES:
            raise CommandRejected(f"'{m}' is research/shadow-only and cannot be enabled")
        modes = dict(control_db.get_setting("allowed_modes") or {})
        if m not in modes:
            raise CommandRejected(f"unknown mode '{m}'")
        modes[m] = enable
        control_db.set_setting("allowed_modes", modes)
        return {"allowed_modes": modes}

    # ---- risk numerics (paper layer) ----
    if not s.enable_paper_commands:
        raise CommandRejected("paper commands disabled by server config")

    if ctype == "SET_RISK_PER_TRADE":
        v = _num(payload.get("value"))
        if not (0 < v <= 0.05):
            raise CommandRejected("risk_per_trade must be in (0, 0.05]")
        return _set("risk_per_trade", v)
    if ctype == "SET_PAPER_BALANCE":
        v = _num(payload.get("value"))
        if not (0 <= v <= 1_000_000):
            raise CommandRejected("paper_balance out of range")
        return _set("paper_balance", v)
    if ctype == "SET_LIVE_BALANCE":
        raise CommandRejected("live balance is locked in v1")
    if ctype == "SET_DAILY_LOSS_LIMIT":
        v = _num(payload.get("value"))
        if not (0 < v <= 0.5):
            raise CommandRejected("daily_loss_limit must be in (0, 0.5]")
        return _set("daily_loss_limit", v)
    if ctype == "SET_WEEKLY_LOSS_LIMIT":
        v = _num(payload.get("value"))
        if not (0 < v <= 0.8):
            raise CommandRejected("weekly_loss_limit must be in (0, 0.8]")
        return _set("weekly_loss_limit", v)
    if ctype == "SET_MAX_OPEN_POSITIONS":
        v = _num(payload.get("value"))
        if v != int(v) or not (1 <= v <= 50):
            raise CommandRejected("max_open_positions must be an integer in [1, 50]")
        return _set("max_positions", int(v))

    # ---- manual PAPER order ----
    if ctype == "MANUAL_PAPER_ORDER":
        return _manual_paper_order(payload, uid, cid)

    # ---- paper trade actions (real control-plane bookkeeping; never touches core engine) ----
    if ctype in ("CANCEL_PENDING_ORDER", "CANCEL_PENDING_PAPER", "CLOSE_PAPER_TRADE"):
        return _paper_trade_action(ctype, payload)

    raise CommandRejected(f"command '{ctype}' not implemented")


def _paper_trade_action(ctype, payload) -> dict:
    """Cancel a queued paper order or close a paper position — in the control DB only.

    Honest: this records the action against the control-plane manual_orders ledger; it does
    NOT execute anything in the crypto-ai-desk core engine (no such API in v1).
    """
    ref = payload.get("order_id") or payload.get("signal_id")
    if not ref:
        raise CommandRejected("order_id or signal_id required")
    order = control_db.find_manual_order(ref)
    if order is None:
        raise CommandRejected(f"no control-plane paper order found for '{ref}'")
    if (order.get("mode") or "") != "paper":
        raise CommandRejected("only paper orders can be modified from the control plane")
    cur = (order.get("status") or "").lower()
    target = "cancelled" if ctype in ("CANCEL_PENDING_ORDER", "CANCEL_PENDING_PAPER") else "closed"
    if cur == target:  # idempotent
        return {"ok": True, "order_id": order["order_id"], "status": cur, "idempotent": True}
    if target == "cancelled" and cur != "queued":
        raise CommandRejected(f"cannot cancel a '{cur}' order (only queued orders can be cancelled)")
    if target == "closed" and cur not in ("queued", "filled"):
        raise CommandRejected(f"cannot close a '{cur}' order")
    control_db.update_manual_order(order["order_id"], status=target)
    control_db.add_notification("info", f"Paper order {target}",
                                f"{order.get('symbol')} {order.get('direction') or ''}".strip(),
                                ref=order["order_id"])
    return {"ok": True, "order_id": order["order_id"], "status": target}


def _manual_paper_order(payload, uid, cid) -> dict:
    # paper-only + not paused
    if str(control_db.get_setting("trading_mode") or "paper").lower() != "paper":
        raise CommandRejected("manual orders are allowed only in paper mode")
    if control_db.get_setting("emergency_paused"):
        raise CommandRejected("engine is emergency-paused")
    symbol = payload.get("symbol")
    if not symbol:
        raise CommandRejected("symbol required")
    direction = str(payload.get("direction") or "").lower()
    if direction not in ("long", "short"):
        raise CommandRejected("direction must be 'long' or 'short'")

    # If linked to a signal, enforce actionability (no scalp/shadow/C-tier/late/sector-cap).
    sig = None
    sid = payload.get("signal_id")
    if sid:
        sig = desk_adapter.get_signal(sid)
        if sig is None:
            raise CommandRejected(f"signal {sid} not found")
        act = sig["actionability"]
        if not act["actionable"]:
            raise CommandRejected(f"signal not actionable: {act['blocked_reason']}")

    # every paper order needs a stop (signal-linked falls back to the signal's stop)
    stop = _opt(payload.get("stop"))
    if stop is None and sig is not None:
        stop = _opt(sig.get("stop_loss") or sig.get("invalidation"))
    if stop is None:
        raise CommandRejected("missing stop — a stop is required for every paper order")

    # per-trade risk
    risk = _num(payload.get("risk_pct", control_db.get_setting("risk_per_trade")))
    if not (0 < risk <= 0.05):
        raise CommandRejected("risk_pct must be in (0, 0.05]")

    # daily paper risk budget: committed risk today must stay within the daily loss cap
    cap = _num(control_db.get_setting("daily_loss_limit") or 0.03)
    used = control_db.paper_risk_used_today()
    if used + risk > cap + 1e-9:
        raise CommandRejected(
            f"daily paper risk budget exceeded ({used*100:.2f}% committed + {risk*100:.2f}% "
            f"> {cap*100:.2f}% cap)")

    # max open paper positions (explicit None check — 0 is a valid "no room" value)
    mp = control_db.get_setting("max_positions")
    max_pos = int(_num(mp if mp is not None else 5))
    if len(control_db.open_paper_orders()) >= max_pos:
        raise CommandRejected(f"max open paper positions reached ({max_pos})")

    max_loss = _opt(payload.get("max_loss"))
    if max_loss is not None and max_loss <= 0:
        raise CommandRejected("max_loss must be positive")

    def pick(key):
        v = _opt(payload.get(key))
        if v is None and sig is not None:
            v = _opt(sig.get(key))
        return v

    order = {
        "telegram_user_id": uid, "mode": "paper", "symbol": symbol,
        "direction": direction,
        "asset_class": payload.get("asset_class") or (sig.get("asset_class") if sig else None),
        "entry_type": payload.get("entry_type", "limit"),
        "entry_price": _opt(payload.get("entry_price"))
        or (_opt(sig.get("entry_trigger") or sig.get("entry_low")) if sig else None),
        "stop": stop, "tp1": pick("tp1"), "tp2": pick("tp2"), "tp3": pick("tp3"),
        "risk_pct": risk, "leverage": _num(payload.get("leverage", 1), 1),
        "max_loss": max_loss,
        "signal_id": sid, "notes": payload.get("notes"), "status": "queued", "command_id": cid,
    }
    oid = control_db.record_manual_order(order)
    control_db.add_notification("info", "Paper order queued",
                                f"{symbol} {direction} · risk {risk*100:.2f}%", ref=oid)
    return {"order_id": oid, "mode": "paper", "status": "queued"}


def _set(key, value) -> dict:
    old = control_db.get_setting(key)
    control_db.set_setting(key, value)
    return {"key": key, "old": old, "new": value}


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        if default is None:
            raise CommandRejected("numeric value required")
        return default


def _opt(v):
    """Optional numeric: None stays None; otherwise coerce to float (or None)."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
