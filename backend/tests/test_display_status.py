"""Control Plane display-status mapping tests (display semantics only)."""
from __future__ import annotations

from app.display_status import (
    ENTERED_UNRESOLVED_EXPIRED,
    NO_ENTRY_EXPIRED,
    OPEN_ACTIVE,
    REVIEW_ONLY_SHADOW,
    derive_display_status,
)


def test_expired_after_entry_not_a_miss():
    d = derive_display_status(
        {"status": "expired", "entry_triggered_at": "2026-06-19T05:00:00Z",
         "actionability": {"status": "actionable"}, "final_r": 0}
    )
    assert d["display_group"] == ENTERED_UNRESOLVED_EXPIRED
    assert d["r_display_policy"] == "unresolved_expiry"
    assert d["is_active_for_operator"] is False


def test_no_entry_expired():
    d = derive_display_status(
        {"status": "stale_before_entry", "actionability": {"status": "actionable"}}
    )
    assert d["display_group"] == NO_ENTRY_EXPIRED


def test_shadow_bucket():
    d = derive_display_status(
        {"status": "triggered", "entry_triggered_at": "x",
         "actionability": {"status": "shadow"}}
    )
    assert d["display_group"] == REVIEW_ONLY_SHADOW


def test_open_active():
    d = derive_display_status(
        {"status": "triggered", "entry_triggered_at": "x",
         "actionability": {"status": "actionable"}}
    )
    assert d["display_group"] == OPEN_ACTIVE
    assert d["is_active_for_operator"] is True


def test_missing_fields_do_not_crash():
    d = derive_display_status({})  # no fields at all
    assert "display_group" in d
    d2 = derive_display_status({"status": "waiting_for_entry"})  # no actionability
    assert d2["display_group"] in {"WAITING_FOR_ENTRY", "UNKNOWN_INCONSISTENT"}
