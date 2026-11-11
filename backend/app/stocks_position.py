"""Read-only view over the crypto-ai-desk Stocks Position Framework shadow tables.

SHADOW ONLY. Reads `stocks_position_candidates` / `stocks_position_outcomes` from the desk SQLite
via the existing read-only connection. NEVER writes, NEVER mixes into the operator/paper actionable
book, NEVER exposes anything as a live/actionable recommendation. If the tables don't exist yet
(no scan run) it returns an empty shadow payload rather than erroring.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .desk_adapter import _ro_conn

PLAYBOOK = "stocks_swing_growth_breakout"
_NOTE = ("SHADOW ONLY — research candidates. Not actionable, not live, not sized, not in the "
         "operator/paper book. Authoritative profitability = USD net; outcomes may be pending.")


def _table_exists(conn, name: str) -> bool:
    try:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None
    except sqlite3.Error:
        return False


def _open_query(conn, select: str, tail: str = "") -> str:
    """SQL for genuinely OPEN candidates: status still `shadow_open` AND no terminal
    (closed / no_entry) outcome — so a resolved candidate never shows as open, even if its
    candidate.status was not flipped. LEFT JOINs (outcomes, reviews) only when those tables exist."""
    joins = ""
    where = "WHERE c.status = 'shadow_open' "
    if _table_exists(conn, "stocks_position_outcomes"):
        joins += "LEFT JOIN stocks_position_outcomes o ON o.candidate_id = c.candidate_id "
        where += "AND (o.status IS NULL OR o.status NOT IN ('closed','no_entry')) "
    if _table_exists(conn, "stocks_position_reviews"):
        joins += "LEFT JOIN stocks_position_reviews r ON r.candidate_id = c.candidate_id "
    return f"SELECT {select} FROM stocks_position_candidates c {joins}{where}{tail}"


def _row_select(conn) -> str:
    """Column list for candidate rows — includes the latest shadow REVIEW verdict when present."""
    if _table_exists(conn, "stocks_position_reviews"):
        return ("c.*, r.verdict AS review_verdict, r.confidence AS review_confidence, "
                "r.reviewed_at AS review_reviewed_at")
    return "c.*"


def _json(v):
    try:
        return json.loads(v) if v else []
    except (TypeError, ValueError):
        return []


def _base() -> dict[str, Any]:
    return {"shadow_only": True, "live_locked": True, "actionable": False,
            "playbook": PLAYBOOK, "note": _NOTE}


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    return {
        "symbol": d.get("symbol"), "setup_variant": d.get("setup_variant"),
        "score": d.get("score"), "data_confidence": d.get("data_confidence"),
        "sector": d.get("sector"), "sector_etf": d.get("sector_etf"),
        "entry_price": d.get("entry_price"), "entry_low": d.get("entry_low"),
        "entry_high": d.get("entry_high"), "stop_price": d.get("stop_price"),
        "stop_reason": d.get("stop_reason"), "risk_usd": d.get("risk_usd"),
        "tp1": d.get("tp1"), "tp1_r": d.get("tp1_r"), "tp2": d.get("tp2"), "tp2_r": d.get("tp2_r"),
        "rs_spy": d.get("rs_spy"), "near_high_pct": d.get("near_high_pct"),
        "volume_ratio": d.get("volume_ratio"), "market_regime": d.get("market_regime"),
        "earnings_risk": d.get("earnings_risk"), "created_at": d.get("created_at"),
        "status": d.get("status"), "reasons": _json(d.get("reasons_json")),
        "thesis": d.get("thesis"), "counter_thesis": d.get("counter_thesis"),
        # latest SHADOW review verdict (research annotation only — never actionable)
        "review_verdict": d.get("review_verdict"),
        "review_confidence": d.get("review_confidence"),
        "reviewed_at": d.get("review_reviewed_at"),
    }


def summary() -> dict[str, Any]:
    out = _base()
    out.update({"available": False, "latest_scan": None, "open_candidates": 0, "top": [],
                "outcomes_available": False})
    conn = _ro_conn()
    if conn is None:
        out["reason"] = "desk DB unavailable (demo/offline)"
        return out
    try:
        if not _table_exists(conn, "stocks_position_candidates"):
            out["reason"] = "no scan yet (stocks_position_candidates table absent)"
            return out
        out["available"] = True
        row = conn.execute(
            "SELECT MAX(created_at) AS t FROM stocks_position_candidates").fetchone()
        out["latest_scan"] = row["t"] if row else None
        out["open_candidates"] = conn.execute(_open_query(conn, "COUNT(*) AS c")).fetchone()["c"]
        top = conn.execute(
            _open_query(conn, _row_select(conn), "ORDER BY c.created_at DESC, c.score DESC LIMIT 5")).fetchall()
        out["top"] = [_row(r) for r in top]
        out["outcomes_available"] = _table_exists(conn, "stocks_position_outcomes")
        return out
    finally:
        conn.close()


def candidates(limit: int = 25) -> dict[str, Any]:
    out = _base()
    out.update({"available": False, "latest_scan": None, "count": 0, "candidates": []})
    conn = _ro_conn()
    if conn is None:
        out["reason"] = "desk DB unavailable (demo/offline)"
        return out
    try:
        if not _table_exists(conn, "stocks_position_candidates"):
            out["reason"] = "no scan yet (stocks_position_candidates table absent)"
            return out
        out["available"] = True
        row = conn.execute("SELECT MAX(created_at) AS t FROM stocks_position_candidates").fetchone()
        out["latest_scan"] = row["t"] if row else None
        rows = conn.execute(
            _open_query(conn, _row_select(conn), "ORDER BY c.created_at DESC, c.score DESC LIMIT ?"),
            (int(limit),)).fetchall()
        out["candidates"] = [_row(r) for r in rows]
        out["count"] = len(out["candidates"])
        return out
    finally:
        conn.close()
