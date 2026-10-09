"""The anchor rule, over the shapes the site's own tests pin.

The equality with the site's functions is held by `tests/output/test_record_contract.py` in the
`emendrix` suite, which can import both; these tests pin the rule on its own.
"""

from __future__ import annotations

import pytest

from emendrix_record.links import change_anchor, entry_anchors, location_slug


@pytest.mark.parametrize(
    ("canonical", "slug"),
    [
        ("AR 5", "ar-5"),
        ("AN III", "an-iii"),
        ("AR 5 PA 1 ALN 1 PTA (bb)", "ar-5-pa-1-aln-1-pta-bb"),
        ("  AR  4a ", "ar-4a"),
    ],
)
def test_a_location_slugs_lowercase_hyphenated_without_parentheses(
    canonical: str, slug: str
) -> None:
    assert location_slug(canonical) == slug


def test_the_first_occurrence_carries_no_suffix_and_later_ones_do() -> None:
    assert change_anchor("v2", "AR 5") == "v2-ar-5"
    assert change_anchor("v2", "AR 5", 1) == "v2-ar-5"
    assert change_anchor("v2", "AR 5", 3) == "v2-ar-5-3"


@pytest.mark.parametrize("occurrence", [0, -1])
def test_an_occurrence_below_one_is_refused(occurrence: int) -> None:
    with pytest.raises(ValueError, match="counts from 1"):
        change_anchor("v2", "AR 5", occurrence)


def test_entry_anchors_count_each_location_in_entry_order() -> None:
    assert entry_anchors("v3", ["AR 2", "AN I", "AR 2", "AR 2"]) == (
        "v3-ar-2",
        "v3-an-i",
        "v3-ar-2-2",
        "v3-ar-2-3",
    )
    assert entry_anchors("v3", []) == ()
