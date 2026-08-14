"""The reference label set, read off the pinned branch notices.

The numbers below are measured twice: on 2026-08-05 by the standalone trace script and on
2026-08-06 by this parser. **If one of them moves, that is a finding to explain, not a test to
update.**
"""

from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from emendrix.core import ActId, ChangeType, Signal
from emendrix.eu.cellar import CellarClient
from emendrix.eu.identifiers import Celex
from emendrix.eu.mod_roles import ROLE_CHANGE_TYPE, ModRole, UnknownRole, parse_role
from emendrix.eu.modmeta import (
    ModificationSet,
    metadata_signal,
    parse_branch_modifications,
    touched_units,
)
from eu_pins import AI_ACT, DIGITAL_OMNIBUS, DSA, MDR, MDR_POSTPONEMENT, REACH


@pytest.fixture
def ai_act(client: CellarClient) -> ModificationSet:
    return parse_branch_modifications(client.branch_notice(Celex.parse(AI_ACT)))


def notice(client: CellarClient, celex: str, **kwargs: str) -> ModificationSet:
    return parse_branch_modifications(client.branch_notice(Celex.parse(celex)), **kwargs)


def test_the_flagship_annotation_count_and_role_histogram(ai_act: ModificationSet) -> None:
    """88 annotations, R=45 / J=39 / DEL=4, one amending act.

    The same counts the live branch notice gave on 2026-08-05, printed in
    `scripts/validation/results/32024R1689-annotations.txt`.
    """
    assert len(ai_act.records) == 88
    assert Counter(str(record.role) for record in ai_act.records) == {"R": 45, "J": 39, "DEL": 4}
    assert ai_act.amending_acts == (DIGITAL_OMNIBUS,)
    assert ai_act.clean


def test_the_flagship_annotations_collapse_to_forty_five_units(ai_act: ModificationSet) -> None:
    """42 articles + 3 annexes. The flagship quotes the article figure; this counts annexes."""
    units = touched_units(ai_act.records)
    assert len(units) == 45
    assert sum(1 for unit in units if unit.canonical.startswith("AR ")) == 42
    assert [unit.canonical for unit in units if unit.canonical.startswith("AN ")] == [
        "AN I",
        "AN VIII",
        "AN XIV",
    ]


def test_every_flagship_annotation_carries_the_same_entry_into_force(
    ai_act: ModificationSet,
) -> None:
    """Clock 1 is free and per-amendment: `START_OF_VALIDITY` on every annotation."""
    assert {record.start_of_validity for record in ai_act.records} == {date(2026, 7, 27)}


def test_the_location_templates_are_stripped_to_canonical_strings(ai_act: ModificationSet) -> None:
    """`{AR|http://…/fd_370/AR} 5 {PA|…} 1 …` is `AR 5 PA 1 ALN 1 PTA (bb)`."""
    found = {record.location.canonical for record in ai_act.records}
    assert "AR 5 PA 1 ALN 1 PTA (bb)" in found
    assert "AR 77 TIT" in found
    assert not [value for value in found if "{" in value or "http" in value]


def test_records_of_other_amending_acts_do_not_leak_in(client: CellarClient) -> None:
    """A branch notice carries every amender in the act's history: 10 for the MDR, 85 for REACH."""
    full = notice(client, MDR)
    assert len(full.amending_acts) == 10
    assert len(full.records) == 61
    one = notice(client, MDR, amending_celex=MDR_POSTPONEMENT)
    assert len(one.records) == 26
    assert {record.amending_celex for record in one.records} == {MDR_POSTPONEMENT}
    assert len(touched_units(one.records)) == 9


def test_the_window_of_a_version_pair_is_the_date_not_the_amending_act(
    client: CellarClient,
) -> None:
    """A pair can fold in several amenders, and one amender can span several dates."""
    window = notice(client, MDR).between(date(2017, 5, 5), date(2020, 4, 24))
    assert len(window) == 26
    assert {record.amending_celex for record in window} == {MDR_POSTPONEMENT}
    assert len(touched_units(window)) == 9


def test_the_reach_notice_exercises_every_documented_oddity(client: CellarClient) -> None:
    """391 annotations, 85 amenders, a `TXT` role that is not a role, and slash dates."""
    reach = notice(client, REACH)
    assert len(reach.records) == 391
    assert len(reach.amending_acts) == 85
    assert reach.unknown_roles == (("TXT", 1),)
    assert not reach.clean
    assert reach.unreadable_dates == 0
    # `2007/11/23` and `2008-10-12` both occur; both parse, and 27 use the legacy spelling.
    assert all(record.start_of_validity is not None for record in reach.records)
    roles = Counter(str(record.role) for record in reach.records)
    assert roles == {"R": 238, "J": 105, "M": 26, "A": 10, "DEL": 7, "C": 4, "TXT": 1}


def test_an_unknown_role_is_counted_not_crashed_on(client: CellarClient) -> None:
    """`TXT` is a location code in a role field: a data-quality defect, carried as data."""
    stray = next(
        record for record in notice(client, REACH).records if isinstance(record.role, UnknownRole)
    )
    assert str(stray.role) == "TXT"
    assert stray.change_type is None
    assert stray.model_dump()["role"] == "UNKNOWN(TXT)"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("{J|http://publications.europa.eu/resource/authority/fd_375/J}", ModRole.J),
        ("{DEL|…/fd_375/DEL}", ModRole.DEL),
        ("R", ModRole.R),
        ("  m  ", ModRole.M),
        ("{TXT|…}", UnknownRole(raw="TXT")),
        ("", None),
        (None, None),
    ],
)
def test_the_role_template_is_parsed_defensively(raw: str | None, expected: object) -> None:
    assert parse_role(raw) == expected


def test_the_role_mapping_covers_every_role_in_the_vocabulary() -> None:
    """The classification convention, as a table nothing may silently outgrow."""
    assert set(ROLE_CHANGE_TYPE) == set(ModRole)
    assert ROLE_CHANGE_TYPE[ModRole.J] is ChangeType.INSERTED
    assert ROLE_CHANGE_TYPE[ModRole.R] is ChangeType.MODIFIED
    assert ROLE_CHANGE_TYPE[ModRole.DEL] is ChangeType.DELETED


def test_a_role_on_a_sub_provision_modifies_the_unit_it_sits_in(ai_act: ModificationSet) -> None:
    """`J` on `AR 5 PA 1 ALN 1 PTA (bb)` inserts a *point into* Article 5 (`core.claims`)."""
    claim = next(
        record.to_claim()
        for record in ai_act.records
        if record.location.canonical == "AR 5 PA 1 ALN 1 PTA (bb)"
    )
    assert claim.change_type is ChangeType.INSERTED
    assert claim.unit.canonical == "AR 5"
    assert claim.unit_kind is ChangeType.MODIFIED


def test_every_flagship_claim_names_the_amending_act_as_a_structured_id(
    ai_act: ModificationSet,
) -> None:
    """The amending CELEX becomes an `ActId`, not only a fragment of the audit string."""
    claims = [record.to_claim() for record in ai_act.records]
    assert {claim.amending_act for claim in claims} == {ActId(corpus="eu", key=DIGITAL_OMNIBUS)}
    assert all(claim.source is not None for claim in claims)


def test_an_annotation_with_no_amending_act_carries_none_rather_than_a_placeholder(
    ai_act: ModificationSet,
) -> None:
    """`'?'` is a legible audit string and would be a lie as an identifier."""
    record = ai_act.records[0].model_copy(update={"amending_celex": None})
    claim = record.to_claim()
    assert claim.amending_act is None
    assert claim.source is not None and claim.source.startswith("?")


def test_the_signal_report_speaks_only_core_vocabulary(ai_act: ModificationSet) -> None:
    report = metadata_signal(ai_act.records)
    assert report.signal is Signal.CORPUS_METADATA
    assert report.available
    assert len(report.units) == 45
    kinds = report.kinds_by_unit()
    assert kinds["AR 5"] == frozenset({ChangeType.MODIFIED})
    assert kinds["AR 4a"] == frozenset({ChangeType.INSERTED})
    assert report.in_force_by_unit()["AR 4a"] == date(2026, 7, 27)


# ------------------------------------------------- what an empty annotation set means


def test_an_act_the_corpus_annotates_nowhere_reports_unavailable_not_empty(
    client: CellarClient,
) -> None:
    """A notice that links no amending act is silence, not a claim that nothing changed.

    Reported as available its zero claims would leave every unit the structural diff found
    `ABSENT`, and `OBSERVED` against `ABSENT` is a dispute, so the whole transition would ship
    disputed on the strength of a reference set that does not exist.
    """
    dsa = notice(client, DSA)
    assert dsa.records == ()
    report = metadata_signal(dsa.records, note="0 annotations in (the act itself, 2022-10-12]")
    assert report.available is False
    assert report.units == ()
    assert report.note == "0 annotations in (the act itself, 2022-10-12]"


def test_an_act_annotated_only_outside_the_window_also_reports_unavailable(
    client: CellarClient,
) -> None:
    """Annotations dated outside the window are no evidence about the window.

    The MDR's notice carries 61 annotations, the earliest dated 2020-04-24, so the pair from
    the act as published to the consolidation of 2017-05-05 has none. That consolidation
    carries a corrigendum, and a corrigendum is not an amendment anybody annotates, so the
    metadata is silent about this pair rather than in dissent with the units the diff finds in
    it. Whether the act is annotated elsewhere does not enter the decision: a claim dated 2020
    says nothing about 2017.
    """
    mdr = notice(client, MDR)
    assert len(mdr.records) == 61
    dated = sorted({record.start_of_validity for record in mdr.records if record.start_of_validity})
    assert dated[0] == date(2020, 4, 24)
    window = mdr.between(None, date(2017, 5, 5))
    assert window == ()
    assert metadata_signal(window).available is False


def test_a_window_the_corpus_did_annotate_stays_available_and_can_still_be_dissented_from(
    client: CellarClient,
) -> None:
    """One annotation is a reference set, and a unit missing from it is a genuine dispute.

    This is the boundary of the rule above and the reason it is stated over the window rather
    than over the act: the MDR pair of 2020-04-24 to 2023-03-11 carries a single annotation,
    and the changes the diff finds beyond it are disagreements worth shipping.
    """
    window = notice(client, MDR).between(date(2020, 4, 24), date(2023, 3, 11))
    assert len(window) == 1
    report = metadata_signal(window)
    assert report.available is True
    assert len(report.units) == 1
