"""Matching follows the containment rules exactly, the first rule winning for each item."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from emendrix_service.db.enums import ItemKind
from emendrix_service.notify.facts import ChangeFacts, ItemFacts, RowHit
from emendrix_service.notify.matching import (
    RANK,
    Hit,
    best,
    is_date_alert,
    match,
    phrase,
    row_name,
    substance_rule,
)

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


def substance(identifier: str, number: int = 20) -> ItemFacts:
    return ItemFacts(
        item_id=UUID(int=number),
        watchlist_id=WATCHLIST,
        kind=ItemKind.SUBSTANCE,
        identifier=identifier,
    )


def row(identifier: str, side: str = "after", kind: str = "amended", **extra: object) -> RowHit:
    values: dict[str, object] = {
        "container": "AN VI SCT 3",
        "table_ordinal": 1,
        "row_key": "605-001-00-5",
        "side": side,
        "identifier": identifier,
        "kind": kind,
        "unit": "AN VI",
        "key_label": "Index No",
        **extra,
    }
    return RowHit.model_validate(values)


def tabled(*hits: RowHit, location: str = "AN VI") -> ChangeFacts:
    """A change of another act than any act item names, carrying `hits`."""
    return ChangeFacts(
        event_key="eu/32008R1272@v9",
        location=location,
        change_type="MODIFIED",
        table_hits=hits,
    )


@pytest.mark.parametrize("kind", ["added", "amended", "removed"])
@pytest.mark.parametrize("side", ["before", "after"])
def test_svc_notify_a_substance_matches_a_moved_row_on_either_side(kind: str, side: str) -> None:
    changed = tabled(row("cas:50-00-0", side, kind))
    assert reasons(match(changed, [substance("cas:50-00-0")])) == ["entry"]


def test_svc_notify_a_substance_skips_typography_and_other_numbers() -> None:
    typography = tabled(row("cas:50-00-0", typography_only=True))
    assert match(typography, [substance("cas:50-00-0")]) == ()
    assert match(tabled(row("ec:200-001-8")), [substance("cas:50-00-0")]) == ()
    assert match(change("AN VI"), [substance("cas:50-00-0")]) == ()
    both = tabled(row("cas:50-00-0", typography_only=True), row("cas:50-00-0", row_key="7"))
    found = substance_rule(substance("cas:50-00-0"), both.table_hits)
    assert found is not None and found.row_key == "7"


def test_svc_notify_entry_ranks_above_act_and_below_the_provision_rules() -> None:
    assert [RANK[r] for r in ("at", "inside", "container", "entry", "act")] == [0, 1, 2, 3, 4]
    changed = tabled(row("cas:50-00-0"), location="AR 6")
    found = match(changed, [item(None, 1), substance("cas:50-00-0", 2)])
    assert best(found) == Hit(item_id=UUID(int=2), reason="entry")
    found = match(changed, [substance("cas:50-00-0", 2), item("AR 6", 3)])
    assert best(found) == Hit(item_id=UUID(int=3), reason="at")


def test_svc_notify_the_entry_phrases_by_key_label() -> None:
    watched = substance("cas:50-00-0")
    hit = Hit(item_id=watched.item_id, reason="entry")
    labelled = tabled(row("cas:50-00-0"))
    assert phrase(hit, watched, labelled, "CLP") == (
        "you watch CAS 50-00-0; Index No 605-001-00-5 in CLP Annex VI was amended"
    )
    ec = substance("ec:200-001-8")
    numbered = tabled(row("ec:200-001-8", kind="added", row_key="77", key_label="Entry"))
    assert phrase(hit, ec, numbered, "REACH") == (
        "you watch EC 200-001-8; entry 77 in REACH Annex VI was added"
    )
    named = tabled(
        row("cas:116-06-3", unit="AN I", key_label=None, row_key="aldicarb", name="Aldicarb")
    )
    assert phrase(hit, substance("cas:116-06-3"), named, "PIC") == (
        "you watch CAS 116-06-3; the entry for Aldicarb in PIC Annex I was amended"
    )


@pytest.mark.parametrize(
    ("name", "shown"),
    [
        ("Aldicarb", "Aldicarb"),
        ("Aldicarb (#); and its salts", "Aldicarb (#)"),
        ("x" * 60, "x" * 60),
        (
            "Perfluorooctane sulfonic acid, its salts and perfluorooctane sulfonyl fluoride",
            "Perfluorooctane sulfonic acid, its salts and perfluorooctane…",
        ),
        ("y" * 70, "y" * 60 + "…"),
    ],
)
def test_svc_notify_a_row_name_is_cut_at_a_semicolon_then_at_a_word(name: str, shown: str) -> None:
    assert row_name(name) == shown
