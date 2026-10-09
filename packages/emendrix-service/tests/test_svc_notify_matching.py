"""Matching follows the containment rules exactly, the first rule winning for each item."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from emendrix_service.db.enums import ItemKind
from emendrix_service.notify.facts import ChangeFacts, ItemFacts
from emendrix_service.notify.matching import Hit, best, is_date_alert, match, phrase

WATCHLIST = UUID(int=1)


def change(location: str, *within: str, change_type: str = "MODIFIED") -> ChangeFacts:
    return ChangeFacts(
        event_key="toy/house-rules@v3",
        location=location,
        change_type=change_type,
        changed_within=within,
    )


def item(location: str | None, number: int = 10) -> ItemFacts:
    return ItemFacts(
        item_id=UUID(int=number),
        watchlist_id=WATCHLIST,
        kind=ItemKind.ACT if location is None else ItemKind.PROVISION,
        corpus="toy",
        act_key="house-rules",
        location=location,
    )


def reasons(found: tuple[Hit, ...]) -> list[str]:
    return [hit.reason for hit in found]


@pytest.mark.parametrize(
    ("changed", "watched", "expected"),
    [
        (change("AR 6", "AR 6"), None, ["act"]),
        (change("AR 6", "AR 6"), "AR 6", ["at"]),
        (change("AR 6 PA 1"), "AR 6", ["at"]),
        (change("AR 6", "AR 6 PA 1"), "AR 6 PA 1", ["inside"]),
        (change("AR 6", "AR 6 PA 1 PTA (a)"), "AR 6 PA 1", ["inside"]),
        (change("AR 6", "AR 6 PA 1"), "AR 6 PA 1 PTA (a)", ["inside"]),
        (change("AR 6"), "AR 6 PA 1", ["container"]),
        (change("AR 6", "AR 6 PA 2"), "AR 6 PA 1", []),
        (change("AR 60", "AR 60"), "AR 6", []),
        (change("AR 6", "AR 6"), "AR 60", []),
        (change("AR 60"), "AR 6 PA 1", []),
        (change("AN I", "AN I", "AN I SLOT 2"), "AN II", []),
    ],
)
def test_svc_notify_the_containment_truth_table(
    changed: ChangeFacts, watched: str | None, expected: list[str]
) -> None:
    assert reasons(match(changed, [item(watched)])) == expected


def test_svc_notify_the_first_rule_wins_for_each_item() -> None:
    # `at` holds and so does `inside` (AR 6 lies around the moved AR 6 PA 1): one hit, `at`.
    found = match(change("AR 6", "AR 6 PA 1"), [item("AR 6")])
    assert found == (Hit(item_id=UUID(int=10), reason="at"),)


def test_svc_notify_each_item_gets_its_own_hit_and_the_most_telling_one_is_shown() -> None:
    items = [item(None, 1), item("AR 6 PA 1", 2), item("AR 6", 3)]
    found = match(change("AR 6", "AR 6 PA 1"), items)
    assert reasons(found) == ["act", "inside", "at"]
    assert best(found) == Hit(item_id=UUID(int=3), reason="at")


def test_svc_notify_the_reason_phrases() -> None:
    watched = item("AR 6 PA 1")
    container = change("AR 6")
    hit = Hit(item_id=watched.item_id, reason="container")
    assert phrase(hit, watched, container, "AI Act") == (
        "you watch AI Act Article 6(1); this change is to Article 6, and the record does not "
        "say which part of it moved"
    )
    at = Hit(item_id=watched.item_id, reason="at")
    assert phrase(at, watched, container, "AI Act") == "you watch AI Act Article 6(1)"
    whole = item(None)
    assert phrase(Hit(item_id=whole.item_id, reason="act"), whole, container, "AI Act") == (
        "you watch AI Act"
    )


def test_svc_notify_a_date_alert_is_a_date_moved_or_a_deferral() -> None:
    assert not is_date_alert(change("AR 113"))
    assert is_date_alert(change("AR 113").model_copy(update={"dates_added": (date(2027, 12, 2),)}))
    assert is_date_alert(change("AR 113").model_copy(update={"dates_removed": (date(2026, 8, 2),)}))
    assert is_date_alert(change("AR 113", change_type="DEFERRED"))
