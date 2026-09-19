"""The roster cut: an official title keeps its subject, and every elision is marked.

The titles below are recorded official titles, copied from committed changelog documents with
their no-break spaces, because the rule exists for the shapes the corpus actually records.
"""

from __future__ import annotations

from typing import Final

import pytest

from emendrix.output.markdown import TITLE_CAP, short_title
from emendrix.site_.titling import subject_cut

_FIC_AMENDMENT: Final = (
    "Commission Delegated Regulation (EU) 2024/2512 of 17\xa0April 2024 amending Annex\xa0II to "
    "Regulation (EU) No\xa01169/2011 of the European Parliament and of the Council on the "
    "provision of food information to consumers, as regards behenic acid from mustard seeds to "
    "be used in the manufacturing of certain emulsifiers"
)
_GLUTEN: Final = (
    "Commission Delegated Regulation (EU) No\xa01155/2013 of 21\xa0August 2013 amending "
    "Regulation (EU) No\xa01169/2011 of the European Parliament and of the Council on the "
    "provision of food information to consumers as regards information on the absence or "
    "reduced presence of gluten in food"
)
_BRRD: Final = (
    "Directive 2014/59/EU of the European Parliament and of the Council of 15\xa0May 2014 "
    "establishing a framework for the recovery and resolution of credit institutions and "
    "investment firms and amending Council Directive 82/891/EEC, and Directives 2001/24/EC, "
    "2002/47/EC, 2004/25/EC, 2005/56/EC, 2007/36/EC, 2011/35/EU, 2012/30/EU and 2013/36/EU"
)
_FIC: Final = (
    "Regulation (EU) No\xa01169/2011 of the European Parliament and of the Council of "
    "25\xa0October 2011 on the provision of food information to consumers, amending "
    "Regulations (EC) No\xa01924/2006 and (EC) No\xa01925/2006 of the European Parliament and "
    "of the Council"
)


def _fragments(cut: str) -> list[str]:
    """What the cut kept, between its markers."""
    return [part.strip() for part in cut.split("[…]") if part.strip()]


def test_a_title_under_the_cap_is_returned_unchanged() -> None:
    title = "Regulation (EU) 2024/1689 on artificial intelligence"
    assert subject_cut(title) == title


def test_the_opening_clause_the_row_repeats_is_dropped_and_marked() -> None:
    cut = subject_cut(_FIC_AMENDMENT)
    assert cut.startswith("[…] amending Annex\xa0II")
    assert "2024/2512" not in cut


def test_the_as_regards_tail_survives_with_both_elisions_marked() -> None:
    for title, subject in ((_FIC_AMENDMENT, "behenic acid"), (_GLUTEN, "gluten in food")):
        cut = subject_cut(title)
        assert "as regards" in cut, cut
        assert subject in cut, cut
        assert cut.count("[…]") >= 2, cut
        assert len(cut) <= TITLE_CAP, cut


def test_a_title_with_no_subject_phrase_is_cut_from_its_head_and_marked() -> None:
    cut = subject_cut(_BRRD)
    assert cut.startswith("[…] establishing a framework")
    assert cut.endswith(" […]")
    assert len(cut) <= TITLE_CAP


def test_an_act_s_own_title_starts_at_its_subject() -> None:
    assert subject_cut(_FIC).startswith("[…] on the provision of food information to consumers")


def test_a_title_the_opening_rule_does_not_know_is_cut_as_the_changelog_cuts_it() -> None:
    title = "Corrigendum to " + _FIC_AMENDMENT
    assert subject_cut(title) == short_title(title)


@pytest.mark.parametrize("title", [_FIC_AMENDMENT, _GLUTEN, _BRRD, _FIC])
@pytest.mark.parametrize("cap", [60, 90, TITLE_CAP])
def test_nothing_kept_is_altered_and_nothing_exceeds_the_cap(title: str, cap: int) -> None:
    """Every kept fragment is a run of the source, no-break spaces and all."""
    cut = subject_cut(title, cap)
    assert len(cut) <= cap
    assert "[…]" in cut
    for fragment in _fragments(cut):
        assert fragment in title, fragment
