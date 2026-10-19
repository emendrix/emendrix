"""The twin note under a change and the twin line on a provision page, in their own words.

The three answers to "did the same amending act change it?" are built from small entries: the
sister act's copy of the same attributed entry gives the instrument an event there, an
unattributed copy gives it none. "Did not amend" is never said, because the record may simply
not hold the event, and no note says a provision should change or is equivalent to another.
"""

from __future__ import annotations

from datetime import date

import pytest
from helpers import text_of
from site_entries import attributed_entry, unattributed_entry
from toy_twins import SISTER, pair, sister_of, toy_map, toy_site

from emendrix.core import ProvisionLocation
from emendrix.output import ChangelogEntry
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.twin_inputs import TwinMaps
from emendrix.site_.twin_note import SIMILAR, twin_line, twin_note
from emendrix.twins.model import TwinPair
from toy_corpus import HOUSE_RULES

ROOT = "../../../"


def _notes(site: SiteInputs, entry: ChangelogEntry, unit: str) -> str:
    act = next(item for item in site.acts if item.act == HOUSE_RULES)
    (emitted,) = [e for e in entry.changes if e.change.location.canonical == unit]
    return "\n".join(twin_note(site, act, entry, emitted, ROOT))


def _site(
    *pairs: TwinPair, sister: ChangelogEntry, urls: dict[str, dict[str, str]] | None = None
) -> SiteInputs:
    """The toy act's attributed entry beside `sister` recorded under the sister act."""
    maps = TwinMaps(maps=(toy_map(*pairs),), urls=urls or {})
    return toy_site(attributed_entry(), sister_of(sister), maps=maps)


def test_yes_when_the_instruments_sister_event_changed_the_twin() -> None:
    site = _site(pair("AR 2", "AR 2"), sister=attributed_entry())
    note = text_of(_notes(site, attributed_entry(), "AR 2"))
    assert "The same amending act changed it: yes." in note


def test_no_when_the_instruments_sister_event_changed_other_units_only() -> None:
    site = _site(pair("AR 2", "AR 9"), sister=attributed_entry())
    note = text_of(_notes(site, attributed_entry(), "AR 2"))
    assert "The same amending act changed it: no." in note


def test_the_record_holding_no_sister_event_is_said_as_exactly_that() -> None:
    site = _site(pair("AR 2", "AR 2"), sister=unattributed_entry())
    note = text_of(_notes(site, attributed_entry(), "AR 2"))
    assert "The record holds no house-rules-sister version made by the same amending act." in note
    assert "changed it" not in note


def test_an_event_no_instrument_is_named_for_gets_no_answer() -> None:
    entry = unattributed_entry()
    site = toy_site(
        entry, sister_of(attributed_entry()), maps=TwinMaps(maps=(toy_map(pair("AR 2", "AR 2")),))
    )
    note = text_of(_notes(site, entry, "AR 2"))
    assert "Twin in house-rules-sister:" in note
    assert "amending act" not in note


def test_identical_twins_say_identical_text_instead_of_a_score() -> None:
    site = _site(pair("AR 2", "AR 2", 1.0, identical=True), sister=attributed_entry())
    note = text_of(_notes(site, attributed_entry(), "AR 2"))
    assert f"{SIMILAR} (identical text)" in note
    assert "1.000" not in note


def test_the_note_names_the_partner_of_the_deepest_changed_coordinate() -> None:
    site = _site(
        pair("AN I", "AN II", 0.93, children=(("AN I SLOT 2", "AN II SLOT 5", 0.912),)),
        sister=attributed_entry(),
    )
    note = text_of(_notes(site, attributed_entry(), "AN I"))
    assert f"Twin in house-rules-sister: {ProvisionLocation.parse('AN II SLOT 5').human}, " in note
    assert f"{SIMILAR} (0.912)" in note
    # The sister's own AN I change is at another unit, so it did not touch Annex II slot 5.
    assert "The same amending act changed it: no." in note


def test_without_an_aligned_changed_child_the_unit_twin_is_named() -> None:
    site = _site(
        pair("AN I", "AN II", 0.93, children=(("AN I SLOT 1", "AN II SLOT 1", 0.97),)),
        sister=attributed_entry(),
    )
    note = text_of(_notes(site, attributed_entry(), "AN I"))
    assert "Twin in house-rules-sister: Annex II, " in note
    assert f"{SIMILAR} (0.930)" in note


@pytest.mark.parametrize(
    ("dates", "said"),
    [
        ({"v2": date(2025, 1, 10)}, "paired on both acts&#x27; texts of 10 January 2025."),
        (
            {"v2": date(2025, 1, 10), "v9": date(2026, 1, 1)},
            "paired on this act&#x27;s text of 10 January 2025 and the house-rules-sister text "
            "of 1 January 2026.",
        ),
        ({}, "paired on both acts&#x27; texts of v2."),
    ],
)
def test_the_note_names_the_texts_the_pair_was_computed_on(
    dates: dict[str, date], said: str
) -> None:
    version_b = "v9" if "v9" in dates else "v2"
    entry = attributed_entry()
    document = toy_map(pair("AR 2", "AR 2"), version_b=version_b)
    site = toy_site(entry, sister_of(entry), maps=TwinMaps(maps=(document,), dates=dates))
    assert said in text_of(_notes(site, entry, "AR 2"))


def test_the_twin_links_its_provision_page_where_the_sister_has_one() -> None:
    site = _site(pair("AR 2", "AR 2"), sister=attributed_entry())
    assert f'<a href="{ROOT}acts/house-rules-sister/ar-2/">Art. 2</a>' in _notes(
        site, attributed_entry(), "AR 2"
    )


def test_without_a_sister_page_the_twin_links_eur_lex_and_without_an_address_nothing() -> None:
    url = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:x#art_9"
    linked = _site(pair("AR 2", "AR 9"), sister=attributed_entry(), urls={"v2": {"AR 9": url}})
    note = _notes(linked, attributed_entry(), "AR 2")
    assert f'<a class="ext" href="{url.replace("&", "&amp;")}">Art. 9' in note
    bare = _site(pair("AR 2", "AR 9"), sister=attributed_entry())
    assert "<a " not in _notes(bare, attributed_entry(), "AR 2").replace(_COMPARE_LINK, "")


_COMPARE_LINK = (
    '<a href="../../../twins/toy-house-rules--toy-house-rules-sister/ar-2/">'
    "See where the two texts differ</a>"
)


def test_a_pair_that_differs_links_its_twin_page_and_an_identical_one_does_not() -> None:
    differs = _site(pair("AR 2", "AR 9"), sister=attributed_entry())
    assert _COMPARE_LINK in _notes(differs, attributed_entry(), "AR 2")
    act = next(item for item in differs.acts if item.act == HOUSE_RULES)
    assert _COMPARE_LINK in twin_line(differs, act, "AR 2", ROOT)[0]
    same = _site(pair("AR 2", "AR 2", identical=True), sister=attributed_entry())
    assert "twins/" not in _notes(same, attributed_entry(), "AR 2")


def test_a_unit_with_no_twin_gets_no_note() -> None:
    site = _site(pair("AR 2", "AR 2"), sister=attributed_entry())
    assert _notes(site, attributed_entry(), "AN I") == ""


def test_every_note_glosses_the_word_and_none_claims_more_than_similarity() -> None:
    notes: list[str] = []
    for sister in (attributed_entry(), unattributed_entry()):
        for twin in ("AR 2", "AR 9"):
            site = _site(pair("AR 2", twin), sister=sister)
            act = next(item for item in site.acts if item.act == HOUSE_RULES)
            notes.extend(_notes(site, attributed_entry(), "AR 2").split("\n"))
            notes.extend(twin_line(site, act, "AR 2", ROOT))
    assert notes
    for note in notes:
        words = text_of(note)
        assert SIMILAR in words, words
        for banned in ("should", "equivalent", "did not amend", "same effect"):
            assert banned not in words.casefold(), words


def test_the_provision_line_names_the_unit_twin_and_its_score() -> None:
    site = _site(
        pair("AN I", "AN II", 0.93, children=(("AN I SLOT 2", "AN II SLOT 5", 0.912),)),
        sister=attributed_entry(),
    )
    act = next(item for item in site.acts if item.act == HOUSE_RULES)
    (line,) = twin_line(site, act, "AN I", ROOT)
    assert text_of(line).startswith(f"Twin in house-rules-sister: Annex II, {SIMILAR} (0.930)")
    assert twin_line(site, act, "AR 4", ROOT) == []
    assert SISTER.key in line
