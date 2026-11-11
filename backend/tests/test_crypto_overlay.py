"""Crypto Quality Overlay (READ-ONLY diagnostics) — control-plane read-model tests.

The overlay is a soft PAPER sizing/routing breaker; this card only surfaces it. Tests assert:
fail-open (no desk DB) shape + live_locked/actionable invariants, the module is read-only (no
INSERT/UPDATE/DELETE/DROP), faithful serialization of the three desk tables, the active +
non-expired cooldown filter, worst-first symbol ordering, the counterfactual window math (must
match the desk's `_summary`), and the per-signal overlay-changed-action/size derivation.
"""
from __future__ import annotations

import os
from pathlib import Path

# Isolate config BEFORE importing the app (mirror test_stocks_position.py): demo mode, auth bypass,
# non-existent desk DB → endpoints return the empty fail-open payload rather than erroring.
os.environ.setdefault("CONTROL_DB_PATH", os.path.join(os.path.dirname(__file__), "_test_control_cqo.sqlite"))
os.environ.setdefault("DESK_DB_PATH", os.path.join(os.path.dirname(__file__), "_no_such_desk_cqo.sqlite"))
os.environ["DEMO_MODE"] = "1"
os.environ["AUTH_DISABLED"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app import control_db, crypto_overlay  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()
control_db.init_db()
client = TestClient(app)


# ---------------------------------------------------------------- endpoints ---
def test_report_fail_open_shape_and_invariants():
    r = client.get("/api/crypto-overlay/report")
    assert r.status_code == 200
    d = r.json()
    # read-only / live-locked / not-actionable invariants hold regardless of data availability
    assert d["read_only"] is True and d["live_locked"] is True and d["actionable"] is False
    # demo / no desk DB → gracefully empty, never errors
    assert d["available"] is False and "reason" in d
    assert d["action_mix"] == {"FULL_SIZE": 0, "HALF_SIZE": 0, "SHADOW_ONLY": 0, "BLOCK": 0}
    assert d["top_reasons"] == [] and d["worst_symbols"] == []
    assert d["active_session_cooldowns"] == [] and d["active_symbol_cooldowns"] == []


def test_signal_fail_open_shape():
    r = client.get("/api/crypto-overlay/signal/whatever")
    assert r.status_code == 200
    d = r.json()
    assert d["read_only"] is True and d["live_locked"] is True and d["actionable"] is False
    assert d["available"] is False and d["signal_id"] == "whatever" and "reason" in d


def test_module_is_read_only():
    src = Path(crypto_overlay.__file__).read_text(encoding="utf-8").upper()
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE", "CREATE TABLE"):
        assert verb not in src


# --------------------------------------------------- serialization + math -----
def _mk_desk_db(path):
    """Synthetic desk DB with the three overlay read-model tables + deterministic rows."""
    import sqlite3
    import json as _json
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE crypto_quality_overlay_decisions (signal_id TEXT PRIMARY KEY, quality_action TEXT, "
        "quality_reasons_json TEXT, would_have_been_action_without_overlay TEXT, overlay_version TEXT, "
        "computed_at TEXT, crypto_quality_verdict TEXT, crypto_quality_score REAL, btc_regime_state TEXT, "
        "eth_confirm_state TEXT, session_bucket_utc TEXT, session_quality_state TEXT, "
        "symbol_cooldown_state TEXT, mode_session_cooldown_state TEXT)")
    conn.executemany(
        "INSERT INTO crypto_quality_overlay_decisions (signal_id, quality_action, quality_reasons_json, "
        "would_have_been_action_without_overlay, overlay_version, computed_at, crypto_quality_verdict, "
        "crypto_quality_score, btc_regime_state, eth_confirm_state, session_bucket_utc, "
        "session_quality_state, symbol_cooldown_state, mode_session_cooldown_state) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [("sig_full1", "FULL_SIZE", _json.dumps([]), "FULL_SIZE", "cqo_v1", "2026-07-07T10:00:00+00:00",
          "OK", 78.0, "trend", "up", "US", "ok", "clear", "clear"),
         ("sig_full2", "FULL_SIZE", _json.dumps([]), "FULL_SIZE", "cqo_v1", "2026-07-07T11:00:00+00:00",
          "OK", 71.0, "range", "flat", "EU", "ok", "clear", "clear"),
         ("sig_half", "HALF_SIZE", _json.dumps(["btc_direction_conflict", "symbol_cooldown[2_original_stops]"]),
          "FULL_SIZE", "cqo_v1", "2026-07-07T12:00:00+00:00", "WEAK", 52.0, "down", "transition_down",
          "US", "weak", "on_cooldown", "clear"),
         ("sig_shadow", "SHADOW_ONLY", _json.dumps(["btc_direction_conflict", "scalp_disabled_shadow_only"]),
          "HALF_SIZE", "cqo_v1", "2026-07-07T13:00:00+00:00", "WEAK", 44.0, "down", "down",
          "ASIA", "weak", "on_cooldown", "on_cooldown")])
    conn.execute(
        "CREATE TABLE crypto_quality_cooldowns (cooldown_type TEXT, affected_mode TEXT, "
        "affected_session_bucket TEXT, affected_symbol TEXT, cooldown_active INTEGER, cooldown_reason TEXT, "
        "cooldown_started_at TEXT, cooldown_expires_at TEXT, recent_closed_count INTEGER, "
        "recent_original_stop_count INTEGER, recent_net_pnl_usd REAL, recent_profit_factor REAL)")
    conn.executemany(
        "INSERT INTO crypto_quality_cooldowns (cooldown_type, affected_mode, affected_session_bucket, "
        "affected_symbol, cooldown_active, cooldown_reason, cooldown_expires_at, recent_closed_count, "
        "recent_original_stop_count, recent_net_pnl_usd, recent_profit_factor) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [("session", "intraday", "US", None, 1, "session_3_stops", None, 8, 3, -50.0, 0.4),
         ("symbol", "swing", None, "BTC/USDT", 1, "2_original_stops", None, 10, 6, -250.0, 0.3),
         ("symbol", "intraday", None, "MEGA/USDT", 1, "2_original_stops", None, 6, 4, -112.0, 0.5),
         # active flag set but TTL already elapsed → must be treated as inactive
         ("symbol", "intraday", None, "OLD/USDT", 1, "expired", "2000-01-01T00:00:00+00:00", 3, 2, -10.0, 0.6),
         # not active → excluded by the WHERE cooldown_active=1
         ("symbol", "intraday", None, "OFF/USDT", 0, "cleared", None, 2, 0, 5.0, 1.2)])
    conn.execute(
        "CREATE TABLE crypto_quality_counterfactual (signal_id TEXT PRIMARY KEY, created_at TEXT, "
        "close_reason TEXT, overlay_action TEXT, baseline_pnl_usd REAL, overlay_simulated_pnl_usd REAL, "
        "avoided_loss_usd REAL, missed_profit_usd REAL)")
    conn.executemany(
        "INSERT INTO crypto_quality_counterfactual (signal_id, created_at, close_reason, overlay_action, "
        "baseline_pnl_usd, overlay_simulated_pnl_usd, avoided_loss_usd, missed_profit_usd) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [("cf_a", "2026-07-07T12:00:00+00:00", "original_stop", "SHADOW_ONLY", -100.0, 0.0, 100.0, 0.0),
         ("cf_b", "2026-07-07T12:00:00+00:00", "tp3_runner", "FULL_SIZE", 200.0, 200.0, 0.0, 0.0),
         ("cf_c", "2026-07-07T12:00:00+00:00", "tp3_runner", "SHADOW_ONLY", 150.0, 0.0, 0.0, 150.0),
         ("cf_d", "2026-07-07T12:00:00+00:00", "original_stop", "HALF_SIZE", -80.0, -40.0, 40.0, 0.0)])
    conn.commit()
    conn.close()


def _patch_ro(monkeypatch, path):
    import sqlite3

    def _ro():
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(crypto_overlay, "_ro_conn", _ro)


def test_report_serialization(tmp_path, monkeypatch):
    p = tmp_path / "desk.sqlite"
    _mk_desk_db(p)
    _patch_ro(monkeypatch, p)

    d = crypto_overlay.overlay_report()
    assert d["available"] is True and d["read_only"] is True and d["actionable"] is False
    assert d["overlay_version"] == "cqo_v1"

    # decision mix — all four canonical keys present, 0-filled
    assert d["action_mix"] == {"FULL_SIZE": 2, "HALF_SIZE": 1, "SHADOW_ONLY": 1, "BLOCK": 0}

    # top reasons — individual reasons exploded + counted across the non-FULL decisions
    reasons = {r["reason"]: r["count"] for r in d["top_reasons"]}
    assert reasons["btc_direction_conflict"] == 2
    assert reasons["scalp_disabled_shadow_only"] == 1
    assert reasons["symbol_cooldown[2_original_stops]"] == 1
    assert d["top_reasons"][0]["reason"] == "btc_direction_conflict"  # most frequent first

    # active session cooldowns (current weak sessions)
    assert len(d["active_session_cooldowns"]) == 1
    assert d["active_session_cooldowns"][0]["mode"] == "intraday"
    assert d["active_session_cooldowns"][0]["session_bucket"] == "US"

    # active symbol cooldowns: BTC + MEGA only (expired OLD excluded, inactive OFF excluded)
    syms = [c["symbol"] for c in d["active_symbol_cooldowns"]]
    assert syms == ["BTC/USDT", "MEGA/USDT"]          # sorted worst (most negative USD) first
    assert "OLD/USDT" not in syms and "OFF/USDT" not in syms
    assert d["worst_symbols"][0]["symbol"] == "BTC/USDT"
    assert d["worst_symbols"][0]["recent_original_stop_count"] == 6


def test_counterfactual_window_math(tmp_path, monkeypatch):
    p = tmp_path / "desk2.sqlite"
    _mk_desk_db(p)
    _patch_ro(monkeypatch, p)

    s = crypto_overlay.overlay_report()["counterfactual"]["all"]
    assert s["evaluated"] == 4 and s["with_usd"] == 4
    assert s["baseline_pnl_usd"] == 170.0 and s["overlay_pnl_usd"] == 160.0
    assert s["net_overlay_delta_usd"] == -10.0
    assert s["avoided_loss_usd"] == 140.0 and s["missed_profit_usd"] == 150.0
    assert s["baseline_pf"] == round(350 / 180, 3) and s["overlay_pf"] == 5.0
    assert s["baseline_original_stops"] == 2 and s["overlay_original_stops_kept"] == 1
    assert s["original_stop_reduction"] == 1
    assert s["missed_tp3_runners"] == 1 and s["total_tp3_runners"] == 2   # a runner WAS killed → visible
    assert s["missed_winners"] == 1 and s["kept_full_size"] == 1
    assert s["trade_count_delta"] == -2


def test_signal_decision_overlay_changed(tmp_path, monkeypatch):
    p = tmp_path / "desk3.sqlite"
    _mk_desk_db(p)
    _patch_ro(monkeypatch, p)

    # HALF over a would-be FULL → action + size both changed (1.0 → 0.5)
    d = crypto_overlay.signal_decision("sig_half")
    assert d["available"] is True and d["read_only"] is True and d["actionable"] is False
    assert d["quality_action"] == "HALF_SIZE"
    assert d["would_have_been_action_without_overlay"] == "FULL_SIZE"
    assert d["overlay_changed_action"] is True and d["overlay_changed_size"] is True
    assert d["crypto_quality_verdict"] == "WEAK" and d["crypto_quality_score"] == 52.0
    assert d["quality_reasons"] == ["btc_direction_conflict", "symbol_cooldown[2_original_stops]"]
    assert d["symbol_cooldown_state"] == "on_cooldown" and d["btc_regime_state"] == "down"

    # FULL over a would-be FULL → nothing changed
    f = crypto_overlay.signal_decision("sig_full1")
    assert f["available"] is True
    assert f["overlay_changed_action"] is False and f["overlay_changed_size"] is False

    # SHADOW over would-be HALF → action changed AND size changed (0.5 → 0.0)
    sh = crypto_overlay.signal_decision("sig_shadow")
    assert sh["overlay_changed_action"] is True and sh["overlay_changed_size"] is True

    # unknown signal → fail-open, not an error
    miss = crypto_overlay.signal_decision("nope")
    assert miss["available"] is False and "reason" in miss


def test_report_read_only_never_writes(tmp_path, monkeypatch):
    """After building the report, the desk DB must be byte-for-byte unchanged (no refresh/write)."""
    import hashlib
    p = tmp_path / "desk4.sqlite"
    _mk_desk_db(p)
    before = hashlib.sha256(p.read_bytes()).hexdigest()
    _patch_ro(monkeypatch, p)
    crypto_overlay.overlay_report()
    crypto_overlay.signal_decision("sig_half")
    after = hashlib.sha256(p.read_bytes()).hexdigest()
    assert before == after
