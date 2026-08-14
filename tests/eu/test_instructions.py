"""The third signal: the amending act's own instructions, and the reference grammar under it.

What the structure-aware parser reaches on the two amending acts the fixture set contains,
measured 2026-08-06. Reading the clauses alone misses every insertion, because EU drafting
writes "the following Article is inserted:" without the number; the identifiers are in the
quoted markup, which is why the parser reads structure rather than prose.

The parser is a *cross-check, not ground truth*. Where it falls short the number is
asserted, not smoothed.
"""

from __future__ import annotations

from collections import Counter

import pytest

from emendrix.core import ActId, ChangeType, ProvisionLocation, Signal
from emendrix.eu.cellar import CellarClient
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.instructions import (
    InstructionParse,
    instruction_signal,
    parse_instructions,
)
from emendrix.eu.references import parse_reference, resolve
from eu_pins import AI_ACT, DIGITAL_OMNIBUS, MDR, MDR_ANNEX_AMENDER, MDR_POSTPONEMENT, package

INSERTED_UNITS = ("AR 4a", "AR 60a", "AR 75a", "AR 75b", "AR 75c", "AR 75d", "AN XIV")
"""What `32026R1744` creates. Six articles and one annex, none of them named in prose."""


def act(celex: str) -> ActId:
    return act_id(Celex.parse(celex))


@pytest.fixture
def omnibus(client: CellarClient) -> InstructionParse:
    return parse_instructions(package(client, DIGITAL_OMNIBUS, DIGITAL_OMNIBUS))


@pytest.fixture
def postponement(client: CellarClient) -> InstructionParse:
    return parse_instructions(package(client, MDR_POSTPONEMENT, MDR_POSTPONEMENT))


@pytest.fixture
def annex_amender(client: CellarClient) -> InstructionParse:
    return parse_instructions(package(client, MDR_ANNEX_AMENDER, MDR_ANNEX_AMENDER))


# ------------------------------------------------------------------- the flagship


def test_every_instruction_of_the_digital_omnibus_is_read(omnibus: InstructionParse) -> None:
    """95 records over three amended acts, and not one instruction-looking clause unread."""
    assert omnibus.matched == 95
    assert omnibus.unread == ()
    assert omnibus.coverage == 1.0
    assert [target.key for target in omnibus.targets] == [AI_ACT, "32018R1139", "32023R1230"]


def test_the_instructions_recover_all_forty_five_units_of_the_flagship(
    omnibus: InstructionParse,
) -> None:
    """The 42 articles and 3 annexes the corpus metadata names, from an independent source."""
    units = omnibus.units(act(AI_ACT))
    assert len(units) == 45
    assert sum(1 for unit in units if unit.canonical.startswith("AR ")) == 42


def test_the_six_insertions_the_prose_does_not_name_are_recovered(
    omnibus: InstructionParse,
) -> None:
    """The whole recall gap: the identifiers come from the quoted provisions, not the clause."""
    inserted = {
        record.location.canonical
        for record in omnibus.for_act(act(AI_ACT))
        if record.change_type is ChangeType.INSERTED and record.location.depth == 1
    }
    assert inserted == set(INSERTED_UNITS)
    assert all(
        record.from_quotation
        for record in omnibus.for_act(act(AI_ACT))
        if record.location.canonical in INSERTED_UNITS
    )


def test_the_added_annex_is_recovered_through_the_included_document(
    omnibus: InstructionParse,
) -> None:
    """ "the following Annex is added:" quotes by `INCL.ELEMENT`, not inline (2026-08-06)."""
    added = next(
        record for record in omnibus.for_act(act(AI_ACT)) if record.location.canonical == "AN XIV"
    )
    assert added.change_type is ChangeType.INSERTED
    assert added.from_quotation


def test_instructions_are_scoped_to_the_act_their_article_names(
    omnibus: InstructionParse,
) -> None:
    """One amending act, three amended regulations: an unscoped read cross-attributes."""
    assert omnibus.scoped
    assert len(omnibus.for_act(act(AI_ACT))) == 84
    assert len(omnibus.for_act(act("32018R1139"))) == 7
    assert len(omnibus.for_act(act("32023R1230"))) == 4


def test_an_insertion_into_a_unit_is_a_modification_of_that_unit(
    omnibus: InstructionParse,
) -> None:
    """ "the following points are inserted:" inside Article 3 does not insert Article 3."""
    records = [record for record in omnibus.for_act(act(AI_ACT)) if record.unit.canonical == "AR 3"]
    assert records
    assert {record.change_type for record in records} == {ChangeType.MODIFIED}


def test_the_kinds_the_flagship_instructions_state(omnibus: InstructionParse) -> None:
    """Measured 2026-08-06: the shape of the act, not a target anybody tuned for."""
    kinds = Counter(record.change_type for record in omnibus.for_act(act(AI_ACT)))
    assert kinds == {
        ChangeType.MODIFIED: 45,
        ChangeType.INSERTED: 36,
        ChangeType.DELETED: 3,
    }


# ---------------------------------------------------------- the second amending act


def test_an_act_that_names_its_target_only_in_a_lead_in_clause_still_scopes(
    postponement: InstructionParse,
) -> None:
    """`32020R0561` has no article subtitle; its Article 1 opens "Regulation (EU) 2017/745 …"."""
    assert [target.key for target in postponement.targets] == [MDR]
    assert postponement.scoped


def test_the_postponement_recovers_exactly_the_units_its_metadata_names(
    postponement: InstructionParse,
) -> None:
    """The nine units of the MDR row, from the prose instead of from the annotations."""
    assert [unit.canonical for unit in postponement.units(act(MDR))] == [
        "AR 1",
        "AR 17",
        "AR 34",
        "AR 59",
        "AR 113",
        "AR 120",
        "AR 122",
        "AR 123",
        "AN IX",
    ]
    assert postponement.matched == 26
    assert postponement.unread == ()


def test_an_article_lead_in_that_names_an_annex_scopes_the_sections_below_it(
    annex_amender: InstructionParse,
) -> None:
    """`32025R2457` Art. 3 opens "Annex I to Regulation (EU) 2017/745 is amended as follows:"
    in its own lead-in alinea, and the items below name bare sections. Dropping that scope
    keys the four changes at `SCT 10.4.x`, a coordinate that resolves to no unit of change,
    so the whole annex amendment lands nowhere the diff can be compared against."""
    records = annex_amender.for_act(act(MDR))
    assert [record.location.canonical for record in records] == [
        "AN I SCT 10.4.1 PTA (b)",
        "AN I SCT 10.4.2 PTA (d)",
        "AN I SCT 10.4.3",
        "AN I SCT 10.4.4",
    ]
    assert [unit.canonical for unit in annex_amender.units(act(MDR))] == ["AN I"]


def test_a_reference_written_innermost_first_still_orders_outermost_first(
    postponement: InstructionParse,
) -> None:
    """ "in point (h) of Section 5.1 of Annex IX": the *of* chain runs the other way."""
    found = {record.location.canonical for record in postponement.records}
    assert "AN IX SCT 5.1 PTA (h)" in found


# ------------------------------------------------------------- the reference grammar


@pytest.mark.parametrize(
    ("clause", "expected"),
    [
        ("in Article 1(2), point (g) is replaced by the following:", "AR 1 PA 2 PTA (g)"),
        ("Article 4 is replaced by the following:", "AR 4"),
        ("in Article 11(1), the second subparagraph is replaced", "AR 11 PA 1 ALN 2"),
        ("in Article 113, the third paragraph is amended as follows:", "AR 113 PA 3"),
        ("Annex I is amended as follows:", "AN I"),
        ("in Annex VIII, section B, points 7 and 9 are deleted;", "AN VIII SCT B PO 7"),
        ("in Annex VI, Part C, section 6.6.2 is replaced", "AN VI PRT C SCT 6.6.2"),
        ("in point (h) of Section 5.1 of Annex IX, the date is replaced", "AN IX SCT 5.1 PTA (h)"),
        ("the heading is replaced by the following:", "AR 77 TIT"),
        ("point (14) is amended as follows:", "AR 3 PO 14"),
        # Names no provision at all: the date is not a coordinate, and neither is a sentence.
        ("in the first sentence, the date 26 May 2020 is replaced by 26 May 2021 ;", None),
        ("the introductory part is replaced by the following:", None),
    ],
)
def test_the_reference_grammar_reads_what_the_drafting_writes(
    clause: str, expected: str | None
) -> None:
    """A markup-free test of the grammar alone. `None` = the clause names nothing on its own."""
    context = {
        "the heading is replaced by the following:": "AR 77",
        "point (14) is amended as follows:": "AR 3",
    }
    parsed = parse_reference(clause)
    if expected is None:
        assert parsed is None
        return
    base = context.get(clause)
    resolved = resolve(clause, ProvisionLocation.parse(base) if base else None)
    assert resolved is not None
    assert resolved.canonical == expected


def test_a_relative_clause_is_read_inside_its_parent() -> None:
    """ "paragraph 2 is replaced" under "Article 2 is amended as follows:" is `AR 2 PA 2`."""
    context = ProvisionLocation.parse("AR 2")
    assert resolve("paragraph 2 is replaced by the following:", context) is not None
    resolved = resolve("paragraph 2 is replaced by the following:", context)
    assert resolved is not None and resolved.canonical == "AR 2 PA 2"


def test_a_clause_that_names_nothing_stays_at_its_parent() -> None:
    context = ProvisionLocation.parse("AR 58 PA 1 ALN 1")
    resolved = resolve("the introductory part is replaced by the following:", context)
    assert resolved == context


def test_an_absolute_clause_ignores_its_parent() -> None:
    resolved = resolve(
        "in Article 40(2), the following subparagraph is added:", ProvisionLocation.parse("AR 2")
    )
    assert resolved is not None and resolved.canonical == "AR 40 PA 2"


# ------------------------------------------------------------------------ the signal


def test_the_signal_report_carries_only_core_vocabulary(omnibus: InstructionParse) -> None:
    report = instruction_signal(omnibus, act(AI_ACT))
    assert report.signal is Signal.INSTRUCTION_PARSE
    assert report.available
    assert len(report.units) == 45
    kinds = report.kinds_by_unit()
    assert kinds["AR 4a"] == frozenset({ChangeType.INSERTED})
    assert kinds["AR 5"] == frozenset({ChangeType.MODIFIED})
    assert report.note is not None and "0 unread" in report.note


def test_instruction_claims_name_the_amending_act_they_were_parsed_from(
    omnibus: InstructionParse,
) -> None:
    """The amender is the parsed document, never the act its own instructions target."""
    signal = instruction_signal(omnibus, act(AI_ACT))
    assert signal.claims
    assert {claim.amending_act for claim in signal.claims} == {act(DIGITAL_OMNIBUS)}
