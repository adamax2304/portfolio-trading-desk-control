"""Read-only view over the crypto-ai-desk Crypto Quality Overlay read-model tables.

READ-ONLY / DIAGNOSTIC. The overlay is a soft PAPER sizing/routing breaker that runs after signal
generation (FULL_SIZE / HALF_SIZE / SHADOW_ONLY / BLOCK). This module NEVER writes, NEVER triggers a
trade, NEVER changes config or unlocks live — it only surfaces what the desk already computed.

Reads three additive desk tables via the existing read-only connection:
  - `crypto_quality_overlay_decisions`   — per-signal action / verdict / reasons / cooldown state
  - `crypto_quality_cooldowns`           — active session + per-symbol cooldowns
  - `crypto_quality_counterfactual`      — baseline-full-size vs overlay per closed paper trade

The card summary mirrors `crypto_quality_overlay.report_data()` on the desk (decision mix, active
cooldowns, worst symbols, weak sessions, avoided-loss vs missed-profit windows), but recomputes the
counterfactual windows purely from the STORED table so no desk refresh/write is triggered. If the
tables don't exist yet (overlay never refreshed) it returns an empty, fail-open payload.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from .desk_adapter import _ro_conn

VERSION = "cqo_v1"  # mirrors src.execution.crypto_quality_overlay.VERSION (display fallback only)
_ACTIONS = ("FULL_SIZE", "HALF_SIZE", "SHADOW_ONLY", "BLOCK")
# Size multiplier per overlay action — identical to the desk counterfactual `_SIZE` map so the
# avoided-loss / missed-profit windows reproduce the desk numbers exactly.
_SIZE = {"FULL_SIZE": 1.0, "HALF_SIZE": 0.5, "SHADOW_ONLY": 0.0, "BLOCK": 0.0}

_NOTE = ("READ-ONLY diagnostic. Soft PAPER sizing/routing breaker — only ever downgrades, never "
         "upgrades. Live LOCKED; signal generation / tier / score / final_r untouched. Never triggers "
         "a trade or config change.")


def _base() -> dict[str, Any]:
    return {"read_only": True, "live_locked": True, "actionable": False,
            "overlay_version": VERSION, "note": _NOTE}


def _has(conn: sqlite3.Connection, name: str) -> bool:
    try:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None
    except sqlite3.Error:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts) -> datetime | None:
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- decision mix / reasons ---
def _action_mix(conn: sqlite3.Connection) -> dict[str, int]:
    """FULL/HALF/SHADOW/BLOCK counts — always includes all four keys (0-filled)."""
    mix = {a: 0 for a in _ACTIONS}
    for action, n in conn.execute(
        "SELECT quality_action, COUNT(*) FROM crypto_quality_overlay_decisions "
        "GROUP BY quality_action"
    ).fetchall():
        if action:
            mix[action] = int(n or 0)  # keep unknown actions too, but the 4 canonical are pre-seeded
    return mix


def _top_reasons(conn: sqlite3.Connection, limit: int = 8) -> list[dict[str, Any]]:
    """Why signals were reduced/shadowed — individual reason strings aggregated across every
    non-FULL decision (explodes quality_reasons_json arrays), most frequent first."""
    counts: dict[str, int] = {}
    for (reasons_json,) in conn.execute(
        "SELECT quality_reasons_json FROM crypto_quality_overlay_decisions "
        "WHERE quality_action != 'FULL_SIZE'"
    ).fetchall():
        try:
            reasons = json.loads(reasons_json) if reasons_json else []
        except (TypeError, ValueError):
            reasons = []
        for r in reasons:
            if r:
                counts[str(r)] = counts.get(str(r), 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"reason": r, "count": c} for r, c in top]


# ---------------------------------------------------------------------------- cooldowns ---
def _active_cooldowns(conn: sqlite3.Connection, now: datetime) -> tuple[list, list]:
    """Return (session_cooldowns, symbol_cooldowns) that are active and not TTL-expired.
    Mirrors crypto_quality_overlay.read_cooldowns()'s active + non-expired filter."""
    sessions: list[dict[str, Any]] = []
    symbols: list[dict[str, Any]] = []
    rows = conn.execute(
        "SELECT cooldown_type, affected_mode, affected_session_bucket, affected_symbol, "
        "cooldown_reason, cooldown_expires_at, recent_closed_count, recent_original_stop_count, "
        "recent_net_pnl_usd, recent_profit_factor FROM crypto_quality_cooldowns "
        "WHERE cooldown_active=1"
    ).fetchall()
    for r in rows:
        d = dict(r)
        exp = _parse(d.get("cooldown_expires_at"))
        if exp is not None and now > exp:
            continue  # TTL elapsed → treat as inactive
        common = {
            "mode": d.get("affected_mode"),
            "reason": d.get("cooldown_reason"),
            "expires_at": d.get("cooldown_expires_at"),
            "recent_closed_count": d.get("recent_closed_count"),
            "recent_original_stop_count": d.get("recent_original_stop_count"),
            "recent_net_pnl_usd": d.get("recent_net_pnl_usd"),
            "recent_profit_factor": d.get("recent_profit_factor"),
        }
        if d.get("cooldown_type") == "session":
            sessions.append({**common, "session_bucket": d.get("affected_session_bucket")})
        else:
            symbols.append({**common, "symbol": d.get("affected_symbol")})
    # Worst first (most negative recent paper USD) so the UI can lead with the biggest bleeders.
    symbols.sort(key=lambda x: (x.get("recent_net_pnl_usd") if x.get("recent_net_pnl_usd") is not None else 0.0))
    sessions.sort(key=lambda x: (x.get("recent_net_pnl_usd") if x.get("recent_net_pnl_usd") is not None else 0.0))
    return sessions, symbols


# ------------------------------------------------------------------------ counterfactual ---
def _pf(vals: list[float | None]) -> float | None:
    # Profit factor = gross gains / gross losses. Undefined (no losses / no data) → None: an
    # infinite PF is not JSON-serializable and would read as a fake finite number in the UI.
    g = sum(v for v in vals if v and v > 0)
    l = -sum(v for v in vals if v and v < 0)
    return round(g / l, 3) if l > 0 else None


def _summary(rows: list[dict[str, Any]], now: datetime, window_days: int | None) -> dict[str, Any]:
    """Reproduces crypto_overlay_counterfactual._summary() from stored per-trade rows (read-only)."""
    if window_days is not None:
        cut = now - timedelta(days=window_days)
        rows = [r for r in rows if (r["t"] or now) >= cut]
    have = [r for r in rows if r["base_usd"] is not None]
    base = [r["base_usd"] for r in have]
    over = [r["over_usd"] for r in have]
    base_stops = sum(1 for r in have if r["close"] == "original_stop")
    over_stops = sum(1 for r in have if r["close"] == "original_stop" and _SIZE.get(r["overlay_action"], 1.0) > 0)
    missed_runners = sum(1 for r in have if r["close"] == "tp3_runner" and _SIZE.get(r["overlay_action"], 1.0) == 0)
    total_runners = sum(1 for r in have if r["close"] == "tp3_runner")
    missed_winners = sum(1 for r in have if (r["base_usd"] or 0) > 0 and _SIZE.get(r["overlay_action"], 1.0) == 0)
    kept_full = sum(1 for r in have if r["overlay_action"] == "FULL_SIZE")
    return {
        "evaluated": len(rows), "with_usd": len(have),
        "baseline_pnl_usd": round(sum(v for v in base if v is not None), 2),
        "overlay_pnl_usd": round(sum(v for v in over if v is not None), 2),
        "net_overlay_delta_usd": round(sum(v for v in over if v is not None)
                                       - sum(v for v in base if v is not None), 2),
        "avoided_loss_usd": round(sum(r["avoided"] for r in have), 2),
        "missed_profit_usd": round(sum(r["missed"] for r in have), 2),
        "baseline_pf": _pf(base), "overlay_pf": _pf(over),
        "baseline_original_stops": base_stops, "overlay_original_stops_kept": over_stops,
        "original_stop_reduction": base_stops - over_stops,
        "missed_tp3_runners": missed_runners, "total_tp3_runners": total_runners,
        "missed_winners": missed_winners, "kept_full_size": kept_full,
        "trade_count_delta": -sum(1 for r in have if _SIZE.get(r["overlay_action"], 1.0) == 0),
    }


def _counterfactual(conn: sqlite3.Connection, now: datetime) -> dict[str, Any]:
    """d2/d7/d14/all avoided-loss vs missed-profit windows, computed from the STORED
    crypto_quality_counterfactual table (no desk refresh / write)."""
    rows: list[dict[str, Any]] = []
    for r in conn.execute(
        "SELECT created_at, close_reason, overlay_action, baseline_pnl_usd, "
        "overlay_simulated_pnl_usd, avoided_loss_usd, missed_profit_usd FROM crypto_quality_counterfactual"
    ).fetchall():
        d = dict(r)
        rows.append({
            "t": _parse(d.get("created_at")), "close": d.get("close_reason"),
            "overlay_action": d.get("overlay_action"),
            "base_usd": d.get("baseline_pnl_usd"), "over_usd": d.get("overlay_simulated_pnl_usd"),
            "avoided": d.get("avoided_loss_usd") or 0.0, "missed": d.get("missed_profit_usd") or 0.0,
        })
    return {"d2": _summary(rows, now, 2), "d7": _summary(rows, now, 7),
            "d14": _summary(rows, now, 14), "all": _summary(rows, now, None)}


# ------------------------------------------------------------------------------- public ---
def overlay_report() -> dict[str, Any]:
    """Read-only Crypto Quality Overlay summary for the control-plane diagnostics card."""
    out = _base()
    out.update({"available": False, "generated_at": _now().isoformat(),
                "action_mix": {a: 0 for a in _ACTIONS}, "top_reasons": [],
                "active_session_cooldowns": [], "active_symbol_cooldowns": [],
                "worst_symbols": [], "counterfactual": {}})
    conn = _ro_conn()
    if conn is None:
        out["reason"] = "desk DB unavailable (demo/offline)"
        return out
    try:
        now = _now()
        has_decisions = _has(conn, "crypto_quality_overlay_decisions")
        has_cooldowns = _has(conn, "crypto_quality_cooldowns")
        if not has_decisions and not has_cooldowns:
            out["reason"] = "overlay not refreshed yet — run `crypto-overlay-report` on the desk"
            return out
        out["available"] = True
        if has_decisions:
            out["action_mix"] = _action_mix(conn)
            out["top_reasons"] = _top_reasons(conn)
            # latest overlay_version stamped on a decision (falls back to module constant)
            row = conn.execute(
                "SELECT overlay_version FROM crypto_quality_overlay_decisions "
                "WHERE overlay_version IS NOT NULL ORDER BY computed_at DESC LIMIT 1").fetchone()
            if row and row[0]:
                out["overlay_version"] = row[0]
        if has_cooldowns:
            sessions, symbols = _active_cooldowns(conn, now)
            out["active_session_cooldowns"] = sessions      # current weak sessions
            out["active_symbol_cooldowns"] = symbols
            out["worst_symbols"] = symbols[:8]              # already sorted worst-first
        if _has(conn, "crypto_quality_counterfactual"):
            out["counterfactual"] = _counterfactual(conn, now)
        return out
    except sqlite3.Error as e:
        out["available"] = False
        out["reason"] = f"desk schema mismatch: {e}"
        return out
    finally:
        conn.close()


def _changed(action: str | None, would: str | None) -> dict[str, bool]:
    """Did the overlay change the action / effective size vs the no-overlay baseline?"""
    if not action or not would:
        return {"overlay_changed_action": False, "overlay_changed_size": False}
    return {
        "overlay_changed_action": action != would,
        "overlay_changed_size": _SIZE.get(action, 1.0) != _SIZE.get(would, 1.0),
    }


def signal_decision(signal_id: str) -> dict[str, Any]:
    """Authoritative per-signal overlay decision from crypto_quality_overlay_decisions.
    Surfaces quality_action, verdict, score, reasons, cooldown state, BTC regime, session bucket,
    and whether the overlay changed the action/size (vs would_have_been_action_without_overlay)."""
    out = _base()
    out.update({"available": False, "signal_id": signal_id})
    conn = _ro_conn()
    if conn is None:
        out["reason"] = "desk DB unavailable (demo/offline)"
        return out
    try:
        if not _has(conn, "crypto_quality_overlay_decisions"):
            out["reason"] = "overlay not refreshed yet"
            return out
        r = conn.execute(
            "SELECT * FROM crypto_quality_overlay_decisions WHERE signal_id=?", (signal_id,)).fetchone()
        if not r:
            out["reason"] = "no overlay decision recorded for this signal"
            return out
        d = dict(r)
        action = d.get("quality_action")
        would = d.get("would_have_been_action_without_overlay")
        try:
            reasons = json.loads(d.get("quality_reasons_json")) if d.get("quality_reasons_json") else []
        except (TypeError, ValueError):
            reasons = []
        out.update({
            "available": True,
            "quality_action": action,
            "would_have_been_action_without_overlay": would,
            "crypto_quality_verdict": d.get("crypto_quality_verdict"),
            "crypto_quality_score": d.get("crypto_quality_score"),
            "quality_reasons": reasons,
            "btc_regime_state": d.get("btc_regime_state"),
            "eth_confirm_state": d.get("eth_confirm_state"),
            "session_bucket_utc": d.get("session_bucket_utc"),
            "session_quality_state": d.get("session_quality_state"),
            "symbol_cooldown_state": d.get("symbol_cooldown_state"),
            "mode_session_cooldown_state": d.get("mode_session_cooldown_state"),
            "overlay_version": d.get("overlay_version") or VERSION,
            "computed_at": d.get("computed_at"),
        })
        out.update(_changed(action, would))
        return out
    except sqlite3.Error as e:
        out["reason"] = f"desk schema mismatch: {e}"
        return out
    finally:
        conn.close()
