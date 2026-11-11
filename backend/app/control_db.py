"""Control-plane SQLite (SEPARATE from the trading core DB).

Holds command queue, audit log, settings/runtime overrides, manual orders, notifications.
The trading core DB is NEVER written by this app — only read via the adapter.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    path = get_settings().control_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS control_users (
    telegram_user_id INTEGER PRIMARY KEY,
    username TEXT, role TEXT DEFAULT 'owner', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS control_commands (
    command_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    telegram_user_id INTEGER,
    username TEXT,
    type TEXT NOT NULL,
    payload_json TEXT,
    status TEXT NOT NULL,            -- pending|approved|applied|rejected|failed
    result_json TEXT,
    error TEXT,
    source TEXT DEFAULT 'mini_app',
    applied_at TEXT
);
CREATE TABLE IF NOT EXISTS control_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    telegram_user_id INTEGER,
    username TEXT,
    action_type TEXT NOT NULL,
    old_value TEXT, new_value TEXT,
    source TEXT DEFAULT 'mini_app',
    confirmation_status TEXT,
    result TEXT,
    error TEXT,
    command_id TEXT
);
CREATE TABLE IF NOT EXISTS control_settings (
    key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
-- runtime overrides applied ON TOP of base YAML (never edits YAML directly)
CREATE TABLE IF NOT EXISTS runtime_overrides (
    key TEXT PRIMARY KEY, value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL, updated_by INTEGER, expires_at TEXT, command_id TEXT
);
CREATE TABLE IF NOT EXISTS manual_orders (
    order_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    telegram_user_id INTEGER,
    mode TEXT NOT NULL,              -- paper|live
    symbol TEXT, direction TEXT, asset_class TEXT,
    entry_type TEXT, entry_price REAL, stop REAL,
    tp1 REAL, tp2 REAL, tp3 REAL,
    risk_pct REAL, leverage REAL, max_loss REAL,
    signal_id TEXT, notes TEXT,
    status TEXT NOT NULL,            -- queued|filled|cancelled|rejected
    command_id TEXT
);
CREATE TABLE IF NOT EXISTS app_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, level TEXT, title TEXT, body TEXT, acked INTEGER DEFAULT 0,
    ref TEXT
);
CREATE TABLE IF NOT EXISTS trade_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, telegram_user_id INTEGER, username TEXT,
    ref TEXT,                         -- signal_id or order_id the note is attached to (nullable)
    text TEXT NOT NULL, command_id TEXT
);
"""

# Default control settings (the editable risk/mode state lives here, not in trading YAML).
DEFAULT_SETTINGS: dict[str, Any] = {
    "trading_mode": "paper",          # disabled|paper|manual_live(locked)|auto_live(locked)
    # PART 3 reconciliation — match the derived paper-portfolio ledger (single source of truth):
    # $5000 deposit · 0.5% risk/trade · max 5x · current paper fee profile.
    "paper_balance": 5000.0,
    "live_balance": 0.0,
    "risk_per_trade": 0.005,          # 0.5% — matches ledger
    "max_leverage": 5,                # max 5x safe leverage policy
    "fee_profile": "bybit_non_vip_usdt_perp",
    "paper_profile_source": "paper_portfolio_ledger ($5000 / 0.5% / max 5x)",
    "daily_loss_limit": 0.03,
    "weekly_loss_limit": 0.06,
    "max_positions": 5,
    "max_sector_exposure": 2,
    "allowed_modes": {
        "crypto_intraday": True, "crypto_swing": True, "crypto_short": True,
        "stocks_intraday": True,
        "crypto_scalp": False,        # research/shadow only — locked
        "stocks_scalp": False,        # research/backtest only — locked
        "stocks_swing": False, "stocks_invest": False,  # paused
    },
    "symbol_whitelist": [],
    "emergency_paused": False,
}


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)
        # lightweight forward migrations for pre-existing control DBs (idempotent)
        for table, col, decl in (("app_notifications", "ref", "TEXT"),):
            cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        for k, v in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO control_settings(key, value_json, updated_at) VALUES(?,?,?)",
                (k, json.dumps(v), _now()),
            )
        c.commit()


# ---- settings ----
def get_setting(key: str, default: Any = None) -> Any:
    with connect() as c:
        row = c.execute("SELECT value_json FROM control_settings WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def all_settings() -> dict[str, Any]:
    with connect() as c:
        rows = c.execute("SELECT key, value_json FROM control_settings").fetchall()
    return {r["key"]: json.loads(r["value_json"]) for r in rows}


def set_setting(key: str, value: Any) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO control_settings(key, value_json, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
            (key, json.dumps(value), _now()),
        )
        c.commit()


# ---- audit ----
def audit(action_type: str, *, user_id=None, username=None, old=None, new=None,
          confirmation=None, result=None, error=None, command_id=None) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO control_audit_log(ts, telegram_user_id, username, action_type, "
            "old_value, new_value, source, confirmation_status, result, error, command_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (_now(), user_id, username, action_type,
             json.dumps(old) if old is not None else None,
             json.dumps(new) if new is not None else None,
             "mini_app", confirmation, result, error, command_id),
        )
        c.commit()


def recent_audit(limit: int = 50) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM control_audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---- commands ----
def create_command(ctype: str, payload: dict, *, user_id=None, username=None,
                   status: str = "pending") -> dict:
    cid = str(uuid.uuid4())
    with connect() as c:
        c.execute(
            "INSERT INTO control_commands(command_id, created_at, telegram_user_id, username, "
            "type, payload_json, status, source) VALUES(?,?,?,?,?,?,?,?)",
            (cid, _now(), user_id, username, ctype, json.dumps(payload), status, "mini_app"),
        )
        c.commit()
    return get_command(cid)


def update_command(cid: str, *, status=None, result=None, error=None) -> None:
    with connect() as c:
        c.execute(
            "UPDATE control_commands SET status=COALESCE(?,status), "
            "result_json=COALESCE(?,result_json), error=COALESCE(?,error), "
            "applied_at=CASE WHEN ?='applied' THEN ? ELSE applied_at END WHERE command_id=?",
            (status, json.dumps(result) if result is not None else None, error,
             status, _now(), cid),
        )
        c.commit()


def get_command(cid: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM control_commands WHERE command_id=?", (cid,)).fetchone()
    return dict(row) if row else None


def recent_commands(limit: int = 50) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM control_commands ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def record_manual_order(order: dict) -> str:
    oid = order.get("order_id") or str(uuid.uuid4())
    order["order_id"] = oid
    cols = ["order_id", "created_at", "telegram_user_id", "mode", "symbol", "direction",
            "asset_class", "entry_type", "entry_price", "stop", "tp1", "tp2", "tp3",
            "risk_pct", "leverage", "max_loss", "signal_id", "notes", "status", "command_id"]
    order.setdefault("created_at", _now())
    with connect() as c:
        c.execute(
            f"INSERT INTO manual_orders({','.join(cols)}) VALUES({','.join('?'*len(cols))})",
            tuple(order.get(k) for k in cols),
        )
        c.commit()
    return oid


def get_manual_order(order_id: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM manual_orders WHERE order_id=?", (order_id,)).fetchone()
    return dict(row) if row else None


def find_manual_order(ref: str) -> dict | None:
    """Find a manual order by order_id OR signal_id (most recent)."""
    with connect() as c:
        row = c.execute(
            "SELECT * FROM manual_orders WHERE order_id=? OR signal_id=? "
            "ORDER BY created_at DESC LIMIT 1", (ref, ref)).fetchone()
    return dict(row) if row else None


def update_manual_order(order_id: str, *, status: str) -> None:
    with connect() as c:
        c.execute("UPDATE manual_orders SET status=? WHERE order_id=?", (status, order_id))
        c.commit()


def recent_manual_orders(limit: int = 50) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM manual_orders ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def open_paper_orders() -> list[dict]:
    """Paper orders that still consume risk (queued or filled)."""
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM manual_orders WHERE mode='paper' AND status IN ('queued','filled')"
        ).fetchall()
    return [dict(r) for r in rows]


def paper_risk_used_today() -> float:
    """Sum of risk_pct for paper orders opened since UTC midnight (queued/filled)."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with connect() as c:
        rows = c.execute(
            "SELECT risk_pct FROM manual_orders WHERE mode='paper' "
            "AND status IN ('queued','filled') AND substr(created_at,1,10)=?", (day,)).fetchall()
    return float(sum((r[0] or 0.0) for r in rows))


# ---- notes ----
def add_trade_note(text: str, *, ref=None, user_id=None, username=None, command_id=None) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO trade_notes(ts, telegram_user_id, username, ref, text, command_id) "
            "VALUES(?,?,?,?,?,?)", (_now(), user_id, username, ref, text, command_id))
        c.commit()
        return cur.lastrowid


def recent_notes(limit: int = 50, ref: str | None = None) -> list[dict]:
    with connect() as c:
        if ref:
            rows = c.execute("SELECT * FROM trade_notes WHERE ref=? ORDER BY id DESC LIMIT ?",
                             (ref, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM trade_notes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---- notifications / alert acks ----
def add_notification(level: str, title: str, body: str = "", ref: str | None = None) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO app_notifications(ts, level, title, body, acked, ref) VALUES(?,?,?,?,0,?)",
            (_now(), level, title, body, ref))
        c.commit()
        return cur.lastrowid


def ack_notification(notif_id) -> bool:
    with connect() as c:
        cur = c.execute("UPDATE app_notifications SET acked=1 WHERE id=?", (notif_id,))
        c.commit()
        return cur.rowcount > 0


def unacked_notifications() -> int:
    with connect() as c:
        return c.execute("SELECT COUNT(*) FROM app_notifications WHERE acked=0").fetchone()[0]


def command_queue_health() -> dict:
    """Counts by status over the last 200 commands — for system health."""
    with connect() as c:
        rows = c.execute(
            "SELECT status, COUNT(*) c FROM (SELECT status FROM control_commands "
            "ORDER BY created_at DESC LIMIT 200) GROUP BY status").fetchall()
    return {r["status"]: r["c"] for r in rows}
