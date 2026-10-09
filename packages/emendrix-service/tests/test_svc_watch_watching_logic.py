"""The Watching tab's pure rules: an item's newest change, its line, the groups and the strip."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from emendrix_record.models import CatalogueWaiting
from emendrix_service.db.enums import Cadence, ItemKind
from emendrix_service.db.latest import ChangeStamp
from emendrix_service.db.watchlists import ActView, ProvisionView, WatchItemView, WatchlistView
from emendrix_service.watch.logic import coverage_line
from emendrix_service.watch.watching import (
    NOT_LISTED,
    coverage_short,
    group_by_act,
    latest_for,
    latest_line,
    strip_for,
)

MDR = "32017R0745"
AI = "32024R1689"


def stamp(
    location: str,
    *,
    act_key: str = MDR,
    in_force: date | None = None,
    detected: date = date(2026, 1, 1),
    event: str = "e1",
    url: str | None = "https://example.org/acts/mdr/v2/",
    changed_within: tuple[str, ...] = (),
) -> ChangeStamp:
    return ChangeStamp(
        corpus="eu",
        act_key=act_key,
        location=location,
        unit=" ".join(location.split(" ")[:2]),
        in_force=in_force,
        detected_on=detected,
        event_key=event,
        url=url,
        anchor=location.lower().replace(" ", "-"),
        changed_within=changed_within,
    )


def item(location: str | None, act_key: str = MDR) -> WatchItemView:
    return WatchItemView(
        id=uuid4(),
        kind=ItemKind.ACT if location is None else ItemKind.PROVISION,
        corpus="eu",
        act_key=act_key,
        location=location,
    )


def act(
    act_key: str = MDR,
    label: str = "MDR",
    *waiting: CatalogueWaiting,
    checked: date | None = date(2026, 10, 8),
) -> ActView:
    return ActView(
        corpus="eu",
        act_key=act_key,
        label=label,
        long_name="Medical Devices Regulation",
        aliases=(),
        url=f"https://example.org/acts/{act_key}/",
        checked_through=checked,
        waiting=waiting,
    )


def test_svc_watch_watching_whole_act_takes_the_newest_change_of_the_act() -> None:
    stamps = [
        stamp("AR 5", in_force=date(2026, 3, 1), event="a"),
        stamp("AN I", in_force=date(2026, 5, 1), event="b"),
        stamp("AR 9", act_key=AI, in_force=date(2027, 1, 1), event="c"),
    ]
    assert latest_for(item(None), stamps) == stamps[1]
    assert latest_for(item(None, act_key="other"), stamps) is None


def test_svc_watch_watching_a_provision_takes_what_lies_within_it() -> None:
    inside = stamp("AR 5 PA 1", in_force=date(2026, 3, 1), event="a")
    beside = stamp("AR 50", in_force=date(2026, 9, 1), event="b")
    assert latest_for(item("AR 5"), [inside, beside]) == inside
    assert latest_for(item("AR 50"), [inside, beside]) == beside
    assert latest_for(item("AR 5 PA 2"), [inside, beside]) is None


def test_svc_watch_watching_a_paragraph_takes_what_an_email_would_announce() -> None:
    whole_unit = stamp("AR 5", event="a")
    assert latest_for(item("AR 5 PA 1"), [whole_unit]) == whole_unit, "container"
    named = stamp("AR 5", event="b", changed_within=("AR 5 PA 2",))
    assert latest_for(item("AR 5 PA 1"), [named]) is None, "the record names another part"
    inside = stamp("AR 5", event="c", changed_within=("AR 5 PA 1 PTA (a)",))
    assert latest_for(item("AR 5 PA 1"), [inside]) == inside, "inside"
    assert latest_for(item("AR 50 PA 1"), [whole_unit]) is None


def test_svc_watch_watching_a_unit_matches_a_change_filed_under_it() -> None:
    filed = stamp("AR 5", event="a").model_copy(update={"location": "AR 5a"})
    assert latest_for(item("AR 5"), [filed]) == filed


def test_svc_watch_watching_falls_back_to_detection_and_breaks_ties_by_event() -> None:
    dated = stamp("AR 5", in_force=date(2026, 2, 1), event="a")
    undated = stamp("AR 5", detected=date(2026, 3, 1), event="b")
    assert latest_for(item("AR 5"), [dated, undated]) == undated
    tie_low = stamp("AR 5", in_force=date(2026, 4, 1), event="c")
    tie_high = stamp("AR 5", in_force=date(2026, 4, 1), event="d")
    assert latest_for(item("AR 5"), [tie_high, tie_low]) == tie_high
    assert latest_for(item("AR 5"), [tie_low, tie_high]) == tie_high


def test_svc_watch_watching_latest_line_wording_and_link() -> None:
    assert latest_line(None) == ("No change recorded yet", None)
    assert latest_line(stamp("AR 5", in_force=date(2026, 4, 1))) == (
        "Latest change in force from 2026-04-01",
        "https://example.org/acts/mdr/v2/#ar-5",
    )
    assert latest_line(stamp("AR 5", detected=date(2026, 3, 9), url=None)) == (
        "Latest change recorded 2026-03-09",
        None,
    )


def test_svc_watch_watching_groups_by_act_label_whole_act_first() -> None:
    acts = {("eu", MDR): act(), ("eu", AI): act(AI, "AI Act")}
    provisions = {
        ("eu", MDR): [ProvisionView(unit="AR 2", heading="Definitions", changes=1)],
        ("eu", AI): [],
    }
    items = [item("AR 10"), item("AR 2 PA 1"), item(None), item("AN I", AI), item("AR 9")]
    groups = group_by_act(items, acts, provisions, [stamp("AR 2 PA 1", in_force=date(2026, 1, 2))])
    assert [group.label for group in groups] == ["AI Act", "MDR"]
    assert [row.where for row in groups[1].rows] == [
        "The whole act",
        "Article 2(1)",
        "Article 9",
        "Article 10",
    ]
    assert groups[1].rows[1].heading == "Definitions"
    assert groups[1].rows[1].latest_text == "Latest change in force from 2026-01-02"
    assert groups[1].rows[0].latest_text == "Latest change in force from 2026-01-02"
    assert groups[0].rows[0].latest_text == "No change recorded yet"


def test_svc_watch_watching_an_act_the_catalogue_dropped_keeps_its_key() -> None:
    (group,) = group_by_act([item("AR 1", "32099R9999")], {}, {}, [])
    assert (group.label, group.url, group.coverage_note) == ("32099R9999", None, NOT_LISTED)


def test_svc_watch_watching_coverage_short_with_and_without_waiting() -> None:
    assert coverage_short(act()) == ("Checked to 2026-10-08", False)
    assert coverage_short(act(checked=None)) == ("Not checked yet", False)
    pending = CatalogueWaiting(
        version="v4", state="consolidation_pending", first_seen=date(2026, 10, 1)
    )
    waiting = act(MDR, "MDR", pending)
    assert coverage_short(waiting) == ("Checked to 2026-10-08", True)
    (group,) = group_by_act([item(None)], {("eu", MDR): waiting}, {("eu", MDR): []}, [])
    assert group.waiting and group.coverage_note == coverage_line(waiting)
    (calm,) = group_by_act([item(None)], {("eu", MDR): act()}, {("eu", MDR): []}, [])
    assert not calm.waiting and calm.coverage_note is None


def test_svc_watch_watching_strip_says_how_a_list_is_heard() -> None:
    watchlist = WatchlistView(
        id=uuid4(),
        name="My watchlist",
        cadence=Cadence.WEEKLY,
        date_alerts=True,
        heartbeat=True,
        paused=False,
        has_feed=False,
        items=(),
    )
    strip = strip_for(watchlist)
    assert (strip.email, strip.feed, strip.dates) == (
        "Weekly digest, Mondays 07:00 Brussels time",
        "Off",
        "Flagged",
    )
    instant = watchlist.model_copy(
        update={"cadence": Cadence.INSTANT, "has_feed": True, "date_alerts": False}
    )
    assert (strip_for(instant).email, strip_for(instant).feed, strip_for(instant).dates) == (
        "Every change",
        "On",
        "Not flagged",
    )
    assert strip_for(watchlist.model_copy(update={"paused": True})).email == "Paused"
