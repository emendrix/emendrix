"""The third signal: the amending act's own instructions, and the reference grammar under it.

What the structure-aware parser reaches on the amending acts the fixture set contains, first
measured 2026-08-06. Reading the clauses alone misses every insertion, because EU drafting
writes "the following Article is inserted:" without the number; the identifiers are in the
quoted markup, which is why the parser reads structure rather than prose.

The parser is a *cross-check, not ground truth*. Where it falls short the number is
asserted, not smoothed.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from xml.etree import ElementTree

import pytest

from emendrix.core import ActId, ChangeType, ProvisionLocation, Signal
from emendrix.eu.cellar import CellarClient
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.instructions import (
    EffectDateSource,
    InstructionParse,
    instruction_signal,
    parse_instructions,
)
from emendrix.eu.instructions.effect import clause_effect_date, source_location
from emendrix.eu.instructions.final_provisions import read_effect_dates
from emendrix.eu.references import parse_reference, resolve
from eu_pins import (
    AI_ACT,
    DIGITAL_OMNIBUS,
    MDR,
    MDR_2023_AMENDER,
    MDR_ANNEX_AMENDER,
    MDR_POSTPONEMENT,
    REACH,
    REACH_2008_AMENDER,
    package,
)

INSERTED_UNITS = ("AR 4a", "AR 60a", "AR 75a", "AR 75b", "AR 75c", "AR 75d", "AN XIV")
"""What `32026R1744` creates. Six articles and one annex, none of them named in prose."""

MDR_2024_AMENDER = "32024R1860"
"""The MDR's 2024 amender, and the pinned act whose Article 3 defers one of its own points:
*"Article 1, point (1), and Article 2, point (1), shall apply from 10 January 2025"*, with the
date in `<DATE ISO="20250110">`."""

IFR_DEFERRED_CLAUSE = (
    "in Chapter 1 of Title I of Part Three, Section 2 (Articles 95 to 98) is deleted "
    "with effect from 26 June 2026 ;"
)
"""`32019R2033` Article 62(14), as `_clause` builds it: an instruction that dates itself."""


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


@pytest.fixture
def mdr_2023(client: CellarClient) -> InstructionParse:
    return parse_instructions(package(client, MDR_2023_AMENDER, MDR_2023_AMENDER))


@pytest.fixture
def reach_2008(client: CellarClient) -> InstructionParse:
    return parse_instructions(package(client, REACH_2008_AMENDER, REACH_2008_AMENDER))


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


# ------------------------------------------------- the articles that carry no list


def test_an_article_without_a_list_reads_the_provision_its_prose_names(
    mdr_2023: InstructionParse,
) -> None:
    """`32023R0502` states its one instruction in prose, so the whole article is the clause.

    The clause is the instruction's own words and nothing else: read on 2026-09-04, the record
    names `AR 44` of the MDR, the unit the structural diff and the annotations both name. Its
    `source_ref` stays the bare `AR 001`, which is provenance rather than a coordinate: it says
    which article of the amending act drafted the instruction, and that is Article 1.
    """
    records = mdr_2023.for_act(act(MDR))
    assert [record.unit.canonical for record in records] == ["AR 44"]
    assert [record.source_ref for record in records] == ["AR 001"]
    assert [unit.canonical for unit in mdr_2023.units(act(MDR))] == ["AR 44"]


def test_the_amending_acts_own_heading_is_not_a_provision_reference(
    reach_2008: InstructionParse,
) -> None:
    """An article heading names the amending act's own number, never the amended act's.

    `32008R0987` states both of its instructions in prose. Until 2026-09-04 the heading survived
    into the clause, and because the reference grammar keeps only the first coordinate at each
    depth, "Article 1" and "Article 2" spoke before "Annex IV" and "Annex V" could: the claims
    came out as `AR 1` and `AR 2`, coordinates no other signal on that transition named.
    """
    assert {unit.canonical for unit in reach_2008.units(act(REACH))} == {"AN IV", "AN V"}
    located = {record.location.canonical for record in reach_2008.records}
    assert not located & {"AR 1", "AR 2"}


def test_a_hybrid_claim_keeps_its_deeper_coordinates_under_the_right_article(
    mdr_2023: InstructionParse,
) -> None:
    """The deeper coordinates were always read off the real sentence; only the article was wrong.

    `32023R0502` Article 1 amends Article 44(10) of the MDR, and until 2026-09-04 the claim read
    `AR 1 PA 10`: the paragraph came off the instruction, the article off the heading above it.
    A claim of that shape is the more misleading of the two the leak produced, because it looks
    like a precise reading. The paragraph must survive the correction rather than go with it.
    """
    records = mdr_2023.for_act(act(MDR))
    assert [record.location.canonical for record in records] == ["AR 44 PA 10"]


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


# ------------------------------------------------------ when an instruction takes effect


def test_a_clause_that_dates_itself_is_read_in_its_own_words() -> None:
    """The prose form, from `32019R2033` Article 62(14). No markup is involved in this one."""
    assert clause_effect_date(IFR_DEFERRED_CLAUSE) == date(2026, 6, 26)


@pytest.mark.parametrize(
    "clause",
    [
        # A date the clause is about, not a date the clause takes effect on (`32020R0561`).
        "in the first sentence, the date 26 May 2020 is replaced by 26 May 2021 ;",
        # The phrase without a date behind it: a deferral this cannot resolve to a day.
        "Article 5 is deleted with effect from the date of entry into force of this Regulation;",
        # Two effect phrases, two days: the clause is not saying one thing.
        "point (a) applies with effect from 1 January 2026 and with effect from 1 January 2027;",
    ],
)
def test_a_date_the_clause_does_not_take_effect_on_is_not_read(clause: str) -> None:
    """Guard one, in the prose reader: an unattached date dates nothing."""
    assert clause_effect_date(clause) is None


def test_the_source_reference_folds_onto_the_grammars_own_spelling() -> None:
    """ "AR 001 (1)" and "Article 1, point (1)" are one coordinate written two ways."""
    folded = source_location("AR 001 (1) (b)")
    assert folded is not None and folded.canonical == "AR 1 PO 1 PTA (b)"


def test_the_deferred_point_of_the_2024_amender_carries_its_tagged_date(
    client: CellarClient,
) -> None:
    """The markup form: Article 3 names `AR 1 PO 1` and dates it, and the tag is the date.

    The instruction that inserts MDR Article 10a is drafted at Article 1, point (1) of the
    amending act, which is exactly the coordinate its final provisions defer.
    """
    parse = parse_instructions(package(client, MDR_2024_AMENDER, MDR_2024_AMENDER))
    deferred = [record for record in parse.records if record.source_ref == "AR 001 (1)"]
    assert [record.location.canonical for record in deferred] == ["AR 10a"]
    assert deferred[0].effect_date == date(2025, 1, 10)
    assert deferred[0].effect_source is EffectDateSource.FINAL_PROVISIONS


def test_the_instructions_that_article_does_not_name_carry_no_date(
    client: CellarClient,
) -> None:
    """The counted gap: `32024R1860` enters into force on the day of its publication, which is
    a day its own text never writes, so every instruction but the deferred one is undated."""
    parse = parse_instructions(package(client, MDR_2024_AMENDER, MDR_2024_AMENDER))
    assert parse.dated == 1
    assert parse.undated == parse.matched - 1
    undated = [record for record in parse.records if record.effect_date is None]
    assert {record.effect_source for record in undated} == {EffectDateSource.UNREAD}


def test_an_act_whose_dates_are_all_about_another_act_dates_no_instruction(
    postponement: InstructionParse,
) -> None:
    """Guard one over a whole act, from the corpus: `32020R0561` is a document of dates.

    Its instructions replace 26 May 2020 with 26 May 2021 a dozen times over and its Article 2
    gives the act no day of its own, so not one of those dates is attached to a coordinate this
    parser wrote and not one of them is used.
    """
    assert postponement.dated == 0
    assert postponement.effect_date_coverage == 0.0
    assert {record.effect_source for record in postponement.records} == {EffectDateSource.UNREAD}


def test_an_unreadable_effect_date_is_counted_and_the_read_is_unchanged(
    omnibus: InstructionParse,
) -> None:
    """`32026R1744` enters into force twenty days after a publication it does not date.

    The whole instruction set is therefore undated, which is a coverage statistic and not an
    error: the 95 records and the 1.000 clause coverage are exactly what they were.
    """
    assert omnibus.matched == 95
    assert omnibus.coverage == 1.0
    assert omnibus.dated == 0
    assert omnibus.undated == 95
    assert omnibus.effect_date_coverage == 0.0


def _act(*alineas: str) -> ElementTree.Element:
    """A markup double of a final-provisions article: only its date reading is under test.

    The `<DATE ISO>` attribute is the one the Publications Office tags, and the sentences are
    the shapes the drafting writes them in.
    """
    body = "".join(f"<ALINEA>{alinea}</ALINEA>" for alinea in alineas)
    return ElementTree.fromstring(
        f"<ARTICLE IDENTIFIER='003'><TI.ART>Article 3</TI.ART>"
        f"<STI.ART><P>Entry into force</P></STI.ART>{body}</ARTICLE>"
    )


APPLIES = "This Regulation shall apply from <DATE ISO='20210628'>28 June 2021</DATE>."


def test_the_acts_own_date_of_application_dates_every_instruction_it_does_not_defer() -> None:
    """The third answer: one date for the whole act, and the coordinate is the act itself."""
    dates = read_effect_dates([_act(APPLIES)])
    assert dates.default == date(2021, 6, 28)
    assert dates.for_clause("Article 4 is deleted;", "AR 001 (7)") == (
        date(2021, 6, 28),
        EffectDateSource.ACT_DEFAULT,
    )


def test_an_enumerated_deferral_withdraws_the_default_from_the_article_it_names() -> None:
    """A deferral this cannot separate leaves its article undated rather than wrongly dated."""
    deferral = (
        "The following points of Article 1 of this Regulation shall apply from "
        "<DATE ISO='20190627'>27 June 2019</DATE>:"
    )
    dates = read_effect_dates([_act(APPLIES, deferral)])
    assert dates.default == date(2021, 6, 28)
    assert dates.for_clause("Article 4 is deleted;", "AR 001 (7)") == (
        None,
        EffectDateSource.UNREAD,
    )
    assert dates.for_clause("Article 4 is deleted;", "AR 002 (1)") == (
        date(2021, 6, 28),
        EffectDateSource.ACT_DEFAULT,
    )


def test_a_deferral_written_as_a_range_withdraws_the_default_from_the_whole_act() -> None:
    """ "Articles 95 to 98" names two units and means four, so nothing here is dated."""
    deferral = (
        "Articles 95 to 98 of this Regulation shall apply from "
        "<DATE ISO='20260626'>26 June 2026</DATE>."
    )
    dates = read_effect_dates([_act(APPLIES, deferral)])
    assert dates.default is None
    assert dates.unread == 1
    assert dates.for_clause("Article 4 is deleted;", "AR 001 (7)") == (
        None,
        EffectDateSource.UNREAD,
    )


def test_a_scope_article_is_not_a_final_provisions_article() -> None:
    """ "This Regulation shall apply to" says nothing about a day, and dates nothing."""
    scope = (
        "This Regulation shall apply to devices placed on the market after "
        "<DATE ISO='20210526'>26 May 2021</DATE>."
    )
    assert read_effect_dates([_act(scope)]).default is None
