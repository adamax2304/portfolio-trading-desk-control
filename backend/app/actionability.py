"""Single source of truth for 'can the operator take this signal, and why / why not'.

Mirrors the crypto-ai-desk rules WITHOUT importing it (separate app, reads the DB):
  * crypto scalp           → shadow only, never actionable
  * stocks scalp           → research/backtest only, never actionable
  * C-tier / rejected      → not actionable
  * stocks swing/invest    → deprecated/removed (old pipeline); new framework is shadow-only
  * proxy/sector shadow    → not actionable (concentration guard)
  * late / very-late entry → DO NOT CHASE (timeframe-aware freshness)
Everything else is actionable (paper always; manual-live only if a separate gate passes).
"""

from __future__ import annotations

from datetime import datetime, timezone

# timeframe-aware freshness (minutes): (fresh<=, acceptable<=, very_late_over)
FRESHNESS = {
    ("crypto", "intraday"): (2, 5, 15),
    ("crypto", "short"): (2, 5, 15),
    ("crypto", "scalp"): (2, 5, 15),
    ("crypto", "swing"): (15, 60, 240),
    ("stocks", "intraday"): (20, 30, 45),
    ("stocks", "swing"): (60, 240, 1440),
}
_DEFAULT_FRESH = (2, 5, 15)
_TERMINAL = {"tp1_hit", "tp2_hit", "tp3_hit", "stopped", "expired", "missed_no_entry",
             "ambiguous", "closed", "invalidated_before_entry",
             # entry never (validly) happened → not chaseable, must not show Manual Entry
             "stale_before_entry", "entry_moved_away"}


def _parse(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def freshness(asset_class, mode, entry_triggered_at, now=None):
    """Return (label, age_min|None, actionable_bool). 'waiting' if no entry yet."""
    if not entry_triggered_at:
        return ("waiting for entry", None, True)
    now = now or datetime.now(timezone.utc)
    t = _parse(entry_triggered_at)
    if t is None:
        return ("unknown", None, False)
    age = max(0.0, (now - t).total_seconds()) / 60.0
    fresh_m, ok_m, late_m = FRESHNESS.get(((asset_class or "crypto").lower(), (mode or "").lower()), _DEFAULT_FRESH)
    note = " (15m candle floor — price check)" if (asset_class == "stocks" and mode == "intraday") else ""
    if age <= fresh_m:
        return (f"fresh {age*60:.0f}s" if age < 1 else f"fresh {age:.1f}m", age, True)
    if age <= ok_m:
        return (f"acceptable {age:.0f}m{note}", age, True)
    if age <= late_m:
        return (f"late {age:.0f}m — check price{note}", age, True)
    return (f"very late {age:.0f}m — DO NOT CHASE{note}", age, False)


def classify(sig: dict, now=None) -> dict:
    """Derive actionability for a normalized signal dict.

    Returns: {actionable, status, blocked_reason, reasons[], badges[], freshness{...}}.
    `status` ∈ actionable | shadow | late | blocked | closed.
    """
    asset = (sig.get("asset_class") or "crypto").lower()
    mode = (sig.get("mode") or "").lower()
    tier = (sig.get("tier") or "").upper()
    sstatus = (sig.get("status") or "").lower()
    conc = (sig.get("concentration_status") or "").lower()
    reasons: list[str] = []
    badges: list[str] = []

    fl_label, fl_age, fl_ok = freshness(asset, mode, sig.get("entry_triggered_at"), now)
    fresh = {"label": fl_label, "age_min": fl_age, "ok": fl_ok}

    # terminal first — a CLOSED trade is not chaseable; the "very late — DO NOT CHASE"
    # chase-guard is for OPEN trades only. Surface a neutral closed-freshness so the UI
    # never shows the chase warning on an already-finished trade (MSTR fix, PART 9).
    if sstatus in _TERMINAL:
        closed_fresh = {"label": f"closed ({sstatus})", "age_min": fl_age, "ok": True}
        return {"actionable": False, "status": "closed", "blocked_reason": f"status={sstatus}",
                "reasons": [f"trade {sstatus}"], "badges": [], "freshness": closed_fresh}

    # hard blocks (cannot ever be manually actionable)
    if asset == "crypto" and mode == "scalp":
        reasons.append("crypto scalp is shadow-only (12mo backtest net-negative)")
        return _shadow(reasons, fresh, "scalp_shadow")
    if asset == "stocks" and mode == "scalp":
        reasons.append("stocks scalp is research/backtest only")
        return _shadow(reasons, fresh, "scalp_shadow")
    if tier in ("C", "REJECTED", ""):
        reasons.append(f"tier {tier or '?'} — not actionable")
        return {"actionable": False, "status": "blocked", "blocked_reason": "c_tier_or_rejected",
                "reasons": reasons, "badges": badges, "freshness": fresh}
    if asset == "stocks" and mode in ("swing", "invest"):
        reasons.append("old stocks swing/invest deprecated/removed; "
                       "new stocks position framework is shadow-only")
        # blocked_reason kept as mode_paused for API/frontend compatibility.
        return {"actionable": False, "status": "blocked", "blocked_reason": "mode_paused",
                "reasons": reasons, "badges": badges, "freshness": fresh}
    if conc in ("shadow_proxy_duplicate", "shadow_sector_cap"):
        reasons.append(sig.get("concentration_reason") or "concentration shadow")
        return _shadow(reasons, fresh, "sector_cap" if "sector" in conc else "proxy_duplicate")

    # late entry → not actionable (do not chase)
    if not fl_ok:
        reasons.append(fl_label)
        return {"actionable": False, "status": "late", "blocked_reason": "late_entry",
                "reasons": reasons, "badges": badges, "freshness": fresh}

    # actionable — build informative badges
    if int(sig.get("news_supported") or 0) > 0:
        badges.append("Catalyst-backed")
    else:
        badges.append("Technical-only")
    if conc == "half_size":
        badges.append("Correlation: half-size")
    elif conc in ("actionable", "", "unknown_bucket_actionable", "not_applicable"):
        badges.append("Correlation OK")
    oi = (sig.get("oi_context") or "").lower()
    if "squeeze" in oi:
        badges.append("Squeeze risk")
    else:
        badges.append("Funding/OI OK")
    badges.append(f"Freshness: {fl_label}")
    badges.append("Manual actionable")
    reasons.append("passes tier/mode/freshness/shadow/concentration gates")
    return {"actionable": True, "status": "actionable", "blocked_reason": None,
            "reasons": reasons, "badges": badges, "freshness": fresh}


def _shadow(reasons, fresh, reason_code):
    return {"actionable": False, "status": "shadow", "blocked_reason": reason_code,
            "reasons": reasons, "badges": ["SHADOW ONLY"], "freshness": fresh}
