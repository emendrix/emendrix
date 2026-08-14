"""Provision trees: build, look up, iterate, and keep the two text forms apart."""

from datetime import date

import pytest

from emendrix.core.identifiers import ActId, VersionId
from emendrix.core.location import ProvisionLocation
from emendrix.core.provisions import (
    ComparisonText,
    DateMention,
    ProvisionNode,
    ProvisionText,
    ProvisionTree,
    normalize_for_comparison,
)

ACT = ActId(corpus="test", key="act", display_name="An act")
VERSION = VersionId("v1")

VERBATIM = "The  duty applies\n   from 2 December 2027."


def _tree() -> ProvisionTree:
    article_five = ProvisionNode.from_plain_text(
        "AR 5",
        "Prohibited practices.",
        heading="Prohibited practices",
        children=(
            ProvisionNode.from_plain_text("AR 5 PA 1", "The following are prohibited:"),
            ProvisionNode.from_plain_text("AR 5 PA 2", "Paragraph 1 does not apply where:"),
        ),
    )
    annex = ProvisionNode.from_plain_text("AN III", "High-risk use cases.")
    return ProvisionTree(act=ACT, version=VERSION, language="ENG", roots=(article_five, annex))


def test_walk_is_document_order() -> None:
    assert [node.location.canonical for node in _tree().walk()] == [
        "AR 5",
        "AR 5 PA 1",
        "AR 5 PA 2",
        "AN III",
    ]


def test_lookup_by_location() -> None:
    tree = _tree()
    found = tree.find("AR 5 PA 2")
    assert found is not None
    assert found.text.startswith("Paragraph 1")
    assert tree.find(ProvisionLocation.parse("AR 5 PA 2")) is found
    assert tree.find("AR 6") is None
    assert tree.find("AR 5 PA 3") is None


def test_unit_locations_are_the_top_level_units() -> None:
    assert [location.canonical for location in _tree().unit_locations()] == ["AR 5", "AN III"]


def test_verbatim_text_is_never_normalised() -> None:
    node = ProvisionNode.from_plain_text("AR 1", VERBATIM)
    assert node.text == VERBATIM
    assert "\n" in node.text
    assert "  " in node.text


def test_comparison_form_is_separate_and_collapsed() -> None:
    node = ProvisionNode.from_plain_text("AR 1", VERBATIM)
    assert node.comparison_text == "The duty applies from 2 December 2027."
    assert str(node.comparison_text) != str(node.text)


def test_comparison_form_is_not_derived_at_compare_time() -> None:
    """Two nodes may agree verbatim-differently: the parser owns the comparison form.

    Whitespace at element boundaries, not structure, is what broke comparison across
    Formex generations. The model therefore stores
    the comparison form the extractor built; nothing recomputes it from `text`.
    """
    spaced = ProvisionNode(
        location=ProvisionLocation.parse("AR 1"),
        text=ProvisionText("oneword"),
        comparison_text=ComparisonText("one word"),
    )
    unspaced = ProvisionNode.from_plain_text("AR 1", "oneword")
    assert spaced.text == unspaced.text
    assert spaced.comparison_text != unspaced.comparison_text


def test_normalize_for_comparison_is_pure() -> None:
    assert normalize_for_comparison("  a \n\t b  ") == "a b"
    assert normalize_for_comparison("") == ""


def test_a_no_break_space_is_whitespace_and_a_typographic_character_is_not() -> None:
    """The comparison form normalises layout and never the characters a drafter chose.

    A version whose only delta is typographic therefore reports `MODIFIED`, which is the
    intended answer: ruling character swaps equivalent needs a table of equivalences, and that
    normalises the source rather than its layout. The asymmetry decides it. Over-reporting
    costs a reader one word-level diff; under-reporting says a provision is unchanged when it
    is not. Both halves are asserted here so neither drifts, and the strings are synthetic.
    """
    assert normalize_for_comparison("a\u00a0b") == normalize_for_comparison("a b")
    assert normalize_for_comparison("matter'") != normalize_for_comparison("matter`")


def test_dates_ride_along_with_their_context() -> None:
    node = ProvisionNode.from_plain_text(
        "AR 113",
        VERBATIM,
        dates=(DateMention(value=date(2027, 12, 2), context="applies from 2 December 2027"),),
    )
    assert node.dates[0].value == date(2027, 12, 2)
    assert "2027" in node.dates[0].context


def test_a_child_outside_its_parent_is_rejected() -> None:
    with pytest.raises(ValueError, match="not within"):
        ProvisionNode.from_plain_text(
            "AR 5",
            "text",
            children=(ProvisionNode.from_plain_text("AR 6 PA 1", "text"),),
        )


def test_nodes_are_frozen() -> None:
    node = ProvisionNode.from_plain_text("AR 1", "text")
    with pytest.raises(ValueError, match="frozen"):
        node.heading = "no"


def test_an_empty_provision_text_is_still_a_text() -> None:
    node = ProvisionNode.from_plain_text("AR 1", "")
    assert node.text == ""
    assert node.comparison_text == ""
