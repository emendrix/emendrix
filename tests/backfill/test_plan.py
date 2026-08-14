"""Which transitions a backfill covers, and what it leaves out.

Driven by hand-built descriptors rather than by a corpus, because the rules under test are
about ordering, readability and a date cutoff, and none of those is EU-specific.
"""

from __future__ import annotations

from datetime import date

from emendrix.backfill.plan import plan_transitions
from emendrix.core import ActId, VersionDescriptor, VersionId

ACT = ActId(corpus="toy", key="house-rules")


def version(
    tag: str, day: date | None, *, languages: tuple[str, ...] = ("ENG",)
) -> VersionDescriptor:
    return VersionDescriptor(act=ACT, version=VersionId(tag), version_date=day, languages=languages)


def test_consecutive_readable_versions_become_transitions_oldest_first() -> None:
    plan = plan_transitions(
        ACT,
        [
            version("v1", date(2020, 1, 1)),
            version("v2", date(2021, 1, 1)),
            version("v3", date(2022, 1, 1)),
        ],
    )
    assert [(item.from_version, item.to_version) for item in plan.transitions] == [
        (VersionId("v1"), VersionId("v2")),
        (VersionId("v2"), VersionId("v3")),
    ]
    assert plan.versions == 3
    assert plan.readable == 3
    assert plan.before_cutoff == ()


def test_an_unreadable_version_is_bridged_over_and_named_on_the_pair() -> None:
    """A version with no readable text does not end the chain; the pair says it stepped over it."""
    plan = plan_transitions(
        ACT,
        [
            version("v1", date(2020, 1, 1)),
            version("v2", date(2021, 1, 1), languages=("FRA",)),
            version("v3", date(2022, 1, 1)),
        ],
    )
    assert len(plan.transitions) == 1
    only = plan.transitions[0]
    assert (only.from_version, only.to_version) == (VersionId("v1"), VersionId("v3"))
    assert only.bridged == (VersionId("v2"),)
    assert plan.readable == 2


def test_a_cutoff_drops_transitions_whose_later_version_predates_it() -> None:
    plan = plan_transitions(
        ACT,
        [
            version("v1", date(2020, 1, 1)),
            version("v2", date(2021, 1, 1)),
            version("v3", date(2024, 1, 1)),
        ],
        not_before=date(2023, 1, 1),
    )
    assert [item.to_version for item in plan.transitions] == [VersionId("v3")]
    assert [item.to_version for item in plan.before_cutoff] == [VersionId("v2")]


def test_a_cutoff_excludes_an_undated_transition_rather_than_guessing() -> None:
    """A cutoff is a promise about how far back a run reaches; an undated version cannot keep it."""
    plan = plan_transitions(
        ACT,
        [version("v1", date(2020, 1, 1)), version("v2", None)],
        not_before=date(2019, 1, 1),
    )
    assert plan.transitions == ()
    assert [item.to_version for item in plan.before_cutoff] == [VersionId("v2")]


def test_with_no_cutoff_an_undated_version_is_an_ordinary_endpoint() -> None:
    plan = plan_transitions(ACT, [version("v1", date(2020, 1, 1)), version("v2", None)])
    assert len(plan.transitions) == 1
    assert plan.transitions[0].to_date is None


def test_one_readable_version_offers_no_transition_and_is_not_an_error() -> None:
    """An act with nothing to compare against is a watchlist member awaiting its first amendment."""
    plan = plan_transitions(ACT, [version("v1", date(2020, 1, 1))])
    assert plan.transitions == ()
    assert plan.readable == 1


def test_no_versions_at_all_is_an_empty_plan() -> None:
    plan = plan_transitions(ACT, [])
    assert plan.transitions == ()
    assert plan.versions == 0


def test_the_key_identifies_a_transition_across_runs() -> None:
    plan = plan_transitions(ACT, [version("v1", date(2020, 1, 1)), version("v2", date(2021, 1, 1))])
    assert plan.transitions[0].key == "toy:house-rules|v1|v2"
