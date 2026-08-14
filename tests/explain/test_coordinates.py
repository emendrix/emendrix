"""The coordinate recogniser: model prose in, canonical locations out, nothing invented.

Every sentence here is obviously synthetic; no legal content. The asymmetry under test is the
design itself: a mention the recogniser misses is a silent undercount and acceptable, a
mention it invents becomes a wrong published number and is not. So the catching tests pin the
forms it must read, and every refusal has a test of its own.
"""

from __future__ import annotations

from emendrix.core import ProvisionLocation
from emendrix.explain import mentioned_locations

UNIT = ProvisionLocation.parse("AR 57")


def canon(sentence: str, unit: ProvisionLocation = UNIT) -> set[str]:
    return {location.canonical for location in mentioned_locations(sentence, unit)}


# ------------------------------------------------------------------ the forms it must catch


def test_a_single_paragraph() -> None:
    assert canon("Paragraph 3 now requires a synthetic notice.") == {"AR 57 PA 3"}


def test_a_list_joined_with_and() -> None:
    assert canon("Paragraphs 1 and 2 remain worded as they were.") == {
        "AR 57 PA 1",
        "AR 57 PA 2",
    }


def test_a_comma_list() -> None:
    assert canon("paragraphs 2, 3 and 4 are reworded.") == {
        "AR 57 PA 2",
        "AR 57 PA 3",
        "AR 57 PA 4",
    }


def test_a_range_names_its_endpoints_and_is_never_expanded() -> None:
    """`paragraphs 1 to 4` wrote down two coordinates; asserting 2 and 3 as well would put
    coordinates in the count that no sentence named."""
    assert canon("Paragraphs 1 to 4 are replaced.") == {"AR 57 PA 1", "AR 57 PA 4"}


def test_a_point_written_directly_against_its_paragraph() -> None:
    assert canon("paragraphs 9(e) and 10 add references.") == {
        "AR 57 PA 9 PTA (e)",
        "AR 57 PA 10",
    }


def test_the_provisions_own_article_form() -> None:
    assert canon("Article 57(12) is said to exist.") == {"AR 57 PA 12"}
    assert canon("Article 57(1)(a) is tightened.") == {"AR 57 PA 1 PTA (a)"}


def test_a_lettered_article_number() -> None:
    unit = ProvisionLocation.parse("AR 4a")
    assert canon("Paragraph 2 is new.", unit) == {"AR 4a PA 2"}
    assert canon("Article 4a(1) opens with a definition.", unit) == {"AR 4a PA 1"}


# ------------------------------------------------------------------ the refusals


def test_a_foreign_article_number_is_not_a_coordinate_of_this_provision() -> None:
    assert canon("Article 10(5) sets out a synthetic duty.") == set()


def test_a_reference_into_another_instrument_is_never_recognised() -> None:
    assert canon("It mirrors Article 11(13) of Directive 93/42/EEC.") == set()
    assert canon("Article 57(2) of that Regulation is cited.") == set()


def test_a_paragraph_of_something_else_is_never_recognised() -> None:
    assert canon("The duty in paragraph 1 of Article 10 applies.") == set()
    assert canon("paragraphs 2 and 3 of Annex I are listed.") == set()


def test_an_ambiguous_numeric_group_stops_at_the_paragraph() -> None:
    """`9(1)` could be a point or a subparagraph; the paragraph is all the sentence safely
    named, so the paragraph is all that is recognised."""
    assert canon("Paragraph 9(1) is amended.") == {"AR 57 PA 9"}


def test_an_annex_unit_recognises_nothing() -> None:
    """Annex prose numbers its parts in vocabularies this recogniser cannot map to canonical
    codes without guessing, so for a non-article unit it stays silent."""
    assert canon("Paragraph 3 changes.", ProvisionLocation.parse("AN XIV")) == set()
    assert canon("Article 57(1) is cited.", ProvisionLocation.parse("AN III")) == set()


def test_prose_with_no_coordinates_yields_nothing() -> None:
    assert canon("The synthetic obligation is broadened in scope.") == set()


def test_a_bare_article_reference_is_not_a_sub_coordinate() -> None:
    """Naming the article itself claims nothing below the unit, so there is nothing to check."""
    assert canon("Article 57 is restructured.") == set()
