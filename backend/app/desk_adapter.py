"""Read-only adapter over the existing crypto-ai-desk SQLite + OHLCV cache.

NEVER writes to the trading DB. Falls back to synthetic demo data when the desk DB is
absent so the UI is fully explorable offline. All signals are passed through
`actionability.classify` so the frontend renders consistent, safe verdicts.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import actionability, books, control_db
from .config import get_settings

_NON_TERMINAL = {"generated", "waiting_for_entry", "triggered", "tp1_hit", "tp2_hit"}


def _now():
    return datetime.now(timezone.utc)


def _ro_conn() -> sqlite3.Connection | None:
    s = get_settings()
    if s.demo_mode or not s.has_desk_db:
        return None
    try:
        conn = sqlite3.connect(f"file:{s.desk_db_path}?mode=ro", uri=True, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


# ---------------------------------------------------------------- signals ---
def _latest_outcome(conn, sid):
    r = conn.execute(
        "SELECT * FROM signal_outcomes WHERE signal_id=? ORDER BY checked_at DESC LIMIT 1", (sid,)
    ).fetchone()
    return dict(r) if r else {}


def _paper_execution(conn, sid):
    """Latest authoritative Paper-execution row for display reconciliation.

    ``signal_outcomes.final_outcome`` is legacy touch-tracker state and can say
    ``expired`` while a position remains open. This is read-only enrichment.
    """
    try:
        r = conn.execute(
            "SELECT lifecycle_state,paper_execution_outcome,paper_execution_r,"
            "close_reason,exit_at,protection_armed,protection_level_r,"
            "lock_armed,lock_level_r,highest_tp_touched "
            "FROM paper_execution_outcomes WHERE signal_id=? "
            "ORDER BY computed_at DESC, rowid DESC LIMIT 1",
            (sid,),
        ).fetchone()
    except sqlite3.OperationalError:
        return {}
    return dict(r) if r else {}


def _close_alert(conn, sid):
    """Latest close/outcome alert delivery state for the signal (read-only)."""
    r = conn.execute(
        "SELECT alert_type, telegram_status, sent_at FROM signal_alerts WHERE signal_id=? "
        "AND alert_type LIKE 'close_%' ORDER BY sent_at DESC LIMIT 1", (sid,)
    ).fetchone()
    if not r:
        return {}
    st = r["telegram_status"]
    return {"close_alert_type": r["alert_type"], "close_alert_status": st,
            "close_alert_sent": st == "sent", "close_alert_at": r["sent_at"]}


def _conc_from_alert(conn, sid):
    r = conn.execute(
        "SELECT payload_json, telegram_status, sent_at FROM signal_alerts WHERE signal_id=? "
        "AND alert_type='paper_entry' ORDER BY sent_at DESC LIMIT 1", (sid,)
    ).fetchone()
    if not r:
        return {}
    # Delivery status is meaningful even when the payload is empty — capture it so the
    # read-model can separate Operator (delivered) from Paper (decided) books.
    entry_meta = {"entry_alert_status": r["telegram_status"],
                  "entry_alert_sent": r["telegram_status"] == "sent",
                  "entry_alert_at": r["sent_at"]}
    if not r["payload_json"]:
        return entry_meta
    try:
        p = json.loads(r["payload_json"])
        out = {"concentration_status": p.get("concentration_status"),
               "concentration_reason": p.get("concentration_reason"),
               "risk_bucket": p.get("risk_bucket"), "size_weight": p.get("size_weight")}
        out.update(entry_meta)
        # Read-only pass-through of the add-only risk-guard diagnostic fields
        # (producer: crypto-ai-desk paper-entry payload). All optional; absent
        # keys stay None. Pure display — never affects commands/locks/routing.
        for k in ("circuit_breaker_state", "day_realized_r", "stops_today",
                  "consecutive_stops", "crypto_long_streak_count",
                  "btc_intraday_risk_off", "regime_context",
                  "lifecycle_label", "held_hours", "next_day_revalidation_required",
                  "carryover_warning", "would_bind_sector_cap", "would_sector_rank",
                  "profit_protection_hint", "catalyst_integrity_status",
                  "direct_news_items_checked", "catalyst_mapping_confidence",
                  # Shadow Intelligence Layer (read-only diagnostic pass-through)
                  "intelligence_layer_status", "squeeze_phase",
                  "squeeze_phase_confidence", "no_chase_warning",
                  "distribution_risk_score", "derivatives_context",
                  "funding_turning_down", "thesis_summary_compact",
                  "thesis_invalidation", "onchain_risk_status",
                  "timeline_confidence", "timeline_recent_outcome_bias",
                  # Crypto Quality Overlay (read-only diagnostic pass-through). Soft PAPER
                  # sizing/routing breaker verdict carried on the paper_entry payload — pure
                  # display; never consumed by actionability/commands/routing.
                  "cqo_quality_action", "cqo_crypto_quality_verdict", "cqo_crypto_quality_score",
                  "cqo_btc_regime_state", "cqo_session_bucket_utc", "cqo_session_quality_state",
                  "cqo_symbol_cooldown_state", "cqo_mode_session_cooldown_state",
                  "cqo_would_have_been_action_without_overlay", "cqo_reasons"):
            out[k] = p.get(k)
        return out
    except Exception:
        return entry_meta


def _normalize(row: dict, outcome: dict, conc: dict, paper_exec: dict | None = None) -> dict:
    paper_exec = paper_exec or {}
    sig = {
        "signal_id": row.get("signal_id"), "symbol": row.get("symbol"),
        "asset_class": row.get("asset_class"), "mode": row.get("mode"),
        "tier": row.get("tier"), "score": row.get("score"), "direction": row.get("direction"),
        "status": row.get("status"), "created_at": row.get("created_at"),
        "entry_low": row.get("entry_low"), "entry_high": row.get("entry_high"),
        "entry_trigger": row.get("entry_trigger"), "stop_loss": row.get("stop_loss"),
        "invalidation": row.get("invalidation"),
        "tp1": row.get("tp1"), "tp2": row.get("tp2"), "tp3": row.get("tp3"),
        "expected_rr_tp1": row.get("expected_rr_tp1"),
        "news_supported": row.get("news_supported"),
        "telegram_supported": row.get("telegram_supported"),
        "derivatives_supported": row.get("derivatives_supported"),
        "setup_type": row.get("setup_type"),
        "market_regime": row.get("market_regime"),
        "validity_window_hours": row.get("validity_window_hours"),
        "expires_at": row.get("expires_at"),
        "funding_context": row.get("funding_context"), "oi_context": row.get("oi_context"),
        "narrative": row.get("narrative") or row.get("sector"),
        "thesis": row.get("thesis"),
        "entry_triggered": outcome.get("entry_triggered"),
        "entry_triggered_at": outcome.get("entry_triggered_at"),
        "stop_hit": outcome.get("stop_hit"),
        "tp1_hit": outcome.get("tp1_hit"),
        "tp2_hit": outcome.get("tp2_hit"),
        "tp3_hit": outcome.get("tp3_hit"),
        "checked_at": outcome.get("checked_at"),
        "final_outcome": outcome.get("final_outcome"), "final_r": outcome.get("final_r"),
        "exit_at": (paper_exec.get("exit_at") or outcome.get("exit_at") or outcome.get("stop_hit_at")
                    or outcome.get("tp3_hit_at") or outcome.get("tp2_hit_at")
                    or outcome.get("tp1_hit_at")),
        "mfe_r": outcome.get("max_favorable_excursion_r"),
        "mae_r": outcome.get("max_adverse_excursion_r"),
        "concentration_status": conc.get("concentration_status"),
        "concentration_reason": conc.get("concentration_reason"),
        "risk_bucket": conc.get("risk_bucket"), "size_weight": conc.get("size_weight"),
        # Telegram delivery state (read-only) — lets the read-model separate the
        # Operator book (actually delivered) from the Paper book (decided by policy).
        "entry_alert_status": conc.get("entry_alert_status"),
        "entry_alert_sent": conc.get("entry_alert_sent"),
        "entry_alert_at": conc.get("entry_alert_at"),
        "close_alert_type": conc.get("close_alert_type"),
        "close_alert_status": conc.get("close_alert_status"),
        "close_alert_sent": conc.get("close_alert_sent"),
        "close_alert_at": conc.get("close_alert_at"),
        "paper_lifecycle_state": paper_exec.get("lifecycle_state"),
        "paper_execution_outcome": paper_exec.get("paper_execution_outcome"),
        "paper_execution_r": paper_exec.get("paper_execution_r"),
        "paper_close_reason": paper_exec.get("close_reason"),
        "paper_exit_at": paper_exec.get("exit_at"),
        "paper_protection_armed": paper_exec.get("protection_armed"),
        "paper_protection_level_r": paper_exec.get("protection_level_r"),
        "paper_lock_armed": paper_exec.get("lock_armed"),
        "paper_lock_level_r": paper_exec.get("lock_level_r"),
        "paper_highest_tp_touched": paper_exec.get("highest_tp_touched"),
    }
    # Add-only risk-guard diagnostics (read-only display fields). Never consumed by
    # actionability/commands — purely surfaced for operator visibility.
    for k in ("circuit_breaker_state", "day_realized_r", "stops_today",
              "consecutive_stops", "crypto_long_streak_count",
              "btc_intraday_risk_off", "regime_context",
              "lifecycle_label", "held_hours", "next_day_revalidation_required",
              "carryover_warning", "would_bind_sector_cap", "would_sector_rank",
              "profit_protection_hint", "catalyst_integrity_status",
              "direct_news_items_checked", "catalyst_mapping_confidence",
              "intelligence_layer_status", "squeeze_phase",
              "squeeze_phase_confidence", "no_chase_warning",
              "distribution_risk_score", "derivatives_context",
              "funding_turning_down", "thesis_summary_compact",
              "thesis_invalidation", "onchain_risk_status",
              "timeline_confidence", "timeline_recent_outcome_bias",
              # Crypto Quality Overlay per-signal diagnostic (read-only display).
              "cqo_quality_action", "cqo_crypto_quality_verdict", "cqo_crypto_quality_score",
              "cqo_btc_regime_state", "cqo_session_bucket_utc", "cqo_session_quality_state",
              "cqo_symbol_cooldown_state", "cqo_mode_session_cooldown_state",
              "cqo_would_have_been_action_without_overlay", "cqo_reasons"):
        sig[k] = conc.get(k)
    # Catalyst/news labels (read-only, from the refreshed signal_catalyst_labels cache).
    for k in ("catalyst_freshness", "catalyst_strength", "catalyst_source_quality",
              "catalyst_symbol_mapping", "catalyst_derivatives_label", "catalyst_headline",
              "catalyst_label_computed_at"):
        sig[k] = conc.get(k)
    # Derived catalyst support: honest tri-state. supported if news/telegram flag set;
    # unknown if no label row exists (linkage missing/stale); else unsupported.
    _ns = bool(sig.get("news_supported")) or bool(sig.get("telegram_supported"))
    if _ns:
        sig["catalyst_supported"] = "supported"
    elif conc.get("catalyst_label_computed_at"):
        sig["catalyst_supported"] = "unsupported"
    else:
        sig["catalyst_supported"] = "unknown"
    sig["actionability"] = actionability.classify(sig)
    # Add-only display semantics (read-only). Lets the UI show open/waiting/
    # entered-unresolved/review-shadow/no-entry instead of a bare `expired`/`+0R`.
    # Never consumed by actionability or commands; fail-open.
    try:
        from app import display_status as _ds
        sig.update(_ds.derive_display_status(sig))
    except Exception:
        pass
    return sig


def _catalyst_label(conn, sid):
    """Latest derived catalyst label row for the signal (read-only display cache)."""
    try:
        r = conn.execute(
            "SELECT catalyst_freshness, catalyst_strength, source_quality, symbol_mapping, "
            "derivatives_label, headline_short, computed_at FROM signal_catalyst_labels "
            "WHERE signal_id=? ORDER BY computed_at DESC LIMIT 1", (sid,)).fetchone()
    except sqlite3.OperationalError:
        return {}
    if not r:
        return {}
    return {"catalyst_freshness": r["catalyst_freshness"],
            "catalyst_strength": r["catalyst_strength"],
            "catalyst_source_quality": r["source_quality"],
            "catalyst_symbol_mapping": r["symbol_mapping"],
            "catalyst_derivatives_label": r["derivatives_label"],
            "catalyst_headline": r["headline_short"],
            "catalyst_label_computed_at": r["computed_at"]}


def _alert_and_labels(conn, sid):
    """Combined read-only enrichment dict: entry alert + close alert + catalyst label."""
    d = _conc_from_alert(conn, sid)
    d.update(_close_alert(conn, sid))
    d.update(_catalyst_label(conn, sid))
    return d


def list_signals(limit: int = 200) -> list[dict]:
    conn = _ro_conn()
    if conn is None:
        return _demo_signals()
    out = []
    rows = conn.execute(
        "SELECT * FROM proposed_signals WHERE status NOT IN ('rejected') "
        "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    for r in rows:
        d = dict(r)
        out.append(_normalize(
            d, _latest_outcome(conn, d["signal_id"]), _alert_and_labels(conn, d["signal_id"]),
            _paper_execution(conn, d["signal_id"]),
        ))
    conn.close()
    return out


def get_signal(sid: str) -> dict | None:
    conn = _ro_conn()
    if conn is None:
        return next((s for s in _demo_signals() if s["signal_id"] == sid), None)
    r = conn.execute("SELECT * FROM proposed_signals WHERE signal_id=?", (sid,)).fetchone()
    if not r:
        conn.close()
        return None
    d = dict(r)
    sig = _normalize(d, _latest_outcome(conn, sid), _alert_and_labels(conn, sid), _paper_execution(conn, sid))
    conn.close()
    return sig


# ----------------------------------------------------------------- trades ---
def trades(bucket: str) -> list[dict]:
    """bucket ∈ open|pending|closed|shadow."""
    sigs = list_signals(400)
    out = []
    for s in sigs:
        st = (s.get("status") or "").lower()
        act = s["actionability"]["status"]
        # "open" = entry happened and the REGISTRY status is still non-terminal (triggered / partial).
        # NOTE: signal_outcomes.final_outcome is an interim tracker label stamped on every per-bar row
        # (even while still open), so it is NOT a reliable "closed" flag — registry status is.
        entered = bool(s.get("entry_triggered_at")) and st in {"triggered", "tp1_hit", "tp2_hit"}
        terminal = bool(st) and st not in _NON_TERMINAL
        if bucket == "shadow" and act in ("shadow",):
            out.append(s)
        elif bucket == "open" and entered:
            out.append(s)
        elif bucket == "pending" and st in ("generated", "waiting_for_entry") and act == "actionable":
            out.append(s)
        elif bucket == "closed" and terminal:
            out.append(s)
    return out


# --------------------------------------------------- canonical book views ---
# Pull a wide window so dedup + 7d ranges are accurate (signal_ids duplicate, so
# row count >> economic-trade count). Read-only; cached by the frontend query layer.
_BOOK_LIMIT = 600


def _enrich_book_row(s: dict) -> dict:
    """Add read-only book classification + human close-reason fields to a signal."""
    cls = books.derive_trade_book(s)
    oc = books.outcome_class(s)
    s = dict(s)
    s["book"] = cls["book"]
    s["book_delivered"] = cls["delivered"]
    s["delivery_state"] = cls["delivery"]
    s["outcome_class"] = oc
    s["close_reason"] = books.close_reason(s)
    s["close_explanation"] = books.plain_explanation(s)
    # LEGACY touch metric (old final_r / realized_r) — optimistic, signal-quality ONLY, NOT PnL.
    # Exposed under ONE explicit name; the old `realized_r` / `touch_r` API keys are removed so
    # nothing can read the touch number as if it were a result/PnL.
    s["legacy_touch_r"] = books.touch_r(s)
    # Paper execution accounting (Model F) — authoritative paper R + protection annotations for
    # the trade row. USD net (paper ledger) is the authoritative PnL. Display only.
    s["paper_execution_r"] = books.paper_execution_r(s)
    s.update(books.paper_exec_flags(s))
    ct = books.close_time(s)
    s["close_time"] = ct.isoformat() if ct else None
    return s


def dashboard_summary() -> dict:
    """Honest, deduped, book-separated dashboard summary (fixes the old -26R)."""
    return books.get_dashboard_summary(list_signals(_BOOK_LIMIT))


def closed_trades_book(book: str = "operator", hours: float | None = None) -> list[dict]:
    """Deduped closed economic trades for one book, enriched for the Closed tab."""
    rows = list_signals(_BOOK_LIMIT)
    closed = books.get_closed_trades(rows, book=book, hours=hours)
    closed.sort(key=lambda t: (t.get("close_time") or t.get("exit_at") or ""), reverse=True)
    return [_enrich_book_row(t) for t in closed]


def _portfolio_ledger_by_signal_id(fee_profile: str | None = None) -> dict[str, dict]:
    """Read paper ledger rows for USD PnL matching. Empty on demo/missing DB."""
    try:
        from app import portfolio
        fee_profile = fee_profile or portfolio.ACTIVE_FEE_PROFILE
        conn = portfolio._ro_conn()
        if conn is None or not portfolio._has_table(conn, "paper_portfolio_ledger"):
            return {}
        try:
            rows = conn.execute(
                "SELECT * FROM paper_portfolio_ledger WHERE event_type='exit' AND fee_profile=?",
                (fee_profile,),
            ).fetchall()
            return {str(r["signal_id"]): dict(r) for r in rows if r["signal_id"]}
        finally:
            conn.close()
    except Exception:
        return {}


def closed_trades_analytics(book: str = "operator", hours: float | None = None,
                            fee_profile: str | None = None) -> dict:
    """PnL curve + trading calendar for the Closed/Shadow trade books."""
    rows = list_signals(_BOOK_LIMIT)
    closed = books.get_closed_trades(rows, book=book, hours=hours)
    out = books.closed_trade_analytics(closed, _portfolio_ledger_by_signal_id(fee_profile))
    out.update({"book": book, "hours": hours})
    return out


def near_winners(book: str = "operator", hours: float | None = 168.0) -> dict:
    """Diagnostic-only near-winner expired panel (does NOT change exits)."""
    rows = list_signals(_BOOK_LIMIT)
    nw = books.near_winner_expired(rows, book=book, hours=hours)
    return {"note": "Diagnostic only — does not change exits.",
            "count": len(nw), "items": [_enrich_book_row(t) for t in nw]}


# ------------------------------------------------------------------ chart ---
def _desk_root() -> Path:
    return get_settings().desk_db_path.parents[1]


def chart(symbol: str, tf: str = "5m") -> dict:
    """Return candles + overlay levels for a symbol. Honest 'unavailable' if no cache."""
    sig = next((s for s in list_signals(400) if s["symbol"] == symbol), None)
    overlays = {}
    if sig:
        overlays = {k: sig.get(k) for k in
                    ("entry_low", "entry_high", "entry_trigger", "stop_loss",
                     "tp1", "tp2", "tp3", "entry_triggered_at", "exit_at", "created_at",
                     "final_outcome", "mfe_r", "mae_r")}
    candles = _load_candles(symbol, tf)
    return {"symbol": symbol, "tf": tf, "candles": candles,
            "candles_available": bool(candles), "overlays": overlays,
            "signal": sig}


def _load_candles(symbol: str, tf: str) -> list[dict]:
    s = get_settings()
    if s.demo_mode or not s.has_desk_db:
        return _demo_candles()
    base = symbol.split("/")[0]
    root = _desk_root() / "data" / "raw"
    candidates = list((root / "ohlcv").glob(f"*/{tf}/{base}_USDT.csv")) + \
        [root / "stocks" / tf / f"{base}.csv"]
    for path in candidates:
        if path.exists():
            return _read_ohlcv_csv(path)
    return []


def _read_ohlcv_csv(path: Path) -> list[dict]:
    out = []
    try:
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
    except Exception:
        return []
    for r in rows[-300:]:
        tcol = next((c for c in r if c.lower() in ("timestamp", "datetime", "date", "time", "open_time")), None)
        try:
            out.append({"t": str(r[tcol]), "o": float(r["open"]), "h": float(r["high"]),
                        "l": float(r["low"]), "c": float(r["close"]),
                        "v": float(r.get("volume", 0) or 0)})
        except Exception:
            continue
    return out


# ------------------------------------------------------------ status/health -
def system_status() -> dict:
    s = get_settings()
    conn = _ro_conn()
    last_tick = None
    online = False
    if conn is not None:
        r = conn.execute("SELECT MAX(checked_at) m FROM signal_outcomes").fetchone()
        last_tick = r["m"] if r else None
        conn.close()
        if last_tick:
            age = (_now() - actionability._parse(last_tick)).total_seconds() if actionability._parse(last_tick) else 1e9
            online = age < 3600  # ticked within last hour
    settings = control_db.all_settings()
    return {
        "engine_online": online, "demo_mode": s.demo_mode,
        "trading_mode": settings.get("trading_mode", "paper"),
        "auto_live_locked": True, "live_commands_enabled": False,
        "last_monitor_tick": last_tick,
        "emergency_paused": settings.get("emergency_paused", False),
        "badges": ["Engine online" if online else "Engine offline",
                   f"Mode: {settings.get('trading_mode','paper')}",
                   "Live LOCKED", "Scalp shadow-only", "Option B tracker", "Concentration guard"],
    }


def _age_min(ts) -> float | None:
    dt = actionability._parse(ts)
    return (_now() - dt).total_seconds() / 60 if dt else None


def _fmt_age(mins: float | None) -> str:
    if mins is None:
        return "n/a"
    if mins < 60:
        return f"{mins:.0f}m ago"
    if mins < 1440:
        return f"{mins/60:.1f}h ago"
    return f"{mins/1440:.1f}d ago"


def _ohlcv_freshness() -> tuple[float | None, str]:
    """Best-effort newest OHLCV csv mtime (bounded scan). Returns (age_min, detail)."""
    root = _desk_root() / "data" / "raw" / "ohlcv"
    if not root.exists():
        return None, "n/a (no ohlcv cache)"
    newest = 0.0
    scanned = 0
    try:
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.endswith(".csv"):
                    scanned += 1
                    try:
                        m = os.path.getmtime(os.path.join(dirpath, f))
                        if m > newest:
                            newest = m
                    except OSError:
                        pass
                    if scanned >= 800:  # bound the walk
                        break
            if scanned >= 800:
                break
    except OSError:
        return None, "n/a (scan error)"
    if newest <= 0:
        return None, "n/a (no csv files)"
    age = max(0.0, (_now().timestamp() - newest)) / 60
    return age, _fmt_age(age)


def _control_health() -> list[dict]:
    """Components derived from the control DB (always available)."""
    try:
        control_db.all_settings()
        ctrl_ok, ctrl_detail = True, "reachable"
    except Exception as e:  # pragma: no cover - defensive
        ctrl_ok, ctrl_detail = False, f"error: {e}"
    q = {}
    try:
        q = control_db.command_queue_health()
    except Exception:
        pass
    failed = q.get("failed", 0)
    return [
        {"name": "Backend API", "ok": True, "detail": "online"},
        {"name": "Control DB", "ok": ctrl_ok, "detail": ctrl_detail},
        {"name": "Command queue", "ok": failed == 0,
         "detail": f"{q.get('applied',0)} applied · {q.get('rejected',0)} rejected · {failed} failed (last 200)"},
    ]


def system_health() -> dict:
    s = get_settings()
    components = _control_health()

    if s.demo_mode or not s.has_desk_db:
        return {"demo_mode": True, "components": components + _demo_health(),
                "errors": [], "schema_ok": True, "schema_error": None}

    conn = _ro_conn()
    if conn is None:
        components.append({"name": "Trading DB (read-only)", "ok": False,
                           "detail": f"cannot open {s.desk_db_path}"})
        return {"demo_mode": False, "components": components,
                "errors": [{"type": "trading_db_unreachable", "count": 1}],
                "schema_ok": False, "schema_error": "trading DB unreachable"}

    errors: list[dict] = []
    schema_ok, schema_error = True, None
    try:
        cutoff = (_now() - timedelta(hours=24)).isoformat()
        errs = conn.execute(
            "SELECT telegram_status, COUNT(*) c FROM signal_alerts WHERE sent_at>=? "
            "AND telegram_status LIKE 'error%' GROUP BY telegram_status", (cutoff,)).fetchall()
        n_timeout = conn.execute(
            "SELECT COUNT(*) FROM signal_alerts WHERE sent_at>=? AND telegram_status LIKE '%timeout%'",
            (cutoff,)).fetchone()[0]
        last_tick = (conn.execute("SELECT MAX(checked_at) m FROM signal_outcomes").fetchone() or {})["m"]
        last_sig = (conn.execute("SELECT MAX(created_at) m FROM proposed_signals").fetchone() or {})["m"]
        last_alert = (conn.execute("SELECT MAX(sent_at) m FROM signal_alerts").fetchone() or {})["m"]
        n_alert = conn.execute("SELECT COUNT(*) FROM signal_alerts WHERE sent_at>=?", (cutoff,)).fetchone()[0]
        errors = [{"type": e["telegram_status"], "count": e["c"]} for e in errs]
    except sqlite3.OperationalError as e:  # schema mismatch
        conn.close()
        components.append({"name": "Trading DB (read-only)", "ok": False,
                           "detail": f"schema mismatch: {e}"})
        return {"demo_mode": False, "components": components,
                "errors": [{"type": "schema_mismatch", "count": 1}],
                "schema_ok": False, "schema_error": str(e)}
    finally:
        try:
            conn.close()
        except Exception:
            pass

    tick_age = _age_min(last_tick)
    sig_age = _age_min(last_sig)
    alert_age = _age_min(last_alert)
    ohlcv_age, ohlcv_detail = _ohlcv_freshness()

    components += [
        {"name": "Trading DB (read-only)", "ok": True, "detail": f"connected · {s.desk_db_path.name}"},
        {"name": "Monitor / tracker", "ok": bool(tick_age is not None and tick_age < 30),
         "detail": f"last tick {_fmt_age(tick_age)}"},
        {"name": "Latest signal", "ok": bool(sig_age is not None and sig_age < 1440),
         "detail": _fmt_age(sig_age)},
        {"name": "Latest alert", "ok": bool(alert_age is not None and alert_age < 1440),
         "detail": _fmt_age(alert_age)},
        {"name": "Telegram alerts (24h)", "ok": n_timeout == 0,
         "detail": f"{n_alert} sent · {n_timeout} timeouts"},
        {"name": "OHLCV freshness", "ok": bool(ohlcv_age is not None and ohlcv_age < 180),
         "detail": ohlcv_detail},
    ]
    return {"demo_mode": False, "components": components, "errors": errors,
            "schema_ok": schema_ok, "schema_error": schema_error}


def system_errors() -> dict:
    """Recent errors across the stack: telegram delivery errors + failed control commands."""
    out: list[dict] = []
    for c in control_db.recent_commands(100):
        if (c.get("status") or "") in ("failed", "rejected"):
            out.append({"ts": c.get("created_at"), "source": "command",
                        "type": c.get("type"), "detail": c.get("error") or c.get("status")})
    h = system_health()
    for e in h.get("errors", []):
        out.append({"ts": None, "source": "trading_db", "type": e["type"],
                    "detail": f"{e['count']} in 24h"})
    return {"errors": out[:50], "count": len(out)}


def sanity_check() -> dict:
    """Run a set of read-only health assertions. Never mutates anything."""
    s = get_settings()
    checks: list[dict] = []

    def chk(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    # control DB
    try:
        settings = control_db.all_settings()
        chk("Control DB reachable", True, f"{len(settings)} settings")
    except Exception as e:
        settings = {}
        chk("Control DB reachable", False, str(e))

    # safety invariants (must always hold)
    chk("Live trading locked", not s.enable_live_commands, "enable_live_commands=False")
    chk("Auto-live locked", s.auto_live_locked, "auto_live_locked=True")
    am = settings.get("allowed_modes", {})
    chk("Crypto scalp not enabled", am.get("crypto_scalp") is False, "shadow-only")
    chk("Stocks scalp not enabled", am.get("stocks_scalp") is False, "research-only")
    chk("Trading mode is paper/disabled",
        str(settings.get("trading_mode")) in ("paper", "disabled"), str(settings.get("trading_mode")))

    # data source
    if s.demo_mode or not s.has_desk_db:
        chk("Data source", True, "demo mode")
    else:
        conn = _ro_conn()
        if conn is None:
            chk("Trading DB reachable", False, "cannot open")
        else:
            try:
                n = conn.execute("SELECT COUNT(*) FROM proposed_signals").fetchone()[0]
                last_sig = (conn.execute("SELECT MAX(created_at) m FROM proposed_signals").fetchone() or {})["m"]
                chk("Trading DB reachable", True, f"{n} signals")
                age = _age_min(last_sig)
                chk("Recent signal (<24h)", bool(age is not None and age < 1440), _fmt_age(age))
            except sqlite3.OperationalError as e:
                chk("Trading DB schema", False, f"mismatch: {e}")
            finally:
                conn.close()

    # command queue
    try:
        q = control_db.command_queue_health()
        chk("No failed commands (last 200)", q.get("failed", 0) == 0, f"{q.get('failed',0)} failed")
    except Exception as e:
        chk("Command queue readable", False, str(e))

    passed = sum(1 for c in checks if c["ok"])
    return {"ok": passed == len(checks), "passed": passed, "total": len(checks), "checks": checks}


# ------------------------------------------------------------------ market --
def market_summary() -> dict:
    sigs = [s for s in list_signals(400) if (s.get("asset_class") == "crypto")]
    by_narr: dict[str, list] = {}
    for s in sigs:
        n = s.get("narrative") or "uncategorized"
        by_narr.setdefault(n, []).append(s)
    narratives = []
    for n, group in sorted(by_narr.items(), key=lambda kv: -len(kv[1]))[:8]:
        syms = sorted({g["symbol"] for g in group})[:6]
        narratives.append({"name": n, "symbols": syms, "count": len(group),
                           "strength": min(100, 40 + 8 * len(group))})
    return {"narratives": narratives,
            "funding_oi": [{"symbol": s["symbol"], "funding": s.get("funding_context"),
                            "oi": s.get("oi_context")}
                           for s in sigs if s.get("oi_context")][:12]}


# ------------------------------------------------------------------- demo ---
def _demo_signals() -> list[dict]:
    now = _now()
    base = [
        dict(signal_id="demo_zec", symbol="ZEC/USDT", asset_class="crypto", mode="intraday",
             tier="B", score=78, direction="long", status="waiting_for_entry",
             entry_low=48.2, entry_high=48.7, stop_loss=46.9, tp1=50.1, tp2=51.8, tp3=53.4,
             news_supported=1, oi_context="price up + OI up", narrative="privacy coins",
             created_at=(now - timedelta(minutes=8)).isoformat()),
        dict(signal_id="demo_wld", symbol="WLD/USDT", asset_class="crypto", mode="intraday",
             tier="B", score=72, direction="long", status="triggered",
             entry_low=1.23, entry_high=1.25, stop_loss=1.19, tp1=1.32, tp2=1.38, tp3=1.46,
             news_supported=0, oi_context="clean", narrative="AI infra",
             entry_triggered_at=(now - timedelta(minutes=3)).isoformat(),
             created_at=(now - timedelta(minutes=30)).isoformat()),
        dict(signal_id="demo_rif", symbol="RIF/USDT", asset_class="crypto", mode="scalp",
             tier="B", score=70, direction="long", status="waiting_for_entry",
             entry_low=0.08, entry_high=0.082, stop_loss=0.077, tp1=0.086, tp2=0.09, tp3=0.095,
             news_supported=0, narrative="payments", created_at=(now - timedelta(minutes=12)).isoformat()),
        dict(signal_id="demo_amd", symbol="AMD", asset_class="stocks", mode="intraday",
             tier="B", score=74, direction="long", status="triggered",
             entry_low=544, entry_high=546, stop_loss=528, tp1=556, tp2=566, tp3=580,
             news_supported=1, narrative="semis",
             entry_triggered_at=(now - timedelta(minutes=40)).isoformat(),
             concentration_status="shadow_sector_cap",
             concentration_reason="3rd correlated exposure in semis long bucket — shadow",
             created_at=(now - timedelta(hours=1)).isoformat()),
        # late entry — triggered 22m ago on a crypto-intraday (very_late > 15m) → "DO NOT CHASE"
        dict(signal_id="demo_arb", symbol="ARB/USDT", asset_class="crypto", mode="intraday",
             tier="B", score=69, direction="long", status="triggered",
             entry_low=0.92, entry_high=0.94, stop_loss=0.88, tp1=0.99, tp2=1.04, tp3=1.12,
             news_supported=0, oi_context="clean", narrative="L2",
             entry_triggered_at=(now - timedelta(minutes=22)).isoformat(),
             created_at=(now - timedelta(minutes=27)).isoformat()),
        # blocked — C-tier never actionable → "BLOCKED"
        dict(signal_id="demo_doge", symbol="DOGE/USDT", asset_class="crypto", mode="intraday",
             tier="C", score=54, direction="long", status="waiting_for_entry",
             entry_low=0.16, entry_high=0.164, stop_loss=0.153, tp1=0.172, tp2=0.181, tp3=0.195,
             news_supported=0, oi_context="clean", narrative="memes",
             created_at=(now - timedelta(minutes=10)).isoformat()),
        # actionable crypto SWING (waiting for entry → actionable; longer freshness window)
        dict(signal_id="demo_eth", symbol="ETH/USDT", asset_class="crypto", mode="swing",
             tier="A", score=81, direction="long", status="waiting_for_entry",
             entry_low=3380, entry_high=3420, stop_loss=3250, tp1=3600, tp2=3820, tp3=4100,
             news_supported=1, oi_context="price up + OI up", narrative="L1",
             expected_rr_tp1=1.7, created_at=(now - timedelta(minutes=18)).isoformat()),
        dict(signal_id="demo_sui", symbol="SUI/USDT", asset_class="crypto", mode="swing",
             tier="A", score=83, direction="long", status="closed",
             entry_low=3.1, entry_high=3.2, stop_loss=2.95, tp1=3.5, tp2=3.8, tp3=4.2,
             news_supported=1, narrative="L1", final_outcome="win", final_r=2.0,
             mfe_r=2.4, mae_r=-0.3,
             entry_triggered_at=(now - timedelta(hours=6)).isoformat(),
             exit_at=(now - timedelta(hours=2)).isoformat(),
             created_at=(now - timedelta(hours=7)).isoformat()),
    ]
    return [_normalize(b, {k: b.get(k) for k in
                           ("entry_triggered_at", "final_outcome", "final_r", "exit_at")}
                       | {"max_favorable_excursion_r": b.get("mfe_r"),
                          "max_adverse_excursion_r": b.get("mae_r")},
                       {"concentration_status": b.get("concentration_status"),
                        "concentration_reason": b.get("concentration_reason")}) for b in base]


def _demo_candles() -> list[dict]:
    now = _now()
    out, price = [], 48.0
    for i in range(120):
        t = (now - timedelta(minutes=5 * (120 - i))).isoformat()
        price += (0.5 - (i % 7) / 7) * 0.15
        out.append({"t": t, "o": price, "h": price + 0.2, "l": price - 0.2, "c": price + 0.05, "v": 1000})
    return out


def _demo_health() -> list[dict]:
    # demo includes one WARNING component (OHLCV stale) to exercise warning rendering,
    # while the error list stays empty (no-error state) — both states are demonstrable.
    return [{"name": "Trading DB (read-only)", "ok": True, "detail": "demo dataset"},
            {"name": "Monitor / tracker", "ok": True, "detail": "demo: last tick 4m ago"},
            {"name": "Latest signal", "ok": True, "detail": "8m ago"},
            {"name": "Telegram alerts (24h)", "ok": True, "detail": "demo · 0 timeouts"},
            {"name": "OHLCV freshness", "ok": False, "detail": "demo: 42m ago (stale — warning)"}]
