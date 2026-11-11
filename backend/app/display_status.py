"""Display-status taxonomy for the Control Plane (read-only, presentation only).

Mirror of crypto-ai-desk `src/status/display_status.py`. Turns a normalized signal
dict into operator-facing display fields so the UI can stop showing a bare
`expired` or a context-free `+0R`. NEVER changes any trade field or the
authoritative `actionability` verdict — it only derives optional display labels
and is fail-open (missing fields → UNKNOWN/"unknown", never raises).
"""
from __future__ import annotations

from typing import Any

OPEN_ACTIVE = "OPEN_ACTIVE"
WAITING_FOR_ENTRY = "WAITING_FOR_ENTRY"
REVIEW_ONLY_SHADOW = "REVIEW_ONLY_SHADOW"
ENTERED_UNRESOLVED_EXPIRED = "ENTERED_UNRESOLVED_EXPIRED"
NO_ENTRY_EXPIRED = "NO_ENTRY_EXPIRED"
CLOSED_WIN = "CLOSED_WIN"
CLOSED_LOSS = "CLOSED_LOSS"
CLOSED_FLAT = "CLOSED_FLAT"
UNKNOWN_INCONSISTENT = "UNKNOWN_INCONSISTENT"

_OPEN_ENTERED = {"triggered", "tp1_hit", "tp2_hit"}
_WAITING = {"generated", "waiting_for_entry"}
_NO_ENTRY = {
    "missed_no_entry", "stale_before_entry", "entry_moved_away",
    "invalidated_before_entry", "cancelled_by_regime_change", "cancelled_by_news",
}
_NO_ENTRY_REASON = {
    "missed_no_entry": "price never touched the entry zone before the window ended",
    "stale_before_entry": "signal aged out waiting for entry (stale)",
    "entry_moved_away": "price ran away from the entry zone before a fill",
    "invalidated_before_entry": "invalidated before entry",
    "cancelled_by_regime_change": "cancelled — market regime changed",
    "cancelled_by_news": "cancelled — news event",
}

_LABELS = {
    OPEN_ACTIVE: "🟢 OPEN — entry filled, monitoring TP/SL",
    WAITING_FOR_ENTRY: "⏳ WAITING — entry not touched yet",
    REVIEW_ONLY_SHADOW: "👁 REVIEW/SHADOW — not actionable by policy",
    ENTERED_UNRESOLVED_EXPIRED: "⌛ EXPIRED AFTER ENTRY — entered, no TP/SL within window (not a missed entry)",
    NO_ENTRY_EXPIRED: "❌ NO ENTRY — price never reached the entry before the window ended",
    CLOSED_FLAT: "⚪ CLOSED FLAT 0R",
    UNKNOWN_INCONSISTENT: "⚠️ STATUS NEEDS REVIEW — inconsistent lifecycle fields",
}


def _to_float(v: Any):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def derive_display_status(sig: dict[str, Any]) -> dict[str, Any]:
    """Return display fields for a normalized Control-Plane signal dict. Fail-open."""
    status = str(sig.get("status") or "").strip().lower()
    final_outcome = str(sig.get("final_outcome") or "").strip().lower()
    final_r = _to_float(sig.get("final_r"))
    paper_outcome = str(sig.get("paper_execution_outcome") or "").strip().lower()
    paper_r = _to_float(sig.get("paper_execution_r"))
    paper_close_reason = str(sig.get("paper_close_reason") or "").strip()
    paper_terminal = paper_outcome in {"win", "loss", "flat", "breakeven", "expired"}
    effective_r = paper_r if paper_terminal and paper_r is not None else final_r
    r_source = "paper execution" if paper_terminal else "legacy touch"
    entry_triggered = bool(sig.get("entry_triggered_at"))
    act = (sig.get("actionability") or {})
    act_status = str(act.get("status") or "").lower()
    is_shadow = act_status in {"shadow", "blocked"}

    has_terminal_close = bool(final_outcome) and final_outcome not in {"expired", "not_triggered", "missed"}

    # The persisted Model-F result wins over the legacy touch tracker. In
    # particular, a placeholder ``final_outcome=expired`` cannot close an
    # authoritative OPEN paper position in the operator UI.
    if paper_terminal:
        if effective_r is not None and effective_r > 0:
            group, reason = CLOSED_WIN, f"closed by paper execution ({paper_close_reason or paper_outcome})"
        elif effective_r is not None and effective_r < 0:
            group, reason = CLOSED_LOSS, f"closed by paper execution ({paper_close_reason or paper_outcome})"
        else:
            group, reason = CLOSED_FLAT, f"closed flat by paper execution ({paper_close_reason or paper_outcome})"
    elif status == "ambiguous" or final_outcome == "ambiguous":
        group, reason = UNKNOWN_INCONSISTENT, "ambiguous lifecycle — needs review"
    elif status in _NO_ENTRY and entry_triggered:
        group, reason = UNKNOWN_INCONSISTENT, f"status '{status}' but entered — inconsistent"
    elif has_terminal_close or status in {"stopped", "tp3_hit"}:
        win_ish = (final_outcome == "win") or (status == "tp3_hit")
        loss_ish = (final_outcome == "loss") or (status == "stopped")
        if effective_r is not None and win_ish and effective_r < 0:
            group, reason = UNKNOWN_INCONSISTENT, "labelled win but final_r<0 — inconsistent"
        elif effective_r is not None and loss_ish and effective_r > 0:
            group, reason = UNKNOWN_INCONSISTENT, "labelled loss but final_r>0 — inconsistent"
        elif effective_r is not None and effective_r == 0:
            group, reason = CLOSED_FLAT, "closed flat at break-even (0R)"
        elif (effective_r is not None and effective_r > 0) or (effective_r is None and win_ish):
            group, reason = CLOSED_WIN, "closed at a winning R"
        elif (effective_r is not None and effective_r < 0) or (effective_r is None and loss_ish):
            group, reason = CLOSED_LOSS, "stopped out / closed at a losing R"
        else:
            group, reason = UNKNOWN_INCONSISTENT, "terminal close without resolvable R/outcome"
    elif status == "expired" and entry_triggered:
        group, reason = ENTERED_UNRESOLVED_EXPIRED, "entered but no TP/SL before the window ended"
    elif status == "expired":
        group, reason = NO_ENTRY_EXPIRED, "validity window ended without an entry touch"
    elif status in _NO_ENTRY:
        group, reason = NO_ENTRY_EXPIRED, _NO_ENTRY_REASON.get(status, "no entry")
    elif is_shadow and status in (_OPEN_ENTERED | _WAITING):
        group, reason = REVIEW_ONLY_SHADOW, "not actionable by policy (C-tier / scalp / shadow)"
    elif entry_triggered and status in _OPEN_ENTERED:
        group, reason = OPEN_ACTIVE, "entry filled, monitoring TP/SL"
    elif status in _WAITING:
        group, reason = WAITING_FOR_ENTRY, "actionable candidate, entry not touched yet"
    else:
        group, reason = UNKNOWN_INCONSISTENT, f"unmapped status '{status or 'n/a'}'"

    r_policy = {
        CLOSED_WIN: "terminal", CLOSED_LOSS: "terminal", CLOSED_FLAT: "terminal_flat",
        ENTERED_UNRESOLVED_EXPIRED: "unresolved_expiry", NO_ENTRY_EXPIRED: "na_no_entry",
        WAITING_FOR_ENTRY: "na_waiting", REVIEW_ONLY_SHADOW: "na_shadow",
        OPEN_ACTIVE: "unrealized",
    }.get(group, "na_unknown")

    # Build win/loss label locally with sign-correct R (never "+-"). final_r is
    # guaranteed positive for WIN / negative for LOSS by the guards above.
    if group == CLOSED_WIN:
        operator_label = f"✅ CLOSED WIN{f' {effective_r:+.1f}R ({r_source})' if effective_r is not None else ''}"
    elif group == CLOSED_LOSS:
        operator_label = f"🔴 CLOSED LOSS{f' {effective_r:+.1f}R ({r_source})' if effective_r is not None else ''}"
    else:
        operator_label = _LABELS.get(group, _LABELS[UNKNOWN_INCONSISTENT])

    return {
        "display_status": group.lower(),
        "display_group": group,
        "display_reason": reason,
        "display_r_source": r_source,
        "paper_outcome_authoritative": paper_terminal,
        "operator_label": operator_label,
        "entry_touched": entry_triggered,
        "is_shadow_or_review": is_shadow,
        "is_active_for_operator": group == OPEN_ACTIVE,
        "r_display_policy": r_policy,
    }
