"""The watch pages' rules, without a database: order, paste, item lines, coverage wording."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from emendrix_record.models import CatalogueWaiting
from emendrix_service.db.enums import ItemKind
from emendrix_service.db.watchlists import ActView, ProvisionView, WatchItemView
from emendrix_service.watch.logic import (
    NO_CHANGE_YET,
    canonical_sort_key,
    coverage_line,
    describe_item,
    read_location,
    readable,
    resolve_paste,
    roster_label,
)


def act(*waiting: CatalogueWaiting, checked: date | None = date(2026, 10, 8)) -> ActView:
    return ActView(
        corpus="eu",
        act_key="32017R0745",
        label="MDR",
        long_name="Medical Devices Regulation",
        aliases=("Regulation (EU) 2017/745",),
        url="https://example.org/acts/32017R0745/",
        checked_through=checked,
        waiting=waiting,
    )


def item(location: str | None) -> WatchItemView:
    return WatchItemView(
        id=uuid4(),
        kind=ItemKind.ACT if location is None else ItemKind.PROVISION,
        corpus="eu",
        act_key="32017R0745",
        location=location,
    )


PROVISIONS = [
    ProvisionView(unit="AR 6", heading="Classification", changes=2),
    ProvisionView(unit="AN I", heading=None, changes=1),
]


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("AR 6", "AR 6a"),
        ("AR 6a", "AR 7"),
        ("AR 7", "AR 60"),
        ("AR 6", "AR 6 PA 1"),
        ("AR 6 PA 1", "AR 6 PA 2"),
        ("AR 6 PA 2", "AR 6 PA 10"),
        ("AR 6 PA 1", "AR 6a"),
        ("AR 120", "AN I"),
        ("AN I", "AN II"),
        ("AN IV", "AN V"),
        ("AN V", "AN IX"),
        ("AN IX", "AN X"),
        ("AN X", "AN XIV"),
        ("AN XIV", "AN XXXIX"),
        ("AR 6 PA 1 ALN 1 PTA (a)", "AR 6 PA 1 ALN 1 PTA (b)"),
        ("AR 6 PA 1 PTA (a)", "AR 6 PA 1 XX 1"),
    ],
)
def test_svc_watch_logic_canonical_order(before: str, after: str) -> None:
    assert canonical_sort_key(before) < canonical_sort_key(after)


def test_svc_watch_logic_sorting_a_shuffled_list() -> None:
    shuffled = ["AN X", "AR 7", "AN IX", "AR 6a", "AN II", "AR 60", "AR 6", "AR 6 PA 1"]
    assert sorted(shuffled, key=canonical_sort_key) == [
        "AR 6",
        "AR 6 PA 1",
        "AR 6a",
        "AR 7",
        "AR 60",
        "AN II",
        "AN IX",
        "AN X",
    ]


def test_svc_watch_logic_paste_resolves_and_shows_back() -> None:
    text = (
        "Article 120\n"
        "  annex 1 \n"
        "\n"
        "MDR Article 6(1)\n"
        "medical devices regulation art. 5\n"
        "Article 6(1)(a)\n"
        "the bit about labels\n"
        "AR 120\n"
        "Regulation (EU) 2017/745 Annex XVI\n"
    )
    resolved, unresolved = resolve_paste(text, act())
    assert resolved == ["AR 120", "AN I", "AR 6 PA 1", "AR 5", "AN XVI"]
    assert unresolved == ["Article 6(1)(a)", "the bit about labels"]


def test_svc_watch_logic_paste_of_nothing() -> None:
    assert resolve_paste("\n  \n", act()) == ([], [])


def test_svc_watch_logic_describes_a_known_unit() -> None:
    line = describe_item(item("AR 6"), act(), PROVISIONS)
    assert (line.act_label, line.where, line.unit, line.heading, line.note) == (
        "MDR",
        "Article 6",
        "Article 6",
        "Classification",
        None,
    )


def test_svc_watch_logic_describes_a_sub_provision_of_a_known_unit() -> None:
    line = describe_item(item("AR 6 PA 1"), act(), PROVISIONS)
    assert (line.where, line.unit, line.heading, line.note) == (
        "Article 6(1)",
        "Article 6",
        "Classification",
        None,
    )


def test_svc_watch_logic_describes_an_unknown_unit() -> None:
    for location in ("AR 60", "AR 7 PA 2"):
        line = describe_item(item(location), act(), PROVISIONS)
        assert (line.unit, line.heading, line.note) == (None, None, NO_CHANGE_YET)


def test_svc_watch_logic_describes_a_whole_act_and_a_dropped_act() -> None:
    whole = describe_item(item(None), act(), PROVISIONS)
    assert (whole.where, whole.note) == ("The whole act", None)
    assert describe_item(item(None), act(), []).note == NO_CHANGE_YET
    dropped = describe_item(item("AN I"), None, [])
    assert (dropped.act_label, dropped.act_url, dropped.note) == ("32017R0745", None, NO_CHANGE_YET)


def test_svc_watch_logic_roster_names_the_act_every_way() -> None:
    assert roster_label(act()) == "MDR (Medical Devices Regulation, Regulation (EU) 2017/745)"


def test_svc_watch_logic_coverage_with_nothing_waiting() -> None:
    assert coverage_line(act()) == "Checked for changes published up to 2026-10-08."


def test_svc_watch_logic_coverage_with_two_waiting() -> None:
    waiting = (
        CatalogueWaiting(version="v5", state="consolidation_pending", first_seen=date(2026, 10, 2)),
        CatalogueWaiting(version="v4", state="consolidation_pending", first_seen=date(2026, 9, 28)),
    )
    assert coverage_line(act(*waiting)) == (
        "Checked for changes published up to 2026-10-08. 2 consolidations have been announced "
        "and are waiting for their text; the oldest was first seen on 2026-09-28."
    )


def test_svc_watch_logic_coverage_with_one_waiting_and_english_unavailable() -> None:
    waiting = (
        CatalogueWaiting(version=None, state="english_unavailable", first_seen=date(2026, 9, 1)),
        CatalogueWaiting(version="v4", state="consolidation_pending", first_seen=None),
    )
    assert coverage_line(act(*waiting)) == (
        "Checked for changes published up to 2026-10-08. 1 consolidation has been announced and "
        "is waiting for its text. 1 version is not offered in English."
    )


def test_svc_watch_logic_coverage_unread() -> None:
    assert coverage_line(act(checked=None)) == (
        "The record does not yet say how far this act has been checked for changes."
    )


def test_svc_watch_logic_refuses_what_no_query_should_see() -> None:
    assert readable("AR 6") and not readable("AR 6\x00") and not readable("A" * 121)
    assert read_location("AR " + "1" * 5000) is None
    assert read_location("AR\x006") is None
    huge = canonical_sort_key("AR " + "1" * 100)
    assert canonical_sort_key("AR 2") < huge, "an oversized number sorts as text, after numbers"
    resolved, unresolved = resolve_paste("Article 2\nAR 1\x00", act())
    assert (resolved, unresolved) == (["AR 2"], ["AR 1\x00"])
