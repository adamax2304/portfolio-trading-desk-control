"""Market dashboard read-model (PART 10) — reads `market_dashboard_snapshots` from the
desk DB read-only, with a stale-warning when the latest snapshot is older than 4–6h.
Writer is the crypto-ai-desk Opus routine (src/market/market_dashboard.py)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.portfolio import _ro_conn, _has_table, _parse

STALE_HOURS = 6.0
WARN_HOURS = 4.0


def _loads(v):
    if not v:
        return []
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return []


def latest_snapshot() -> dict:
    base = {"available": False, "live_locked": True, "auto_live_locked": True,
            "reason": "no market snapshot yet (Opus routine has not run)"}
    conn = _ro_conn()
    if conn is None:
        return base
    try:
        if not _has_table(conn, "market_dashboard_snapshots"):
            return base
        r = conn.execute("SELECT * FROM market_dashboard_snapshots ORDER BY id DESC LIMIT 1").fetchone()
        if not r:
            return base
        row = dict(r)
        ts = _parse(row.get("timestamp")) or _parse(row.get("created_at"))
        now = datetime.now(timezone.utc)
        age_h = ((now - ts).total_seconds() / 3600.0) if ts else None
        stale = bool(age_h is not None and age_h > STALE_HOURS)
        warn = bool(age_h is not None and age_h > WARN_HOURS)
        return {
            "available": True, "live_locked": True, "auto_live_locked": True,
            "timestamp": row.get("timestamp"), "age_hours": round(age_h, 1) if age_h is not None else None,
            "stale": stale, "stale_warning": warn,
            "generated_by": row.get("generated_by"), "confidence": row.get("confidence"),
            "source_summary": row.get("source_summary"),
            "crypto_fear_greed": row.get("crypto_fear_greed"),
            "crypto_market_mode": row.get("crypto_market_mode"),
            "stocks_market_mode": row.get("stocks_market_mode"),
            "crypto_main_risk": row.get("crypto_main_risk"),
            "stocks_main_risk": row.get("stocks_main_risk"),
            "crypto_regime": row.get("crypto_regime"),
            "stocks_regime": row.get("stocks_regime"),
            "today_news": _loads(row.get("today_news")),
            "long_term_news": _loads(row.get("long_term_news")),
            "extras": {
                "btc_dominance": row.get("btc_dominance"), "eth_btc": row.get("eth_btc"),
                "vix": row.get("vix"), "spy_trend": row.get("spy_trend"), "qqq_trend": row.get("qqq_trend"),
            },
            "note": ("Market dashboard is written by the Opus enriched-review routine (~4h). "
                     "Stale if older than 6h — the enriched review body itself is unchanged."),
        }
    finally:
        conn.close()
