"""Clock 2: what the diff will and will not say about when a provision applies.

Two real transitions carry the whole story, and neither of them was hand-authored:

- **MDR 2017-05-05 → 2020-04-24** (Regulation (EU) 2020/561, the one-year postponement) is the
  clean case. Six units differ in nothing but a date that moved, so each becomes `DEFERRED`
  with the new date read straight off the corpus's own `DATE ISO` values.
- **AI Act Article 113** is the case the second clock was written for. Its dates moved *and* its
  prose changed around them, and four dates were added at once, so no date that moved can be
  read as the article's application date. It reports `ApplicabilityUnknown` with the dates
  recorded as detail, `2027-12-02` and `2028-08-02` among them, for the explanation to quote
  verbatim.

The second outcome is not a shortfall. Attaching a date to a set of provisions is prose, with
exceptions and conditions; many unknowns is the correct
result and the model never fills one in.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import (
    ApplicabilityUnchanged,
    ApplicabilityUnknown,
    ChangeType,
    DateMention,
    Delta,
    ProvisionNode,
    ProvisionTree,
)
from emendrix.diff import compute_delta, read_dates
from emendrix.diff.deferred import _BEYOND_DATES_REASON, _NOT_ONE_DATE_REASON
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from eu_pins import AI_ACT, AI_ACT_V2, MDR, MDR_V1, MDR_V2, package

AI_ACT_OJ = AI_ACT


def delta(client: CellarClient, celex: str, before: str, after: str) -> Delta:
    trees = [parse_act(package(client, celex, version)).tree for version in (before, after)]
    return compute_delta(trees[0], trees[1])


def dated(text: str, year: int, month: int, day: int) -> ProvisionNode:
    """A one-provision node carrying one machine-readable date, the way the parser hands it on."""
    return ProvisionNode.from_plain_text(
        "AR 1", text, dates=(DateMention(value=date(year, month, day), context=text),)
    )


def node(client: CellarClient, celex: str, version: str, location: str) -> ProvisionNode:
    tree: ProvisionTree = parse_act(package(client, celex, version)).tree
    found = tree.find(location)
    assert found is not None, f"{celex} {version} has no {location}"
    return found


# ------------------------------------------------------- the clean case: the MDR postponement


def test_the_mdr_postponement_is_read_as_six_deferrals(client: CellarClient) -> None:
    computed = delta(client, MDR, MDR_V1, MDR_V2)
    deferred = {
        change.location.canonical: change.applies_from
        for change in computed.changes
        if change.change_type is ChangeType.DEFERRED
    }
    assert deferred == {
        "AR 1": date(2021, 5, 26),
        "AR 17": date(2021, 5, 26),
        "AR 34": date(2021, 3, 25),
        "AR 113": date(2021, 2, 25),
        "AR 120": date(2021, 5, 26),
        "AN IX": date(2021, 5, 26),
    }


def test_a_deferral_records_the_date_it_replaced(client: CellarClient) -> None:
    computed = delta(client, MDR, MDR_V1, MDR_V2)
    change = next(c for c in computed.changes if c.location.canonical == "AR 1")
    assert change.dates_removed == (date(2020, 5, 26),)
    assert change.dates_added == (date(2021, 5, 26),)


def test_a_unit_whose_prose_changed_around_its_dates_is_not_deferred(
    client: CellarClient,
) -> None:
    """MDR Article 123 moved three dates *and* rewrote its transitional points: `MODIFIED`."""
    computed = delta(client, MDR, MDR_V1, MDR_V2)
    change = next(c for c in computed.changes if c.location.canonical == "AR 123")
    assert change.change_type is ChangeType.MODIFIED
    assert isinstance(change.applies_from, ApplicabilityUnknown)
    assert change.dates_added == (date(2020, 4, 24),)


# ---------------------------------------------------- the honest unknown: AI Act Article 113


def test_ai_act_article_113_captures_the_deferred_dates_without_claiming_one_applies(
    client: CellarClient,
) -> None:
    computed = delta(client, AI_ACT, AI_ACT_OJ, AI_ACT_V2)
    change = next(c for c in computed.changes if c.location.canonical == "AR 113")
    assert date(2027, 12, 2) in change.dates_added
    assert date(2028, 8, 2) in change.dates_added
    assert change.dates_added == (
        date(2026, 7, 27),
        date(2026, 12, 2),
        date(2027, 12, 2),
        date(2028, 8, 2),
    )
    assert change.change_type is ChangeType.MODIFIED
    applies = change.applies_from
    assert isinstance(applies, ApplicabilityUnknown)
    assert applies.reason == _BEYOND_DATES_REASON, (
        "the reason is prose a reader and a model both meet, so it is asserted whole"
    )


def test_the_deferred_dates_are_localised_to_the_points_that_carry_them(
    client: CellarClient,
) -> None:
    """Which subparagraph moved is detail the diff can give; which date applies is not."""
    computed = delta(client, AI_ACT, AI_ACT_OJ, AI_ACT_V2)
    change = next(c for c in computed.changes if c.location.canonical == "AR 113")
    within = [location.canonical for location in change.changed_within]
    assert "AR 113 ALN 3 PTA (c) PTI (i)" in within
    assert "AR 113 ALN 3 PTA (c) PTI (ii)" in within


# ------------------------------------------------------------------------- the reader itself


def test_a_unit_whose_dates_did_not_move_says_unchanged_rather_than_unknown(
    client: CellarClient,
) -> None:
    """AI Act Article 4's text changed and its dates did not; clock 2 has a definite answer."""
    before = node(client, AI_ACT, AI_ACT_OJ, "AR 4")
    after = node(client, AI_ACT, AI_ACT_V2, "AR 4")
    verdict = read_dates(before, after)
    assert not verdict.deferred
    assert verdict.applies_from == ApplicabilityUnchanged()


def test_dates_come_from_the_markup_and_never_from_a_regex_over_the_prose() -> None:
    """A year written in the text but not tagged as a date is not date material.

    Regex date-finding is exactly where false deferrals would come from, so a
    provision whose only difference is an untagged number stays `MODIFIED`.
    """
    before = ProvisionNode.from_plain_text("AR 1", "Reports are due in cycle 2020 of the scheme.")
    after = ProvisionNode.from_plain_text("AR 1", "Reports are due in cycle 2021 of the scheme.")
    verdict = read_dates(before, after)
    assert not verdict.deferred
    assert verdict.applies_from == ApplicabilityUnchanged()


def test_a_renumbered_cross_reference_beside_a_moved_date_is_not_a_pure_date_move() -> None:
    """The date really moved *and* `point 5` became `point 6`. That is not a deferral.

    A day of the month is a small integer, and a small integer in legal prose is usually a
    cross-reference. The reader therefore requires every differing region to carry a token
    that can only be a date, a year or a month name or a written-out numeric date, before it
    accepts the region as date material. Without that guard the bare `5` → `6` passes as the
    day that moved, the substantive edit is swallowed, and the change ships with a confident
    `applies_from` it has not earned.
    """
    before = dated(
        "The measure applies from 5 March 2020. See point 5 for the conditions.", 2020, 3, 5
    )
    after = dated(
        "The measure applies from 6 March 2021. See point 6 for the conditions.", 2021, 3, 6
    )
    verdict = read_dates(before, after)
    assert not verdict.deferred
    assert isinstance(verdict.applies_from, ApplicabilityUnknown)
    assert verdict.removed == (date(2020, 3, 5),)
    assert verdict.added == (date(2021, 3, 6),)


def test_a_date_that_moved_alone_is_still_read_when_the_month_moved_with_it() -> None:
    """The same shape without the stray reference: the month name is the evidence."""
    before = dated("The measure applies from 26 May 2020 in every Member State.", 2020, 5, 26)
    after = dated("The measure applies from 24 April 2021 in every Member State.", 2021, 4, 24)
    verdict = read_dates(before, after)
    assert verdict.deferred
    assert verdict.applies_from == date(2021, 4, 24)


def test_a_window_that_shifted_whole_reports_how_many_dates_it_could_not_choose_between() -> None:
    """Date-only differences, two dates added, so there is no single date to report.

    Synthetic on purpose. Nothing in the committed corpus reaches this branch: every unit whose
    differences are confined to its dates added exactly one, so the case has no fixture to
    borrow. A validity window that shifted by a year is the smallest honest shape for it, and
    hand-written arithmetic is not hand-authored legal content: no provision of any real act is
    quoted, asserted about or interpreted here.
    """
    before = ProvisionNode.from_plain_text(
        "AR 1",
        "The scheme runs from 1 January 2020 to 31 December 2020.",
        dates=(
            DateMention(value=date(2020, 1, 1), context="1 January 2020"),
            DateMention(value=date(2020, 12, 31), context="31 December 2020"),
        ),
    )
    after = ProvisionNode.from_plain_text(
        "AR 1",
        "The scheme runs from 1 January 2021 to 31 December 2021.",
        dates=(
            DateMention(value=date(2021, 1, 1), context="1 January 2021"),
            DateMention(value=date(2021, 12, 31), context="31 December 2021"),
        ),
    )
    verdict = read_dates(before, after)
    assert not verdict.deferred
    assert verdict.added == (date(2021, 1, 1), date(2021, 12, 31))
    applies = verdict.applies_from
    assert isinstance(applies, ApplicabilityUnknown)
    assert applies.reason == _NOT_ONE_DATE_REASON.format(count=2)
