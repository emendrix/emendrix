"""The flagship regression: the AI Act against the Digital Omnibus, plus MDR and REACH.

These numbers were measured three times by three independent implementations: the standalone
validation trace on 2026-08-05 (`scripts/validation/`), the parser's own set difference on
2026-08-06 (`tests/eu/test_formex_parse.py`), and `emendrix.diff.compute_delta` here. **If one
of them moves, that is a finding to explain, not a test to update.**

The AI Act transition is stated at article granularity (6 inserted · 36 modified · 0 deleted ·
77 unchanged → 42 touched), because the article is the headline unit and what the corpus's
modification metadata was compared against. The delta
covers annexes too, so its own totals are 7 · 38 · 0 · 88 → 45 touched. Both are asserted, and
the difference between them is `AN XIV` (inserted) and two modified annexes.
"""

from __future__ import annotations

from collections import Counter

import pytest

from emendrix.core import ChangeType, Delta, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from eu_pins import (
    AI_ACT,
    AI_ACT_V2,
    MDR,
    MDR_V1,
    MDR_V2,
    REACH,
    REACH_2008,
    REACH_2009,
    package,
)

AI_ACT_OJ = AI_ACT
"""The act as published in the Official Journal is its own version tag (`eu/identifiers.py`)."""


def tree(client: CellarClient, celex: str, version: str) -> ProvisionTree:
    return parse_act(package(client, celex, version)).tree


def delta(client: CellarClient, celex: str, before: str, after: str) -> Delta:
    return compute_delta(tree(client, celex, before), tree(client, celex, after))


def counts(computed: Delta, prefix: str) -> Counter[ChangeType]:
    return Counter(
        change.change_type
        for change in computed.changes
        if change.unit.canonical.startswith(prefix)
    )


def test_the_flagship_article_numbers_are_reproduced_exactly(client: CellarClient) -> None:
    """The flagship numbers, at the article granularity the headline is stated in."""
    before = tree(client, AI_ACT, AI_ACT_OJ)
    computed = compute_delta(before, tree(client, AI_ACT, AI_ACT_V2))
    articles = counts(computed, "AR ")
    assert articles[ChangeType.INSERTED] == 6
    assert articles[ChangeType.MODIFIED] == 36
    assert articles[ChangeType.DELETED] == 0
    assert articles[ChangeType.RENUMBERED] == 0
    assert articles[ChangeType.DEFERRED] == 0
    published = sum(1 for unit in before.unit_locations() if unit.canonical.startswith("AR "))
    assert published == 113
    assert published - articles[ChangeType.MODIFIED] - articles[ChangeType.DELETED] == 77


def test_the_flagship_touched_article_count_is_forty_two(client: CellarClient) -> None:
    computed = delta(client, AI_ACT, AI_ACT_OJ, AI_ACT_V2)
    touched = {c.unit.canonical for c in computed.changes if c.unit.canonical.startswith("AR ")}
    assert len(touched) == 42


def test_the_inserted_articles_are_exactly_the_ones_the_digital_omnibus_published(
    client: CellarClient,
) -> None:
    computed = delta(client, AI_ACT, AI_ACT_OJ, AI_ACT_V2)
    inserted = sorted(
        change.location.canonical
        for change in computed.changes
        if change.change_type is ChangeType.INSERTED
    )
    assert inserted == ["AN XIV", "AR 4a", "AR 60a", "AR 75a", "AR 75b", "AR 75c", "AR 75d"]


@pytest.mark.parametrize(
    ("celex", "before", "after", "inserted", "modified", "deferred", "deleted", "unchanged"),
    [
        # Annexes included: `AN XIV` inserted and two annexes modified beyond the article count.
        (AI_ACT, AI_ACT_OJ, AI_ACT_V2, 7, 38, 0, 0, 88),
        # Regulation (EU) 2020/561 postponed the MDR by a year: six of the nine touched units
        # differ in nothing but a date, so they classify `DEFERRED`.
        (MDR, MDR_V1, MDR_V2, 0, 3, 6, 0, 131),
        (REACH, REACH_2008, REACH_2009, 0, 40, 0, 0, 118),
    ],
)
def test_every_pinned_transition_yields_the_validated_totals(
    client: CellarClient,
    celex: str,
    before: str,
    after: str,
    inserted: int,
    modified: int,
    deferred: int,
    deleted: int,
    unchanged: int,
) -> None:
    """`DEFERRED` refines `MODIFIED`, so the two together are the validated `modified` number."""
    summary = delta(client, celex, before, after).summary
    assert summary.inserted == inserted
    assert summary.modified == modified
    assert summary.deferred == deferred
    assert summary.deleted == deleted
    assert summary.renumbered == 0
    assert summary.unchanged_units == unchanged
    assert summary.touched_units == inserted + modified + deferred + deleted


def test_no_renumbering_is_found_where_none_occurred(client: CellarClient) -> None:
    """Seven traces, three acts, 2006 to 2026: not one renumbering. A hit here is a bug."""
    for celex, before, after in (
        (AI_ACT, AI_ACT_OJ, AI_ACT_V2),
        (MDR, MDR_V1, MDR_V2),
        (REACH, REACH_2008, REACH_2009),
    ):
        computed = delta(client, celex, before, after)
        assert computed.summary.renumbered == 0
        assert all(change.previous_location is None for change in computed.changes)


def test_the_delta_is_emitted_in_the_new_versions_document_order(client: CellarClient) -> None:
    """Insertions sit where the new text puts them: `AR 4a` after `AR 4`, not at the end."""
    computed = delta(client, AI_ACT, AI_ACT_OJ, AI_ACT_V2)
    order = [change.location.canonical for change in computed.changes]
    assert order[:6] == ["AR 1", "AR 2", "AR 3", "AR 4", "AR 4a", "AR 5"]
    positions = {
        node.location.canonical: index
        for index, node in enumerate(tree(client, AI_ACT, AI_ACT_V2).roots)
    }
    assert [positions[key] for key in order] == sorted(positions[key] for key in order)


def test_the_before_and_after_texts_are_the_unnormalised_ones(client: CellarClient) -> None:
    """Verbatim means verbatim: the diff compares the comparison form and quotes the other.

    The no-break space inside `Article\xa04` is the document's own and survives untouched; the
    line break after it is the one edit extraction makes, where the markup closed the title and
    opened the subtitle with no text between them.
    """
    computed = delta(client, AI_ACT, AI_ACT_OJ, AI_ACT_V2)
    change = next(c for c in computed.changes if c.location.canonical == "AR 4")
    assert change.after is not None and change.after.startswith("Article\xa04\nAI literacy\n")
    assert change.before is not None and change.before.startswith("Article\xa04\nAI literacy\n")


def test_sub_provision_coordinates_land_on_locations_the_tree_really_has(
    client: CellarClient,
) -> None:
    """Detail coordinates are resolvable, so the changelog can cite them without a second parse.

    Resolvable in *one* of the two versions: a sub-provision the amendment removed exists only
    in the old text, and saying so is the point of reporting it. AI Act Article 4 is the case:
    its single unnumbered alinea `AR 4 ALN 1` became the three paragraphs `AR 4 PA 1` to
    `AR 4 PA 3`, so all four coordinates are reported and only three of them resolve forward.
    """
    before, after = tree(client, AI_ACT, AI_ACT_OJ), tree(client, AI_ACT, AI_ACT_V2)
    computed = compute_delta(before, after)
    localised = 0
    for change in computed.changes:
        if change.change_type is not ChangeType.MODIFIED:
            continue
        assert change.changed_within, change.location.canonical
        for location in change.changed_within:
            found = after.find(location) or before.find(location)
            assert found is not None, location.canonical
            assert location.is_within(change.unit) or location == change.unit
            localised += 1
    assert localised == 100  # measured 2026-08-06 over the 38 modified units


def test_the_flagship_delta_is_byte_stable(client: CellarClient) -> None:
    before, after = tree(client, AI_ACT, AI_ACT_OJ), tree(client, AI_ACT, AI_ACT_V2)
    assert (
        compute_delta(before, after).model_dump_json()
        == compute_delta(before, after).model_dump_json()
    )
