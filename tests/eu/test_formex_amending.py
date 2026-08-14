"""The amending-act parser, against the Digital Omnibus.

An insertion is the case the prose cannot carry: EU drafting writes *"the following Article is
inserted:"* without the number, so the identifier exists only in the quoted `ARTICLE` element.
These tests pin that the markup is read for it, on the act that shows the shape most clearly.
"""

from __future__ import annotations

from xml.etree import ElementTree

import pytest

from emendrix.core import AmendingActDoc, QuotedProvision
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import Formex4Parser, parse_amending_act
from emendrix.eu.formex.amending import named_act
from eu_pins import AI_ACT, DIGITAL_OMNIBUS, package

INSERTED_ARTICLES = ("AR 4a", "AR 60a", "AR 75a", "AR 75b", "AR 75c", "AR 75d")
"""The six insertions of `32026R1744`, confirmed against the OJ text."""


@pytest.fixture
def omnibus(client: CellarClient) -> AmendingActDoc:
    return parse_amending_act(package(client, DIGITAL_OMNIBUS, DIGITAL_OMNIBUS)).document


def locations(quoted: tuple[QuotedProvision, ...], act: str) -> list[str]:
    return [
        provision.location.canonical
        for provision in quoted
        if provision.location is not None
        and provision.amended_act is not None
        and provision.amended_act.key == act
    ]


def test_the_amending_act_is_first_of_all_an_act(omnibus: AmendingActDoc) -> None:
    """Its own four articles and its own annex; the quoted articles are not units of it."""
    assert [unit.canonical for unit in omnibus.tree.unit_locations()] == [
        "AR 1",
        "AR 2",
        "AR 3",
        "AR 4",
        "AN XIV",
    ]


def test_the_acts_it_amends_are_read_off_its_instruction_articles(
    omnibus: AmendingActDoc,
) -> None:
    """`Article 1` / `Amendments to Regulation (EU) 2024/1689`, and two more like it."""
    assert [act.key for act in omnibus.amends] == [AI_ACT, "32018R1139", "32023R1230"]


def test_every_inserted_article_is_recovered_with_its_identifier(
    omnibus: AmendingActDoc,
) -> None:
    """The prose omits these six numbers and the markup carries them."""
    found = locations(omnibus.quoted, AI_ACT)
    for article in INSERTED_ARTICLES:
        assert article in found


def test_quoted_provisions_are_scoped_to_the_act_their_instruction_names(
    omnibus: AmendingActDoc,
) -> None:
    """One amending act, three amended regulations: an unscoped list would cross-attribute.

    Measured 2026-08-06: 73 quotations, 62 of them the AI Act's.
    """
    assert len(omnibus.quoted) == 73
    assert len(locations(omnibus.quoted, AI_ACT)) == 62
    assert len(locations(omnibus.quoted, "32018R1139")) == 7
    assert len(locations(omnibus.quoted, "32023R1230")) == 4
    assert all(provision.location is not None for provision in omnibus.quoted)


def test_a_quoted_paragraph_names_its_article_too(omnibus: AmendingActDoc) -> None:
    """`<PARAG IDENTIFIER="005.001A">` is `AR 5 PA 1a`: article and paragraph in one value.

    Each of these is a location the AI Act's CELLAR modification metadata also publishes
    (`celex_32024R1689.branch.xml`), which is what makes the two signals comparable at all.
    """
    found = locations(omnibus.quoted, AI_ACT)
    for location in ("AR 5 PA 1a", "AR 57 PA 3a", "AR 2 PA 13", "AR 75 PA 2a"):
        assert location in found


def test_only_the_outermost_quotation_is_reported(omnibus: AmendingActDoc) -> None:
    """A quoted article's own paragraphs are part of it, not further quotations.

    `AR 4` is quoted whole (a replacement) and carries three paragraphs; none of them appears
    beside it as `AR 4 PA 1`.
    """
    found = locations(omnibus.quoted, AI_ACT)
    assert "AR 4" in found
    assert not [location for location in found if location.startswith("AR 4 PA")]


def test_quoted_text_is_verbatim(omnibus: AmendingActDoc) -> None:
    """What the amending act quotes is quoted back unnormalised, like any other stored text."""
    inserted = next(
        provision
        for provision in omnibus.quoted
        if provision.location is not None and provision.location.canonical == "AR 4a"
    )
    assert inserted.text.startswith("Article\xa04a")
    assert inserted.comparison_text.startswith("Article 4a Processing of special categories")
    assert "bias detection" in inserted.comparison_text


@pytest.mark.parametrize(
    ("subtitle", "expected"),
    [
        # Post-2015 numbering: year first, no `No`. Both forms taken from real act titles.
        ("Amendments to Regulation (EU) 2024/1689", "32024R1689"),
        ("Amendments to Regulation (EU) 2018/1139", "32018R1139"),
        # Pre-2015 numbering: number first, and `No` is the only marker that says so. Four
        # digits either side, so reading it positionally would yield `31907R2006`.
        ("Amendments to Regulation (EC) No 1907/2006", "32006R1907"),
        ("Amendments to Regulation (EC) No 1272/2008", "32008R1272"),
        ("Amendments to Regulation (EU) No 1025/2012", "32012R1025"),
        # No answer beats a wrong one: a two-digit year, and a form the grammar does not read.
        ("Amendments to Regulation (EEC) No 2913/92", None),
        ("Amendments to Directive 2011/93/EU", None),
        ("Entry into force and application", None),
    ],
)
def test_the_cited_act_is_read_by_the_numbering_convention(
    subtitle: str, expected: str | None
) -> None:
    """A markup double, not a fixture: only the citation grammar is under test here.

    The order of the two numbers flipped with the 2015 numbering reform and digit length
    cannot tell them apart: `1907/2006` is four digits on both sides.
    """
    article = ElementTree.fromstring(
        f"<ARTICLE IDENTIFIER='001'><TI.ART>Article 1</TI.ART>"
        f"<STI.ART>{subtitle}</STI.ART></ARTICLE>"
    )
    found = named_act(article)
    assert (None if found is None else found.key) == expected


def test_the_parser_object_returns_the_same_document(client: CellarClient) -> None:
    """`Formex4Parser` is what the adapter holds; its coverage report rides alongside."""
    fetched = package(client, DIGITAL_OMNIBUS, DIGITAL_OMNIBUS)
    parser = Formex4Parser()
    read = parser.read_amending(fetched)
    assert parser.parse_amending(fetched) == read.document
    assert read.coverage.clean
    assert read.coverage.units == 5
