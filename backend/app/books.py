"""Canonical trade-book read-model for the Control Plane.

Turns the desk's per-signal rows (one normalized dict per proposed_signal, each
carrying its LATEST signal_outcomes row + alert delivery state) into honest,
**deduplicated economic trades**, classified into books, with realized R counted
**only from terminal close outcomes**.

WHY THIS EXISTS — the old dashboard summed `final_r` over the last 200 raw
signals (no day boundary, no dedup, shadow mixed in, expired confused with flat)
→ it showed e.g. -26R when the real Operator book was ≈ -1R over 2 days.

Books
-----
* operator : actionable A/B, entry alert actually **delivered** to Telegram
             (status='sent'). "What the operator saw / their book."
* paper    : actionable-by-policy (A/B, not scalp/C-tier/stocks-swing-invest,
             not routed to shadow) — delivered OR delivery-failed. Superset of
             operator; the operator-vs-paper gap = delivery losses.
* shadow   : C-tier, crypto scalp, stocks swing/invest, sector-cap / late /
             guard-blocked / review-only / advisory. Never the operator's book.
* research : everything (broad, explicitly not-actionable analysis view).

READ-ONLY. Never writes the trading DB; never changes scoring/TP-SL/entry/
routing/actionability. Pure measurement + display.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

# Outcome classes
WIN, LOSS, FLAT = "win", "loss", "flat"
EXPIRED_UNRESOLVED = "expired_unresolved"   # entry filled, no TP/SL before window
NO_ENTRY = "no_entry"                        # price never reached entry / stale / moved away
OPEN = "open"
WAITING = "waiting"
NEEDS_REVIEW = "needs_review"                # lifecycle fields contradict / ambiguous
SHADOW_OPEN = "shadow_open"

_TERMINAL_REALIZED = {WIN, LOSS, FLAT}
_DELIVERY_SHADOW = {"shadow_only", "shadow_sector_cap", "late_shadow"}


def _parse(ts: Any) -> datetime | None:
    if not ts:
        return None
    try:
        s = str(ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _f(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- gates ------
def _gates_ok(sig: dict) -> bool:
    """Actionable-by-policy gate (mirrors the desk's decide_paper_entry gates).
    Pure read: never changes routing — only decides which book a row is counted in."""
    tier = str(sig.get("tier") or "").upper()
    asset = str(sig.get("asset_class") or "crypto").lower()
    mode = str(sig.get("mode") or "").lower()
    if tier not in ("A", "B"):
        return False
    if asset == "crypto" and mode == "scalp":
        return False
    if asset == "stocks" and mode in ("swing", "invest"):
        return False
    return True


def derive_trade_book(sig: dict) -> dict:
    """Classify one signal into a book. Returns {book, delivered, delivery}.

    book ∈ operator | paper | shadow. operator ⊆ paper (operator = delivered paper).
    """
    delivery = sig.get("entry_alert_status")
    act = (sig.get("actionability") or {}).get("status")
    # Routed-to-shadow by delivery, or blocked/shadow/late by actionability, or
    # fails the actionable-by-policy gate → Shadow book.
    if delivery in _DELIVERY_SHADOW or act in ("shadow", "blocked", "late") or not _gates_ok(sig):
        return {"book": "shadow", "delivered": False, "delivery": delivery or act or "shadow"}
    delivered = bool(sig.get("entry_alert_sent")) or delivery == "sent"
    return {"book": "operator" if delivered else "paper",
            "delivered": delivered, "delivery": delivery or ("sent" if delivered else "not_sent")}


def in_book(sig: dict, book: str) -> bool:
    b = derive_trade_book(sig)["book"]
    if book == "operator":
        return b == "operator"
    if book == "paper":
        return b in ("operator", "paper")          # all actionable-by-policy
    if book == "shadow":
        return b == "shadow"
    if book == "research":
        return True                                 # everything
    return False


# ------------------------------------------------------------- outcomes ------
def outcome_class(sig: dict) -> str:
    """Lifecycle/outcome class. Prefers the canonical display_status group, then
    falls back to raw fields. NEVER treats expired as a realized loss/flat."""
    grp = str(sig.get("display_status") or "").lower()
    mapping = {
        "closed_win": WIN, "closed_loss": LOSS, "closed_flat": FLAT,
        "entered_unresolved_expired": EXPIRED_UNRESOLVED,
        "no_entry_expired": NO_ENTRY,
        "open_active": OPEN, "waiting_for_entry": WAITING,
        "review_only_shadow": SHADOW_OPEN,
        "unknown_inconsistent": NEEDS_REVIEW,
    }
    if grp in mapping:
        return mapping[grp]
    # fallback from raw fields
    fo = str(sig.get("final_outcome") or "").lower()
    r = _f(sig.get("final_r"))
    entered = bool(sig.get("entry_triggered")) or bool(sig.get("entry_triggered_at"))
    if fo == "win":
        return WIN if (r is None or r > 0) else NEEDS_REVIEW
    if fo == "loss":
        return LOSS if (r is None or r < 0) else NEEDS_REVIEW
    if fo == "expired":
        return EXPIRED_UNRESOLVED if entered else NO_ENTRY
    if fo in ("flat",) or (fo and r == 0):
        return FLAT
    if fo in ("not_triggered",):
        return NO_ENTRY
    if entered:
        return OPEN
    return WAITING


def realized_r(sig: dict) -> float | None:
    """TOUCH-based realized R — old `final_r` (highest TP touched). OPTIMISTIC /
    signal-quality only; NOT the authoritative paper PnL. Use paper_execution_r
    for the honest number. Kept for the secondary 'Recorded Touch R' card."""
    oc = outcome_class(sig)
    if oc not in _TERMINAL_REALIZED:
        return None
    if oc == FLAT:
        return 0.0
    return _f(sig.get("final_r"))


# Alias: the touch number is exactly the old realized_r. Named explicitly so the
# read-model and UI can talk about "touch R" vs "paper execution R" unambiguously.
def touch_r(sig: dict) -> float | None:
    return realized_r(sig)


# Model F thresholds (mirror src/execution/paper_execution_accounting.py on the
# desk side — early_mfe_protection_v1). Kept in sync; pinned by a backend test.
_ARM_BE_AT_R = 0.6
_LOCK_AT_R = 1.0
_LOCK_LEVEL_R = 0.5
PAPER_RISK_MODEL = "early_mfe_protection_v1"


def paper_execution_r(sig: dict) -> float | None:
    """AUTHORITATIVE paper PnL — Model F (early MFE-armed protection).

    Real-time triggers reconstructed from the recorded path: stop->BE once price
    is +0.6R favorable, lock +0.5R once +1R favorable, runner to TP3. Resolves
    entered trades only (incl. expired-after-entry -> closed at protected level).
    Returns None for not-entered / open / waiting (no realized paper PnL yet).

    Mirrors src/execution/paper_execution_accounting.early_mfe_protection_v1.
    """
    # A persisted Model-F result from the desk is authoritative. Do not
    # re-derive it from legacy touch fields in the Control Plane.
    recorded_outcome = str(sig.get("paper_execution_outcome") or "").lower()
    recorded = _f(sig.get("paper_execution_r"))
    if recorded_outcome in {"win", "loss", "flat", "breakeven", "expired"} and recorded is not None:
        return recorded

    oc = outcome_class(sig)
    entered = bool(sig.get("entry_triggered")) or bool(sig.get("entry_triggered_at"))
    if not entered:
        return None
    # Resolved = terminal realized OR entered-then-expired (Model F closes it at
    # the protected level). Open/waiting/no-entry/needs-review -> not yet PnL.
    if oc not in (_TERMINAL_REALIZED | {EXPIRED_UNRESOLVED}):
        return None
    c3 = bool(sig.get("tp3_hit"))
    st = oc == LOSS or bool(sig.get("stop_hit"))
    exp = oc == EXPIRED_UNRESOLVED
    mfe = _f(sig.get("mfe_r"))
    if mfe is None:
        return None  # cannot compute -> caller flags as unavailable (no silent 0)
    m0 = _f(sig.get("final_r"))
    m0 = 0.0 if m0 is None else m0
    if c3:
        return round(m0, 4)
    if mfe >= _LOCK_AT_R:
        return round(_LOCK_LEVEL_R if (st or exp) else m0, 4)
    if mfe >= _ARM_BE_AT_R:
        return round(0.0 if (st or exp) else m0, 4)
    return round(-1.0 if st else 0.0, 4)


def paper_execution_available(sig: dict) -> bool:
    """True if a resolved, entered trade has the inputs to compute paper PnL."""
    oc = outcome_class(sig)
    entered = bool(sig.get("entry_triggered")) or bool(sig.get("entry_triggered_at"))
    if not entered or oc not in (_TERMINAL_REALIZED | {EXPIRED_UNRESOLVED}):
        return True  # not a resolved trade -> nothing to be 'missing'
    return _f(sig.get("mfe_r")) is not None


def paper_exec_flags(sig: dict) -> dict:
    """Per-trade Model F annotations for the UI/timeline (stop moved, BE/lock
    armed, giveback). Pure display."""
    mfe = _f(sig.get("mfe_r")) or 0.0
    oc = outcome_class(sig)
    st = oc == LOSS or bool(sig.get("stop_hit"))
    exp = oc == EXPIRED_UNRESOLVED
    armed = mfe >= _ARM_BE_AT_R
    locked = mfe >= _LOCK_AT_R
    giveback = bool(armed and (st or exp) and not bool(sig.get("tp3_hit")))
    pe = paper_execution_r(sig)
    tr = touch_r(sig)
    # Paper display annotations (no routing change): weak-cohort warn label.
    playbook = str(sig.get("setup_type") or sig.get("playbook") or "")
    cohort_warning = playbook == "crypto_intraday_catalyst_or_momentum"
    return {
        "risk_model": PAPER_RISK_MODEL,
        # LEGACY touch metric — optimistic, NOT PnL. Exposed under its explicit name only.
        "legacy_touch_r": tr,
        "paper_execution_r": pe,
        "protection_armed": bool(armed),
        "protection_level_r": 0.0 if armed else None,
        "lock_armed": bool(locked),
        "lock_level_r": _LOCK_LEVEL_R if locked else None,
        "stop_moved": bool(armed),
        "giveback": giveback,
        "highest_tp_touched": 3 if sig.get("tp3_hit") else 2 if sig.get("tp2_hit") else 1 if sig.get("tp1_hit") else 0,
        "original_stop_avoided": bool(armed and (st or exp)),  # BE/lock instead of -1R
        "paper_execution_available": paper_execution_available(sig),
        "cohort_warning": cohort_warning,                      # weak chase-long cohort (display only)
        "paper_feature_tags": (["model_f"] if pe is not None else [])
            + (["be_protected"] if armed else []) + (["profit_lock"] if locked else [])
            + (["giveback_protected"] if giveback else []) + (["cohort_warn"] if cohort_warning else []),
    }


def is_closed(sig: dict) -> bool:
    """A trade is 'closed' for the Closed tab if it has any terminal resolution,
    including expired-after-entry (shown as unresolved, not as PnL)."""
    return outcome_class(sig) in (_TERMINAL_REALIZED | {EXPIRED_UNRESOLVED, NO_ENTRY, NEEDS_REVIEW})


def close_time(sig: dict) -> datetime | None:
    return (_parse(sig.get("exit_at")) or _parse(sig.get("close_alert_at"))
            or _parse(sig.get("checked_at")))


# --------------------------------------------------------- economic dedup ----
def _round_zone(sig: dict) -> Any:
    """Rounded entry zone — same setup re-registered across cycles shares it."""
    for k in ("entry_trigger", "suggested_entry", "entry_low"):
        v = _f(sig.get(k))
        if v:
            # round to 4 significant-ish figures to absorb tiny re-quote drift
            import math
            if v == 0:
                return 0.0
            digits = 3 - int(math.floor(math.log10(abs(v))))
            return round(v, max(0, digits))
    return None


def economic_trade_key(sig: dict) -> tuple:
    """Deterministic key collapsing duplicate signal_ids for ONE real setup.

    Same symbol+class+mode+direction+tier+playbook+rounded-entry within the same
    entry-day bucket = one economic trade.
    """
    t = close_time(sig) or _parse(sig.get("entry_triggered_at")) or _parse(sig.get("created_at"))
    day = t.date().isoformat() if t else "?"
    return (
        str(sig.get("symbol") or "?"),
        str(sig.get("asset_class") or "crypto").lower(),
        str(sig.get("mode") or "").lower(),
        str(sig.get("direction") or "").lower(),
        str(sig.get("tier") or "").upper(),
        str(sig.get("setup_type") or sig.get("playbook") or ""),
        _round_zone(sig),
        day,
    )


# representative-priority: terminal realized > expired-unresolved > open > waiting > other
_PRIO = {WIN: 5, LOSS: 5, FLAT: 5, EXPIRED_UNRESOLVED: 4, NEEDS_REVIEW: 4,
         OPEN: 3, NO_ENTRY: 2, WAITING: 1, SHADOW_OPEN: 1}


def collapse_economic_trades(rows: Iterable[dict]) -> list[dict]:
    """Collapse duplicate signal_ids into one representative economic trade each.

    The representative is the most-resolved row (terminal > expired > open …),
    tie-broken by latest checked_at. Adds `duplicates_collapsed_count` and
    `duplicate_signal_ids` for the detail drawer / debug.
    """
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault(economic_trade_key(r), []).append(r)
    out: list[dict] = []
    for key, members in groups.items():
        def rank(m):
            return (_PRIO.get(outcome_class(m), 0),
                    (_parse(m.get("checked_at")) or datetime.min.replace(tzinfo=timezone.utc)))
        members_sorted = sorted(members, key=rank, reverse=True)
        rep = dict(members_sorted[0])
        rep["duplicates_collapsed_count"] = len(members) - 1
        rep["duplicate_signal_ids"] = [m.get("signal_id") for m in members_sorted[1:]]
        rep["economic_trade_key"] = "|".join(str(x) for x in key)
        out.append(rep)
    return out


# ---------------------------------------------------------- query helpers ----
def _within(sig: dict, since: datetime | None) -> bool:
    if since is None:
        return True
    ct = close_time(sig)
    return bool(ct and ct >= since)


def get_closed_trades(rows: Iterable[dict], book: str = "operator",
                      hours: float | None = None) -> list[dict]:
    """Deduped closed economic trades for a book, optionally within `hours`."""
    pool = [r for r in rows if in_book(r, book)]
    trades = collapse_economic_trades(pool)
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)) if hours else None
    return [t for t in trades if is_closed(t) and _within(t, since)]


def closed_trade_analytics(trades: Iterable[dict], ledger_by_signal_id: dict[str, dict] | None = None) -> dict:
    """Build a read-only PnL curve and day buckets for already-filtered closed trades.

    USD net from paper_portfolio_ledger is preferred. Paper Execution R remains a
    secondary diagnostic and the fallback when no USD ledger row exists.
    """
    ledger_by_signal_id = ledger_by_signal_id or {}
    rows = []
    for t in trades:
        ct = close_time(t)
        if not ct:
            continue
        ids = [str(t.get("signal_id") or "")]
        ids.extend(str(x) for x in (t.get("duplicate_signal_ids") or []) if x)
        led = next((ledger_by_signal_id.get(i) for i in ids if i in ledger_by_signal_id), None)
        usd = _f((led or {}).get("net_pnl_usdt"))
        pr = paper_execution_r(t)
        rows.append({
            "signal_id": t.get("signal_id"),
            "symbol": t.get("symbol"),
            "asset_class": t.get("asset_class"),
            "mode": t.get("mode"),
            "direction": t.get("direction"),
            "outcome_class": outcome_class(t),
            "close_time": ct,
            "net_pnl_usd": usd,
            "paper_execution_r": pr,
        })
    rows.sort(key=lambda r: r["close_time"])

    cum_usd = 0.0
    cum_r = 0.0
    peak_usd = 0.0
    peak_r = 0.0
    max_dd_usd = 0.0
    max_dd_r = 0.0
    series = []
    days: dict[str, dict] = {}
    usd_count = 0

    for r in rows:
        usd = r["net_pnl_usd"]
        pr = r["paper_execution_r"]
        if usd is not None:
            usd_count += 1
            cum_usd += usd
        if pr is not None:
            cum_r += pr
        peak_usd = max(peak_usd, cum_usd)
        peak_r = max(peak_r, cum_r)
        max_dd_usd = min(max_dd_usd, cum_usd - peak_usd)
        max_dd_r = min(max_dd_r, cum_r - peak_r)
        day = r["close_time"].date().isoformat()
        bucket = days.setdefault(day, {
            "date": day, "trades": 0, "net_pnl_usd": 0.0, "net_r": 0.0,
            "wins": 0, "losses": 0, "flat": 0, "missing_usd": 0, "trade_ids": [],
        })
        bucket["trades"] += 1
        bucket["trade_ids"].append(r["signal_id"])
        if usd is None:
            bucket["missing_usd"] += 1
        else:
            bucket["net_pnl_usd"] += usd
        if pr is not None:
            bucket["net_r"] += pr
        if r["outcome_class"] == WIN:
            bucket["wins"] += 1
        elif r["outcome_class"] == LOSS:
            bucket["losses"] += 1
        elif r["outcome_class"] == FLAT:
            bucket["flat"] += 1
        series.append({
            "ts": r["close_time"].isoformat(),
            "signal_id": r["signal_id"],
            "symbol": r["symbol"],
            "asset_class": r["asset_class"],
            "mode": r["mode"],
            "direction": r["direction"],
            "outcome_class": r["outcome_class"],
            "trade_pnl_usd": round(usd, 2) if usd is not None else None,
            "trade_r": round(pr, 3) if pr is not None else None,
            "cumulative_usd": round(cum_usd, 2),
            "cumulative_r": round(cum_r, 3),
        })

    day_rows = []
    for d in sorted(days):
        b = days[d]
        b["net_pnl_usd"] = round(b["net_pnl_usd"], 2)
        b["net_r"] = round(b["net_r"], 3)
        day_rows.append(b)

    return {
        "available": True,
        "metric": "usd_net" if usd_count else "paper_execution_r",
        "pnl_usd_available": usd_count > 0,
        "trades": len(rows),
        "usd_trades": usd_count,
        "missing_usd_trades": len(rows) - usd_count,
        "total_pnl_usd": round(cum_usd, 2),
        "total_r": round(cum_r, 3),
        "max_drawdown_usd": round(max_dd_usd, 2),
        "max_drawdown_r": round(max_dd_r, 3),
        "series": series,
        "days": day_rows,
        "note": "USD net comes from paper_portfolio_ledger when available; R is Paper Execution R.",
    }


def _summ(trades: list[dict]) -> dict:
    real = [realized_r(t) for t in trades]              # touch-based (optimistic)
    real = [r for r in real if r is not None]
    paper = [paper_execution_r(t) for t in trades]      # Model F (authoritative paper)
    paper = [r for r in paper if r is not None]
    classes = [outcome_class(t) for t in trades]
    flags = [paper_exec_flags(t) for t in trades]
    giveback = sum(1 for f in flags if f["giveback"])
    be_scratch = sum(1 for t in trades if paper_execution_r(t) == 0.0
                     and (outcome_class(t) in (LOSS, EXPIRED_UNRESOLVED)))
    protected = sum(1 for f in flags if f["protection_armed"] and f["paper_execution_r"] is not None)
    stops_avoided = sum(1 for f in flags if f["original_stop_avoided"])
    unavailable = sum(1 for t in trades if not paper_execution_available(t))
    touch_sum = round(sum(real), 2)
    paper_sum = round(sum(paper), 2)
    return {
        # authoritative paper R (Model F). USD net (paper_portfolio_ledger.net_pnl_usdt) is the
        # authoritative PROFITABILITY — this R is the auxiliary paper-R diagnostic.
        "paper_execution_r": paper_sum,
        "paper_resolved_n": len(paper),
        # LEGACY touch metric (old final_r, highest-TP-touched) — OPTIMISTIC, signal-quality only.
        # NOT PnL. Never summed as profit / equity / win-rate anywhere authoritative. The old
        # `touch_r` / `realized_r` keys are removed: this is the only name it is exposed under.
        "legacy_touch_r": touch_sum,
        "resolved_n": len(real),
        # touch overstatement vs the honest paper R (touch − paper; can be negative when
        # protection adds value). Diagnostic only.
        "touch_minus_paper_r": round(touch_sum - paper_sum, 2),
        "giveback_n": giveback,
        "be_scratch_n": be_scratch,
        "protected_n": protected,
        "original_stops_avoided_n": stops_avoided,
        "paper_unavailable_n": unavailable,
        "win": classes.count(WIN), "loss": classes.count(LOSS), "flat": classes.count(FLAT),
        "expired_unresolved": classes.count(EXPIRED_UNRESOLVED),
        "no_entry": classes.count(NO_ENTRY),
        "needs_review": classes.count(NEEDS_REVIEW),
        "trades_n": len(trades),
    }


_CLOSE_REASON = {
    WIN: "tp_hit", LOSS: "stop_hit", FLAT: "flat_exit",
    EXPIRED_UNRESOLVED: "expired_after_entry", NO_ENTRY: "no_entry",
    NEEDS_REVIEW: "ambiguous_needs_review", OPEN: "open", WAITING: "waiting",
    SHADOW_OPEN: "shadow",
}
_PLAIN = {
    "tp_hit": "TP hit: price reached target before stop.",
    "stop_hit": "Closed by stop: price touched stop before TP.",
    "flat_exit": "Closed flat: resolved at ~breakeven (0R).",
    "expired_after_entry": "Expired after entry: entry filled, no TP/SL before the validity window.",
    "no_entry": "No-entry: price never reached the entry zone (or stale / moved away).",
    "ambiguous_needs_review": "Needs review: lifecycle fields contradict or same-candle ambiguous.",
    "open": "Open: entry filled, trade still live.",
    "waiting": "Waiting: pending entry trigger.",
    "shadow": "Shadow: blocked by policy, not sent to operator.",
}


def close_reason(sig: dict) -> str:
    return _CLOSE_REASON.get(outcome_class(sig), "open")


def plain_explanation(sig: dict) -> str:
    return _PLAIN.get(close_reason(sig), "")


def near_winner_expired(rows: Iterable[dict], book: str = "operator",
                        hours: float | None = None, mfe_threshold: float = 0.8) -> list[dict]:
    """Diagnostic ONLY (does not change exits): expired-after-entry trades whose
    favorable excursion reached >= mfe_threshold R before the window closed."""
    out = []
    for t in get_closed_trades(rows, book=book, hours=hours):
        if outcome_class(t) != EXPIRED_UNRESOLVED:
            continue
        mfe = _f(t.get("mfe_r"))
        if mfe is not None and mfe >= mfe_threshold:
            out.append(t)
    return sorted(out, key=lambda x: -(_f(x.get("mfe_r")) or 0))


def get_dashboard_summary(rows: Iterable[dict]) -> dict:
    """Honest per-book dashboard summary. Today R = Operator book, deduped,
    terminal realized only, shadow excluded — with explicit windows."""
    rows = list(rows)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    windows = {"today": today_start, "h48": now - timedelta(hours=48), "d7": now - timedelta(days=7)}

    def book_block(book: str) -> dict:
        pool = [r for r in rows if in_book(r, book)]
        trades = collapse_economic_trades(pool)
        block = {"book": book}
        for wname, since in windows.items():
            block[wname] = _summ([t for t in trades if is_closed(t) and _within(t, since)])
        # live state counts (current, not windowed)
        classes = [outcome_class(t) for t in trades]
        block["open_now"] = classes.count(OPEN)
        block["waiting_now"] = classes.count(WAITING)
        block["duplicates_collapsed"] = sum(t.get("duplicates_collapsed_count", 0) for t in trades)
        return block

    operator = book_block("operator")
    paper = book_block("paper")
    shadow = book_block("shadow")

    # delivery gaps = ENTERED actionable trades that were NOT delivered to the
    # operator (an entry alert that errored / was routed late). Waiting A/B
    # signals that never triggered are not counted — they are not trades yet.
    delivery_gaps = 0
    for r in rows:
        entered = bool(r.get("entry_triggered")) or bool(r.get("entry_triggered_at"))
        if not entered:
            continue
        c = derive_trade_book(r)
        st = str(c.get("delivery") or "")
        if c["book"] == "paper" and not c["delivered"] and (st.startswith("error") or st.startswith("failed") or st in ("not_sent",)):
            delivery_gaps += 1

    return {
        "headline": {
            # Authoritative PROFITABILITY is USD net (paper_portfolio_ledger.net_pnl_usdt, surfaced
            # by the portfolio read-model). This R headline is the auxiliary paper-R diagnostic.
            "today_paper_execution_r": operator["today"]["paper_execution_r"],
            "h48_paper_execution_r": operator["h48"]["paper_execution_r"],
            "d7_paper_execution_r": operator["d7"]["paper_execution_r"],
            "risk_model": PAPER_RISK_MODEL,
            # LEGACY touch metric — optimistic, signal-quality ONLY, NOT PnL. Explicitly named.
            "today_legacy_touch_r": operator["today"]["legacy_touch_r"],
            "h48_legacy_touch_r": operator["h48"]["legacy_touch_r"],
            "today_touch_minus_paper_r": operator["today"]["touch_minus_paper_r"],
            # back-compat alias (old key) — now points at the honest paper number
            "today_operator_r": operator["today"]["paper_execution_r"],
            "h48_operator_r": operator["h48"]["paper_execution_r"],
            "today_paper_unavailable_n": operator["today"]["paper_unavailable_n"],
            "authoritative_metric": "usd_net_after_fees_slippage_funding",
            "label": ("Authoritative profitability = USD net (Paper Equity / Net PnL, after "
                      "exchange fees + slippage + funding). Paper Execution R (Model F) is the "
                      "auxiliary paper-R metric, Operator book, deduped, entered+resolved, shadow "
                      "excluded (UTC day). 'Legacy Touch R' is the old highest-TP-touched number — "
                      "optimistic, signal-quality only, NEVER PnL."),
        },
        "operator": operator, "paper": paper, "shadow": shadow,
        "delivery_gaps": delivery_gaps,
        "generated_at": now.isoformat(),
    }
