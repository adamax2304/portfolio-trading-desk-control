"""Stocks Position Framework (SHADOW ONLY) — control-plane read-model + actionability tests."""
from __future__ import annotations

import os

# Isolate config BEFORE importing the app (mirror test_control_plane.py): demo mode, auth bypass,
# non-existent desk DB → endpoints return the empty shadow payload rather than erroring.
os.environ.setdefault("CONTROL_DB_PATH", os.path.join(os.path.dirname(__file__), "_test_control_sp.sqlite"))
os.environ.setdefault("DESK_DB_PATH", os.path.join(os.path.dirname(__file__), "_no_such_desk_sp.sqlite"))
os.environ["DEMO_MODE"] = "1"
os.environ["AUTH_DISABLED"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app import actionability, control_db  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()
control_db.init_db()
client = TestClient(app)


# ---------------------------------------------------------------- endpoints ---
def test_stocks_position_summary_shadow_only():
    r = client.get("/api/stocks-position/summary")
    assert r.status_code == 200
    d = r.json()
    assert d["shadow_only"] is True
    assert d["actionable"] is False
    assert d["live_locked"] is True
    assert d["playbook"] == "stocks_swing_growth_breakout"
    # demo/no-desk-DB → gracefully empty, never errors
    assert d["available"] is False
    assert d["open_candidates"] == 0
    assert d["top"] == []


def test_stocks_position_candidates_shadow_only():
    r = client.get("/api/stocks-position/candidates?limit=5")
    assert r.status_code == 200
    d = r.json()
    assert d["shadow_only"] is True
    assert d["actionable"] is False
    assert d["live_locked"] is True
    assert d["count"] == 0
    assert d["candidates"] == []


# ------------------------------------------------------------- actionability --
def test_actionability_stocks_swing_deprecated_removed():
    v = actionability.classify({"asset_class": "stocks", "mode": "swing", "tier": "A",
                                "status": "waiting_for_entry"})
    assert v["actionable"] is False
    assert v["blocked_reason"] == "mode_paused"           # key kept for compatibility
    joined = " ".join(v["reasons"]).lower()
    assert "deprecated/removed" in joined


def test_actionability_stocks_invest_deprecated_removed():
    v = actionability.classify({"asset_class": "stocks", "mode": "invest", "tier": "B",
                                "status": "waiting_for_entry"})
    assert v["actionable"] is False
    assert v["blocked_reason"] == "mode_paused"
    assert "deprecated/removed" in " ".join(v["reasons"]).lower()


# ---------------------------------------------- serialization + read-only ----
def _mk_desk_db(path):
    import sqlite3
    import json as _json
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE stocks_position_candidates (candidate_id TEXT, created_at TEXT, symbol TEXT, "
        "setup_variant TEXT, score REAL, data_confidence REAL, sector TEXT, sector_etf TEXT, "
        "entry_price REAL, entry_low REAL, entry_high REAL, stop_price REAL, stop_reason TEXT, "
        "risk_usd REAL, tp1 REAL, tp1_r REAL, tp2 REAL, tp2_r REAL, rs_spy REAL, near_high_pct REAL, "
        "volume_ratio REAL, market_regime TEXT, earnings_risk TEXT, thesis TEXT, counter_thesis TEXT, "
        "reasons_json TEXT, status TEXT)")
    conn.execute(
        "INSERT INTO stocks_position_candidates (candidate_id, created_at, symbol, setup_variant, "
        "score, sector, entry_price, stop_price, tp1, tp1_r, rs_spy, near_high_pct, status, "
        "reasons_json, thesis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("spf_AAPL_2026-07-02", "2026-07-02T12:00:00+00:00", "AAPL", "breakout", 82.0, "Technology",
         190.0, 182.0, 206.0, 2.0, 0.08, 3.2, "shadow_open",
         _json.dumps(["breakout setup, above 50D & 200D"]), "AAPL breakout thesis"))
    conn.commit()
    conn.close()


def test_candidates_serialization_and_read_only(tmp_path, monkeypatch):
    import sqlite3
    from app import stocks_position
    p = tmp_path / "desk.sqlite"
    _mk_desk_db(p)

    def _ro():
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(stocks_position, "_ro_conn", _ro)

    d = stocks_position.candidates(limit=5)
    assert d["available"] is True and d["shadow_only"] is True and d["actionable"] is False
    assert d["live_locked"] is True and d["count"] == 1
    row = d["candidates"][0]
    assert row["symbol"] == "AAPL" and row["setup_variant"] == "breakout" and row["score"] == 82.0
    assert row["tp1_r"] == 2.0 and row["sector"] == "Technology"
    assert row["reasons"] == ["breakout setup, above 50D & 200D"]        # JSON → list

    s = stocks_position.summary()
    assert s["available"] is True and s["open_candidates"] == 1 and len(s["top"]) == 1
    assert s["latest_scan"] == "2026-07-02T12:00:00+00:00"

    # read-only: our code must NEVER create proposed_signals / signal_outcomes
    conn = sqlite3.connect(str(p))
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "proposed_signals" not in names and "signal_outcomes" not in names


def test_terminal_outcome_excluded_from_open(tmp_path, monkeypatch):
    """A candidate with a terminal (closed/no_entry) outcome — or a flipped candidate status —
    must NOT appear in the open list / open_candidates count."""
    import sqlite3
    import json as _json
    from app import stocks_position
    p = tmp_path / "desk2.sqlite"
    conn = sqlite3.connect(str(p))
    conn.execute(
        "CREATE TABLE stocks_position_candidates (candidate_id TEXT, created_at TEXT, symbol TEXT, "
        "setup_variant TEXT, score REAL, sector TEXT, entry_price REAL, stop_price REAL, tp1 REAL, "
        "tp1_r REAL, status TEXT, reasons_json TEXT)")
    conn.execute("CREATE TABLE stocks_position_outcomes (candidate_id TEXT UNIQUE, status TEXT, net_pnl_usd REAL)")
    conn.executemany(
        "INSERT INTO stocks_position_candidates (candidate_id, created_at, symbol, setup_variant, "
        "score, sector, entry_price, stop_price, tp1, tp1_r, status, reasons_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [("spf_OPEN", "2026-07-02T12:00:00+00:00", "OPEN", "breakout", 80.0, "Technology",
          100.0, 95.0, 110.0, 2.0, "shadow_open", _json.dumps([])),
         ("spf_CLOSED", "2026-07-02T12:00:00+00:00", "CLOSEDX", "breakout", 80.0, "Technology",
          100.0, 95.0, 110.0, 2.0, "shadow_open", _json.dumps([])),   # open status but closed outcome
         ("spf_NOENT", "2026-07-01T12:00:00+00:00", "NOENT", "breakout", 80.0, "Technology",
          100.0, 95.0, 110.0, 2.0, "shadow_no_entry", _json.dumps([]))])  # flipped terminal status
    conn.execute("INSERT INTO stocks_position_outcomes (candidate_id, status, net_pnl_usd) VALUES (?,?,?)",
                 ("spf_CLOSED", "closed", 12.3))
    conn.commit()
    conn.close()

    def _ro():
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(stocks_position, "_ro_conn", _ro)
    d = stocks_position.candidates(limit=25)
    syms = [c["symbol"] for c in d["candidates"]]
    assert "OPEN" in syms
    assert "CLOSEDX" not in syms          # terminal outcome → excluded via LEFT JOIN
    assert "NOENT" not in syms            # flipped candidate status → excluded
    assert d["count"] == 1
    assert stocks_position.summary()["open_candidates"] == 1


def test_review_verdict_surfaced_in_candidates(tmp_path, monkeypatch):
    """The latest shadow review verdict/confidence/reviewed_at is joined into the candidate payload
    (read-only research annotation — never actionable)."""
    import sqlite3
    import json as _json
    from app import stocks_position
    p = tmp_path / "desk3.sqlite"
    conn = sqlite3.connect(str(p))
    conn.execute(
        "CREATE TABLE stocks_position_candidates (candidate_id TEXT, created_at TEXT, symbol TEXT, "
        "setup_variant TEXT, score REAL, sector TEXT, entry_price REAL, stop_price REAL, tp1 REAL, "
        "tp1_r REAL, status TEXT, reasons_json TEXT)")
    conn.execute(
        "CREATE TABLE stocks_position_reviews (candidate_id TEXT UNIQUE, reviewed_at TEXT, "
        "verdict TEXT, confidence REAL)")
    conn.execute(
        "INSERT INTO stocks_position_candidates (candidate_id, created_at, symbol, setup_variant, "
        "score, sector, entry_price, stop_price, tp1, tp1_r, status, reasons_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("spf_AAPL", "2026-07-02T12:00:00+00:00", "AAPL", "breakout", 80.0, "Technology",
         100.0, 95.0, 110.0, 2.0, "shadow_open", _json.dumps([])))
    conn.execute(
        "INSERT INTO stocks_position_reviews (candidate_id, reviewed_at, verdict, confidence) "
        "VALUES (?,?,?,?)", ("spf_AAPL", "2026-07-02T13:00:00+00:00", "wait_pullback", 0.6))
    conn.commit()
    conn.close()

    def _ro():
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(stocks_position, "_ro_conn", _ro)
    d = stocks_position.candidates(limit=5)
    row = d["candidates"][0]
    assert row["review_verdict"] == "wait_pullback"
    assert row["review_confidence"] == 0.6
    assert row["reviewed_at"] == "2026-07-02T13:00:00+00:00"
