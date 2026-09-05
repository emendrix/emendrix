"""A dated statement that writes out every point it defers, and the ones that do not.

The shape is `32021R2117` Article 6, committed verbatim at
`tests/fixtures/eu/celex_32021R2117.article6.xml` and never retyped here. That file is the
output of

    uv run python scripts/validation/instruction_effect_dates.py --markup 32021R2117

run against the disk cache on 2026-09-05, so what is asserted below is what the Publications
Office published rather than a shape invented for a test.

The reason the whole set matters more than the twenty points it dates is the blast radius of a
doubt: a statement read only to its first coordinate leaves the article it names guarded, and
a guarded amending article takes every date away from every instruction drafted in it.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.core import ProvisionLocation
from emendrix.eu.instructions import ActDates, DateKind, EffectDates, EffectDateSource, NoticeDate
from emendrix.eu.instructions.effect import Deferral
from emendrix.eu.instructions.enumerated import read_enumerated
from emendrix.eu.instructions.final_provisions import read_effect_dates
from emendrix.eu.xml_ import fromstring
from eu_pins import FIXTURE_DIR

ARTICLE_6 = FIXTURE_DIR / "celex_32021R2117.article6.xml"

APPLIES = "This Regulation shall apply from <DATE ISO='20210628'>28 June 2021</DATE>."
"""The act speaking about itself, so the doubles below have a default there is something to lose."""


def act(*alineas: str) -> EffectDates:
    """A markup double of a final-provisions article, read the way the loop reads one."""
    body = "".join(f"<ALINEA>{alinea}</ALINEA>" for alinea in alineas)
    return read_effect_dates(
        [fromstring(f"<ARTICLE IDENTIFIER='003'><TI.ART>Article 3</TI.ART>{body}</ARTICLE>")]
    )


def deferred(found: EffectDates) -> dict[str, date]:
    return {item.location.canonical: item.effective for item in found.deferrals}


# ------------------------------------------------------- the enumeration, from the corpus


def test_the_2021_amender_defers_every_one_of_the_twenty_points_it_names() -> None:
    """Four sentences, twenty coordinates, and each one written out in full.

    `(8)(d)(i)` is a depth-three coordinate under Article 1 and resolves the way the
    instruction walk writes the same place, `AR 001 (8) (d) (i)`. The reference grammar keeps
    the first coordinate at each depth, which would have given `AR 1 PO 8` and nothing else.
    """
    found = read_effect_dates([fromstring(ARTICLE_6.read_bytes())])
    assert deferred(found) == {
        "AR 1 PO 8 PTA (d) PTA (i)": date(2021, 1, 1),
        "AR 1 PO 8 PTA (d) PTA (iii)": date(2021, 1, 1),
        "AR 1 PO 10 PTA (a) PTA (ii)": date(2021, 1, 1),
        "AR 1 PO 38": date(2021, 1, 1),
        "AR 2 PO 19 PTA (b)": date(2022, 6, 8),
        "AR 1 PO 1": date(2023, 1, 1),
        "AR 1 PO 2 PTA (b)": date(2023, 1, 1),
        "AR 1 PO 8 PTA (a)": date(2023, 1, 1),
        "AR 1 PO 8 PTA (b)": date(2023, 1, 1),
        "AR 1 PO 8 PTA (e)": date(2023, 1, 1),
        "AR 1 PO 18": date(2023, 1, 1),
        "AR 1 PO 31": date(2023, 1, 1),
        "AR 1 PO 35": date(2023, 1, 1),
        "AR 1 PO 62": date(2023, 1, 1),
        "AR 1 PO 68 PTA (a)": date(2023, 1, 1),
        "AR 1 PO 69": date(2023, 1, 1),
        "AR 1 PO 73": date(2023, 1, 1),
        "AR 1 PO 32 PTA (a) PTA (ii)": date(2023, 12, 8),
        "AR 1 PO 32 PTA (c)": date(2023, 12, 8),
        "AR 3 PO 5": date(2023, 12, 8),
    }


def test_the_2021_amender_raises_no_doubt_at_all() -> None:
    """The measurement this step exists for. Nothing guarded, nothing unread.

    Article 1 of that act drafts 200 instructions and defers 19 of them. Guarding the article
    took the date away from all 200; reading the sentence in full takes it away from 19.
    """
    found = read_effect_dates([fromstring(ARTICLE_6.read_bytes())])
    assert found.unread == 0
    assert found.guarded == ()


def test_a_point_the_act_never_deferred_keeps_the_day_its_notice_publishes() -> None:
    """The three steps compose here or none of them reaches this act.

    The act's own text writes no day for the act as a whole, and its notice dates four parts of
    it separately, which on its own is no act-wide answer: the notice never says which part.
    The four days are exactly the four this article attributes to coordinates, so the staging
    is placed and the act's entry into force stands for everything it did not defer.
    """
    read = read_effect_dates([fromstring(ARTICLE_6.read_bytes())])
    staged = tuple(
        NoticeDate(value=item.effective, kind=DateKind.APPLICATION, comment="MA/PART V ART 6")
        for item in read.deferrals
    )
    entry = NoticeDate(value=date(2021, 12, 7), kind=DateKind.ENTRY_INTO_FORCE)

    found = read_effect_dates(
        [fromstring(ARTICLE_6.read_bytes())], dates=ActDates(entries=(entry, *staged))
    )
    assert found.published == date(2021, 12, 7)
    assert found.for_clause("Article 4 is deleted;", "AR 001 (57)") == (
        date(2021, 12, 7),
        EffectDateSource.NOTICE,
    )
    assert found.for_clause("Article 4 is deleted;", "AR 001 (38)") == (
        date(2021, 1, 1),
        EffectDateSource.FINAL_PROVISIONS,
    )


def test_a_notice_this_reader_cannot_place_keeps_answering_nothing() -> None:
    """A staged day no statement of the act attributes leaves the notice where it was.

    The act-wide answer is withheld because the notice does not say what its staged entry
    covers, and a reader that has not read that day either cannot place it for the notice.
    """
    read = read_effect_dates([fromstring(ARTICLE_6.read_bytes())])
    staged = (
        *(
            NoticeDate(value=item.effective, kind=DateKind.APPLICATION, comment="MA/PART V ART 6")
            for item in read.deferrals
        ),
        NoticeDate(value=date(2025, 5, 5), kind=DateKind.APPLICATION, comment="MA/PART V ART 6"),
    )
    entry = NoticeDate(value=date(2021, 12, 7), kind=DateKind.ENTRY_INTO_FORCE)

    found = read_effect_dates(
        [fromstring(ARTICLE_6.read_bytes())], dates=ActDates(entries=(entry, *staged))
    )
    assert found.published is None


# ------------------------------------------------------------- every refusal still refuses


def test_a_range_of_articles_still_takes_the_default_from_the_whole_act() -> None:
    """ "Articles 95 to 98" names two units and means four, and nothing here changes that."""
    found = act(
        APPLIES, "Articles 95 to 98 shall apply from <DATE ISO='20260626'>26 June 2026</DATE>."
    )
    assert found.default is None
    assert found.unread == 1
    assert found.deferrals == ()


def test_a_range_of_points_is_a_fragment_that_does_not_resolve() -> None:
    """ "points (11) to (14)" names two and means four, one nesting level down.

    The enumeration grammar covers a list and not a span, so the whole statement falls back to
    the reading that keeps the first coordinate and guards the article it named.
    """
    found = act(
        APPLIES,
        "Article 1, point (7)(g), and points (11) to (14), shall apply from "
        "<DATE ISO='20260305'>5 March 2026</DATE>.",
    )
    assert ProvisionLocation.parse("AR 1") in found.guarded
    assert found.for_clause("Article 4 is deleted;", "AR 001 (9)") == (
        None,
        EffectDateSource.UNREAD,
    )


def test_a_statement_that_names_a_second_act_is_not_read_in_full() -> None:
    """A coordinate of the amended act is not a coordinate of the amending one.

    *"as regards Article 104a of Regulation (EU) No 575/2013"* is a description of what a point
    does, in another act's numbering, and reading it as a list would defer a provision this act
    does not contain.
    """
    found = act(
        APPLIES,
        "Point (53), as regards Article 104a of Regulation (EU) No 575/2013, and points (55) "
        "and (69) of Article 1 of this Regulation shall apply from "
        "<DATE ISO='20230628'>28 June 2023</DATE>.",
    )
    assert deferred(found) != {
        "AR 1 PO 55": date(2023, 6, 28),
        "AR 1 PO 69": date(2023, 6, 28),
    }
    assert found.guarded != ()


def test_a_list_written_somewhere_else_still_guards_the_article_it_names() -> None:
    """ "The following points of Article 1 … :" writes its points in the sub-list below it.

    Nothing in the statement names them, so the article stays guarded exactly as it was.
    """
    found = act(
        APPLIES,
        "The following points of Article 1 of this Regulation shall apply from "
        "<DATE ISO='20190627'>27 June 2019</DATE>:",
    )
    assert found.guarded == (ProvisionLocation.parse("AR 1"),)
    assert found.default == date(2021, 6, 28)
    assert found.for_clause("Article 4 is deleted;", "AR 001 (7)") == (
        None,
        EffectDateSource.UNREAD,
    )


def test_a_scope_article_still_says_nothing_about_a_day() -> None:
    """ "This Regulation shall apply to devices" is not an article about dates at all."""
    found = act(
        "This Regulation shall apply to devices placed on the market after "
        "<DATE ISO='20210526'>26 May 2021</DATE>."
    )
    assert found.default is None
    assert found.deferrals == ()


# ------------------------------------------------------------ a list of one is a list of one


def test_a_single_point_reads_exactly_as_it_did_before() -> None:
    """One coordinate, one deferral, and the act's default for everything else."""
    found = act(
        APPLIES,
        "Article 1, point (5), shall apply from <DATE ISO='20220101'>1 January 2022</DATE>.",
    )
    assert found.deferrals == (
        Deferral(location=ProvisionLocation.parse("AR 1 PO 5"), effective=date(2022, 1, 1)),
    )
    assert found.guarded == ()
    assert found.for_clause("Article 4 is deleted;", "AR 001 (7)") == (
        date(2021, 6, 28),
        EffectDateSource.ACT_DEFAULT,
    )


# ---------------------------------------------------------------------------- the grammar


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Article 1, point (5)", ["AR 1 PO 5"]),
        ("Article 1, points (1) and (2)", ["AR 1 PO 1", "AR 1 PO 2"]),
        ("points (2) and (3) of Article 63", ["AR 63 PO 2", "AR 63 PO 3"]),
        ("point (30) of Article 62", ["AR 62 PO 30"]),
        ("Point (24) of Article 1 of this Regulation", ["AR 1 PO 24"]),
        ("Article 1, point (1), and Article 2, point (1)", ["AR 1 PO 1", "AR 2 PO 1"]),
        ("Annex I, point (3)(a)", ["AN I PO 3 PTA (a)"]),
        ("However, Article 1, point (5)", ["AR 1 PO 5"]),
    ],
)
def test_the_shapes_the_drafting_writes_a_list_in(subject: str, expected: list[str]) -> None:
    """Both nesting orders, one or several units, one or several points, and a connective."""
    found = read_enumerated(subject)
    assert found is not None
    assert [where.canonical for where in found] == expected


@pytest.mark.parametrize(
    "subject",
    [
        "The following points of Article 1",
        "Article 1, points (11) to (14)",
        "Article 1, points (55) and (69) of Regulation (EU) No 575/2013",
        "Point (46)(b) of Article 1 of this Regulation, containing the provisions on own funds",
        "Article 1, point 33, points (a) and (b)",
        "Article 2(25), (43) and (82)",
        "This Regulation",
        "Articles 95 to 98",
    ],
)
def test_anything_this_grammar_does_not_cover_in_full_is_refused(subject: str) -> None:
    """Refusal is the safe direction: the caller then reads the statement as it always did."""
    assert read_enumerated(subject) is None
