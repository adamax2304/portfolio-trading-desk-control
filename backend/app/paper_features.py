"""Paper Feature Flags — read-model for the Control Plane "Paper Features" panel.

Single, honest descriptor of which PAPER features are active (accounting/display/
advisory), which are kept shadow/measuring, which are archived, and which are
dangerous/locked. READ-ONLY. Mirrors `crypto-ai-desk/config/paper_features.yaml`
+ `config/cohort_guard.yaml`. NOTHING here enables live/auto-live/execution.
"""
from __future__ import annotations

import os

try:
    import yaml  # optional; we fall back to the static descriptor if absent
except Exception:  # pragma: no cover
    yaml = None

# Static, audited descriptor (source of truth = config/paper_features.yaml). Each
# entry: key, label, state, affects_trades, evidence, decision_date.
_FEATURES = [
    {"key": "model_f_paper_execution", "label": "Model F — paper execution R",
     "state": "active_paper_accounting", "affects_trades": False,
     "evidence": "replay actionable touch +6.2R → +74.1R, PF~1.43 (forward-validation pending)",
     "decision_date": "2026-06-24"},
    {"key": "touch_r_optimistic_label", "label": "Touch R relabelled optimistic",
     "state": "active_paper_display", "affects_trades": False,
     "evidence": "touch overstated PnL by ~+100..+143R vs realistic exits", "decision_date": "2026-06-24"},
    {"key": "lifecycle_status_clarity", "label": "Lifecycle status clarity",
     "state": "active_paper_display", "affects_trades": False,
     "evidence": "expired split + lifecycle R; UNKNOWN 87→3", "decision_date": "2026-06-19"},
    {"key": "risk_guard_warnings", "label": "Risk-guard warnings (alert-only)",
     "state": "active_advisory", "affects_trades": False,
     "evidence": "circuit-breaker/sector-cap/correlation/profit-hint as warnings; fail-open, never block",
     "decision_date": "2026-06-19"},
    {"key": "catalyst_labels_refresh", "label": "Catalyst label refresh + integrity",
     "state": "active_advisory", "affects_trades": False,
     "evidence": "fixes scan-time ~5h news under-fire; data-quality", "decision_date": "2026-06-19"},
    {"key": "cohort_guard_warn", "label": "Weak-cohort warn label",
     "state": "active_paper_display", "affects_trades": False,
     "evidence": "crypto_intraday_catalyst +0.02R/trade (weakest); warn=label only", "decision_date": "2026-06-24"},
    {"key": "intelligence_layer", "label": "Intelligence layer (timeline/derivs/squeeze)",
     "state": "keep_measuring", "affects_trades": False,
     "evidence": "NEED_MORE_DATA (<30 closed actionable)", "decision_date": "2026-06-19"},
    {"key": "circuit_breaker_block", "label": "Circuit breaker as BLOCK",
     "state": "keep_shadow", "affects_trades": False,
     "evidence": "needs ≥10 real would_pause fires", "decision_date": "2026-06-19"},
    {"key": "sector_concentration_caps_block", "label": "Sector/concentration caps as BLOCK",
     "state": "keep_shadow", "affects_trades": False,
     "evidence": "needs binds + net-positive counterfactual", "decision_date": "2026-06-19"},
    {"key": "shadow_exit_manager_variants", "label": "Old BE/partial/trailing variants",
     "state": "archived", "affects_trades": False,
     "evidence": "SUPERSEDED_BY_MODEL_F (armed too late)", "decision_date": "2026-06-24"},
    {"key": "crypto_scalp_actionable", "label": "Crypto scalp actionable",
     "state": "dangerous_locked", "affects_trades": False,
     "evidence": "net-negative every model", "decision_date": "2026-06-18"},
    {"key": "stocks_c_tier_actionable", "label": "Stocks C-tier actionable",
     "state": "dangerous_locked", "affects_trades": False,
     "evidence": "30d −34R drag", "decision_date": "2026-06-18"},
    {"key": "stocks_swing_invest_actionable", "label": "Stocks swing/invest actionable",
     "state": "dangerous_locked", "affects_trades": False,
     "evidence": "paused by policy", "decision_date": "2026-06-18"},
]

_ACTIVE_STATES = {"active_paper_accounting", "active_paper_display", "active_advisory"}


def _cohort_guard_mode() -> str:
    """Best-effort read of the desk cohort_guard mode; default 'warn'."""
    db = os.environ.get("DESK_DB_PATH", "")
    # config lives next to the desk DB's project root: <root>/config/cohort_guard.yaml
    for base in (os.path.dirname(os.path.dirname(db)) if db else "",
                 os.environ.get("DESK_ROOT", "")):
        if not base:
            continue
        path = os.path.join(base, "config", "cohort_guard.yaml")
        if yaml and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return str((yaml.safe_load(fh) or {}).get("cohort_guard", {}).get("mode") or "warn")
            except Exception:
                pass
    return "warn"


def paper_features_summary() -> dict:
    """Active/inactive/archived/dangerous paper-feature lists for the app panel."""
    cohort_mode = _cohort_guard_mode()
    feats = []
    for f in _FEATURES:
        g = dict(f)
        if g["key"] == "cohort_guard_warn":
            g["mode"] = cohort_mode
            g["state"] = "active_paper_display" if cohort_mode in ("warn", "paper_review_only") else "off"
        feats.append(g)
    active = [f for f in feats if f["state"] in _ACTIVE_STATES]
    shadow = [f for f in feats if f["state"] in ("keep_measuring", "keep_shadow")]
    archived = [f for f in feats if f["state"] == "archived"]
    dangerous = [f for f in feats if f["state"] == "dangerous_locked"]
    return {
        "risk_model": "early_mfe_protection_v1",
        "live_locked": True, "auto_live_locked": True,
        "active": active, "shadow_or_measuring": shadow,
        "archived": archived, "dangerous_locked": dangerous,
        "counts": {"active": len(active), "shadow": len(shadow),
                   "archived": len(archived), "dangerous": len(dangerous)},
        "note": ("Active features are PAPER/ACCOUNTING/DISPLAY only — none enable live, "
                 "auto-live, exchange execution, production exits, or production TP/SL. "
                 "Historical final_r is never rewritten."),
    }
