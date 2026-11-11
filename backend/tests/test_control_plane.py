"""Backend safety + auth tests for the control plane."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

import pytest

# Isolate config BEFORE importing the app: tmp control DB, demo mode, auth bypass for
# endpoint tests (auth itself is tested directly against verify_init_data).
os.environ["CONTROL_DB_PATH"] = os.path.join(os.path.dirname(__file__), "_test_control.sqlite")
os.environ["DESK_DB_PATH"] = os.path.join(os.path.dirname(__file__), "_no_such_desk.sqlite")
os.environ["DEMO_MODE"] = "1"
os.environ["AUTH_DISABLED"] = "1"

if os.path.exists(os.environ["CONTROL_DB_PATH"]):
    os.remove(os.environ["CONTROL_DB_PATH"])

from fastapi.testclient import TestClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app import telegram_auth, control_db, commands  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()
control_db.init_db()
client = TestClient(app)


# ---------------------------------------------------------------- auth ------
def _build_init_data(bot_token: str, user: dict, auth_date: int | None = None) -> str:
    auth_date = auth_date or int(time.time())
    pairs = {"auth_date": str(auth_date), "user": json.dumps(user)}
    dcs = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    pairs["hash"] = h
    return urlencode(pairs)


def test_auth_valid_initdata_passes(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "555")
    get_settings.cache_clear()
    init = _build_init_data("123:ABC", {"id": 555, "username": "owner"})
    user = telegram_auth.verify_init_data(init)
    assert user["id"] == 555
    get_settings.cache_clear()


def test_auth_bad_hash_rejected(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    get_settings.cache_clear()
    with pytest.raises(telegram_auth.AuthError):
        telegram_auth.verify_init_data("user=%7B%22id%22%3A1%7D&auth_date=1&hash=deadbeef")
    get_settings.cache_clear()


def test_auth_unauthorized_user_rejected(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "555")
    get_settings.cache_clear()
    init = _build_init_data("123:ABC", {"id": 999, "username": "intruder"})
    with pytest.raises(telegram_auth.AuthError):
        telegram_auth.verify_init_data(init)
    get_settings.cache_clear()


def test_endpoint_blocks_missing_auth(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    get_settings.cache_clear()
    r = client.get("/api/status")  # no initData header
    assert r.status_code == 401
    get_settings.cache_clear()


# ------------------------------------------------------- read-only safety ---
def test_status_and_signals_read_only():
    assert client.get("/api/status").status_code == 200
    sigs = client.get("/api/signals").json()["signals"]
    assert len(sigs) > 0
    # read endpoints must not create commands/audit rows
    before = len(control_db.recent_commands(1000))
    client.get("/api/signals"); client.get("/api/trades/open"); client.get("/api/closed/operator/analytics"); client.get("/api/system/health")
    assert len(control_db.recent_commands(1000)) == before


def test_shadow_signal_not_actionable():
    sigs = client.get("/api/signals").json()["signals"]
    scalp = [s for s in sigs if s["mode"] == "scalp"]
    assert scalp and all(not s["actionability"]["actionable"] for s in scalp)
    assert all(s["actionability"]["status"] == "shadow" for s in scalp)


# -------------------------------------------------------- command safety ----
def test_unknown_command_rejected():
    r = client.post("/api/command", json={"type": "DROP_TABLES", "confirm_token": "x"}).json()
    assert r["status"] == "rejected"


def test_command_requires_confirm_token():
    r = client.post("/api/command", json={"type": "SET_RISK_PER_TRADE", "payload": {"value": 0.01}})
    assert r.status_code == 400


def test_risk_out_of_range_rejected():
    r = client.post("/api/command", json={"type": "SET_RISK_PER_TRADE",
                                          "payload": {"value": 0.5}, "confirm_token": "ok"}).json()
    assert r["status"] == "rejected"


def test_risk_in_range_applied():
    r = client.post("/api/command", json={"type": "SET_RISK_PER_TRADE",
                                          "payload": {"value": 0.01}, "confirm_token": "ok"}).json()
    assert r["status"] == "applied"
    assert control_db.get_setting("risk_per_trade") == 0.01


def test_crypto_scalp_cannot_be_enabled():
    r = client.post("/api/command", json={"type": "ENABLE_MODE",
                                          "payload": {"mode": "crypto_scalp"}, "confirm_token": "ok"}).json()
    assert r["status"] == "rejected"
    assert control_db.get_setting("allowed_modes")["crypto_scalp"] is False


def test_stocks_scalp_cannot_be_enabled():
    r = client.post("/api/command", json={"type": "ENABLE_MODE",
                                          "payload": {"mode": "stocks_scalp"}, "confirm_token": "ok"}).json()
    assert r["status"] == "rejected"


def test_manual_live_order_locked():
    r = client.post("/api/command", json={"type": "MANUAL_LIVE_ORDER",
                                          "payload": {"symbol": "BTC/USDT"}, "confirm_token": "ok"}).json()
    assert r["status"] == "rejected"
    assert "lock" in (r["error"] or "").lower()


def test_set_mode_live_locked():
    for m in ("manual_live", "auto_live"):
        r = client.post("/api/command", json={"type": "SET_MODE",
                                              "payload": {"mode": m}, "confirm_token": "ok"}).json()
        assert r["status"] == "rejected"


def test_emergency_pause_creates_command_and_flag():
    r = client.post("/api/emergency-pause").json()
    assert r["status"] == "applied"
    assert control_db.get_setting("emergency_paused") is True
    # it is a flag/command, not a destructive process action
    assert "no process killed" in json.dumps(r["result_json"])
    control_db.set_setting("emergency_paused", False)


def test_manual_paper_order_on_shadow_signal_rejected():
    # demo has a scalp (shadow) signal demo_rif
    r = client.post("/api/command", json={"type": "MANUAL_PAPER_ORDER",
                                          "payload": {"symbol": "RIF/USDT", "signal_id": "demo_rif",
                                                      "direction": "long", "risk_pct": 0.01},
                                          "confirm_token": "ok"}).json()
    assert r["status"] == "rejected"
    assert "not actionable" in (r["error"] or "")


def test_manual_paper_order_on_actionable_signal_ok():
    r = client.post("/api/command", json={"type": "MANUAL_PAPER_ORDER",
                                          "payload": {"symbol": "ZEC/USDT", "signal_id": "demo_zec",
                                                      "direction": "long", "risk_pct": 0.01},
                                          "confirm_token": "ok"}).json()
    assert r["status"] == "applied"
    assert json.loads(r["result_json"])["mode"] == "paper"


def test_command_writes_audit_row():
    before = len(control_db.recent_audit(1000))
    client.post("/api/command", json={"type": "SET_RISK_PER_TRADE",
                                       "payload": {"value": 0.02}, "confirm_token": "ok"})
    assert len(control_db.recent_audit(1000)) > before


# ------------------------------------------------- v1 paper controls --------
def _loosen_limits():
    control_db.set_setting("max_positions", 50)
    control_db.set_setting("daily_loss_limit", 0.5)
    control_db.set_setting("trading_mode", "paper")
    control_db.set_setting("emergency_paused", False)


def test_set_max_open_positions():
    r = client.post("/api/command", json={"type": "SET_MAX_OPEN_POSITIONS",
                                          "payload": {"value": 7}, "confirm_token": "ok"}).json()
    assert r["status"] == "applied"
    assert control_db.get_setting("max_positions") == 7
    bad = client.post("/api/command", json={"type": "SET_MAX_OPEN_POSITIONS",
                                            "payload": {"value": 999}, "confirm_token": "ok"}).json()
    assert bad["status"] == "rejected"
    _loosen_limits()


def test_weekly_loss_limit_range():
    ok = client.post("/api/command", json={"type": "SET_WEEKLY_LOSS_LIMIT",
                                           "payload": {"value": 0.1}, "confirm_token": "ok"}).json()
    assert ok["status"] == "applied"
    bad = client.post("/api/command", json={"type": "SET_WEEKLY_LOSS_LIMIT",
                                            "payload": {"value": 0.9}, "confirm_token": "ok"}).json()
    assert bad["status"] == "rejected"


def test_enable_mode_paper_alias_and_scalp_lock():
    ok = client.post("/api/command", json={"type": "ENABLE_MODE_PAPER",
                                           "payload": {"mode": "crypto_swing"}, "confirm_token": "ok"}).json()
    assert ok["status"] == "applied"
    scalp = client.post("/api/command", json={"type": "ENABLE_MODE_PAPER",
                                              "payload": {"mode": "crypto_scalp"}, "confirm_token": "ok"}).json()
    assert scalp["status"] == "rejected"


def test_paper_order_missing_stop_rejected():
    _loosen_limits()
    r = client.post("/api/command", json={"type": "MANUAL_PAPER_ORDER",
                                          "payload": {"symbol": "AAA/USDT", "direction": "long",
                                                      "risk_pct": 0.001},
                                          "confirm_token": "ok"}).json()
    assert r["status"] == "rejected"
    assert "missing stop" in (r["error"] or "")


def test_paper_order_custom_ok_then_close_idempotent():
    _loosen_limits()
    r = client.post("/api/command", json={"type": "MANUAL_PAPER_ORDER",
                                          "payload": {"symbol": "BBB/USDT", "direction": "long",
                                                      "stop": 1.0, "entry_price": 1.05, "risk_pct": 0.001},
                                          "confirm_token": "ok"}).json()
    assert r["status"] == "applied"
    oid = json.loads(r["result_json"])["order_id"]
    closed = client.post("/api/command", json={"type": "CLOSE_PAPER_TRADE",
                                               "payload": {"order_id": oid}, "confirm_token": "ok"}).json()
    assert closed["status"] == "applied"
    assert json.loads(closed["result_json"])["status"] == "closed"
    again = client.post("/api/command", json={"type": "CLOSE_PAPER_TRADE",
                                              "payload": {"order_id": oid}, "confirm_token": "ok"}).json()
    assert json.loads(again["result_json"]).get("idempotent") is True


def test_cancel_pending_paper():
    _loosen_limits()
    r = client.post("/api/command", json={"type": "MANUAL_PAPER_ORDER",
                                          "payload": {"symbol": "CCC/USDT", "direction": "short",
                                                      "stop": 2.0, "risk_pct": 0.001},
                                          "confirm_token": "ok"}).json()
    oid = json.loads(r["result_json"])["order_id"]
    cancelled = client.post("/api/command", json={"type": "CANCEL_PENDING_PAPER",
                                                  "payload": {"order_id": oid}, "confirm_token": "ok"}).json()
    assert cancelled["status"] == "applied"
    assert json.loads(cancelled["result_json"])["status"] == "cancelled"


def test_max_open_positions_enforced():
    _loosen_limits()
    control_db.set_setting("max_positions", 0)
    r = client.post("/api/command", json={"type": "MANUAL_PAPER_ORDER",
                                          "payload": {"symbol": "DDD/USDT", "direction": "long",
                                                      "stop": 1.0, "risk_pct": 0.001},
                                          "confirm_token": "ok"}).json()
    assert r["status"] == "rejected"
    assert "max open" in (r["error"] or "")
    _loosen_limits()


def test_daily_paper_risk_budget_enforced():
    _loosen_limits()
    control_db.set_setting("daily_loss_limit", 0.001)
    r = client.post("/api/command", json={"type": "MANUAL_PAPER_ORDER",
                                          "payload": {"symbol": "EEE/USDT", "direction": "long",
                                                      "stop": 1.0, "risk_pct": 0.02},
                                          "confirm_token": "ok"}).json()
    assert r["status"] == "rejected"
    assert "daily paper risk budget" in (r["error"] or "")
    _loosen_limits()


def test_add_trade_note_no_confirm_needed():
    r = client.post("/api/command", json={"type": "ADD_TRADE_NOTE",
                                          "payload": {"text": "watching BTC reclaim"}}).json()
    assert r["status"] == "applied"
    assert any(n["text"] == "watching BTC reclaim" for n in control_db.recent_notes(20))


def test_acknowledge_alert():
    nid = control_db.add_notification("warning", "test", "body")
    r = client.post("/api/command", json={"type": "ACKNOWLEDGE_ALERT",
                                          "payload": {"notification_id": nid}}).json()
    assert r["status"] == "applied"
    assert json.loads(r["result_json"])["acked"] == nid


def test_run_sanity_check_endpoint_and_command():
    rep = client.get("/api/system/sanity-check").json()
    assert rep["total"] > 0
    names = {c["name"]: c["ok"] for c in rep["checks"]}
    assert names.get("Live trading locked") and names.get("Auto-live locked")
    assert names.get("Crypto scalp not enabled")
    cmd = client.post("/api/command", json={"type": "RUN_SANITY_CHECK", "payload": {}}).json()
    assert cmd["status"] == "applied"


def test_recent_endpoints():
    assert "commands" in client.get("/api/commands/recent").json()
    assert "audit" in client.get("/api/audit/recent").json()
    assert "orders" in client.get("/api/orders/recent").json()
    assert "errors" in client.get("/api/system/errors").json()


def test_health_components_present():
    h = client.get("/api/system/health").json()
    names = [c["name"] for c in h["components"]]
    assert "Backend API" in names and "Control DB" in names and "Command queue" in names


def test_emergency_pause_bot_token(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "0")
    monkeypatch.setenv("CONTROL_BOT_TOKEN", "s3cr3t-bot")
    get_settings.cache_clear()
    ok = client.post("/api/emergency-pause", headers={"X-Control-Bot-Token": "s3cr3t-bot"}).json()
    assert ok["status"] == "applied"
    bad = client.post("/api/emergency-pause", headers={"X-Control-Bot-Token": "wrong"})
    assert bad.status_code == 401
    control_db.set_setting("emergency_paused", False)
    get_settings.cache_clear()


def test_production_forbids_auth_disabled(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_DISABLED", "1")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        get_settings().assert_safe_for_env()
    get_settings.cache_clear()
