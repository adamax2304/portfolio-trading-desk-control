"""Control Plane must display persisted Paper execution ahead of legacy touch state."""
from __future__ import annotations

from app.display_status import CLOSED_WIN, OPEN_ACTIVE, derive_display_status


def test_legacy_expired_placeholder_stays_open_when_paper_execution_is_open():
    result = derive_display_status({
        "status": "triggered",
        "entry_triggered_at": "2026-08-19T02:00:00+00:00",
        "final_outcome": "expired",
        "final_r": 0.0,
        "paper_lifecycle_state": "OPEN",
        "paper_execution_outcome": "open",
        "paper_execution_r": None,
        "actionability": {"status": "actionable"},
    })

    assert result["display_group"] == OPEN_ACTIVE
    assert result["paper_outcome_authoritative"] is False


def test_terminal_paper_execution_overrides_legacy_touch_label_and_r():
    result = derive_display_status({
        "status": "triggered",
        "entry_triggered_at": "2026-08-19T02:00:00+00:00",
        "final_outcome": "expired",
        "final_r": 0.0,
        "paper_lifecycle_state": "CLOSED",
        "paper_execution_outcome": "win",
        "paper_execution_r": 0.5,
        "paper_close_reason": "profit_lock_stop",
        "actionability": {"status": "actionable"},
    })

    assert result["display_group"] == CLOSED_WIN
    assert result["paper_outcome_authoritative"] is True
    assert result["display_r_source"] == "paper execution"
    assert "+0.5R" in result["operator_label"]
