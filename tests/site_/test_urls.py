"""Anchors and hrefs: canonical identifiers in, stable URL parts out."""

from __future__ import annotations

import pytest

from emendrix.site_.urls import (
    act_href,
    amendment_href,
    amendments_href,
    change_anchor,
    depth_of,
    domain_anchor,
    entry_anchors,
    event_href,
    location_slug,
    provision_href,
    shared_path,
    up,
)


def test_location_slugs_are_lowercase_hyphenated_and_parenthesis_free() -> None:
    assert location_slug("AR 13") == "ar-13"
    assert location_slug("AR 5 PA 1 ALN 1 PTA (bb)") == "ar-5-pa-1-aln-1-pta-bb"
    assert location_slug("AN III") == "an-iii"
    assert location_slug("AR 3.20") == "ar-3.20"


def test_distinct_canonical_locations_keep_distinct_slugs() -> None:
    codes = ["AR 5", "AR 5 PA 1", "AR 5 PA 1 ALN 1", "AR 5 PA 1 ALN 1 PTA (bb)", "AN III", "AN I"]
    slugs = [location_slug(code) for code in codes]
    assert len(set(slugs)) == len(slugs)


def test_a_parenthesised_point_and_its_bare_twin_share_a_slug() -> None:
    """The one collision the slug alphabet allows, pinned so the docstring cannot drift off it.

    Dropping the parentheses is what does it. Nothing writes the bare form: the Formex reader
    parenthesises every `PTA` and `PTI` value and leaves every `PO` value bare, and a change
    location is a top-level unit that carries no point segment at all. So this is documented
    behaviour rather than a defect, and the assertion exists so the two stay in step.
    """
    assert location_slug("AR 5 PTA (bb)") == location_slug("AR 5 PTA bb") == "ar-5-pta-bb"


def test_a_change_anchor_is_entry_key_then_location_then_occurrence() -> None:
    assert change_anchor("02017R0745-20200424", "AR 1") == "02017R0745-20200424-ar-1"
    assert change_anchor("02017R0745-20200424", "AR 1", occurrence=2) == (
        "02017R0745-20200424-ar-1-2"
    )


def test_occurrence_below_one_is_refused() -> None:
    with pytest.raises(ValueError):
        change_anchor("k", "AR 1", occurrence=0)


def test_one_entrys_anchors_number_the_repeats_and_leave_the_first_bare() -> None:
    anchors = entry_anchors("k", ["AR 1", "AR 2", "AR 1", "AR 1 PA 1"])
    assert anchors == ("k-ar-1", "k-ar-2", "k-ar-1-2", "k-ar-1-pa-1")
    assert entry_anchors("k", []) == ()


def test_act_href_and_relative_prefix() -> None:
    assert act_href("32016R0679") == "acts/32016R0679/"
    assert up(0) == ""
    assert up(2) == "../../"


def test_depth_counts_the_separators_of_a_site_root_relative_path() -> None:
    """A file at the root is depth 0 just as the root itself is: `404.html` is not one down."""
    assert depth_of("") == 0
    assert depth_of("404.html") == 0
    assert depth_of("acts/") == 1
    assert depth_of("acts/x/") == 2


def test_an_act_page_sits_two_directories_down() -> None:
    """The number `pages/act.py` holds as a literal, because its path needs an act to exist."""
    assert depth_of(act_href("32024R1689")) == 2


def test_an_event_page_nests_under_its_act() -> None:
    """One directory scheme, not two: the event path is the act path plus the entry key."""
    assert event_href("32016R0679", "02016R0679-20160504") == (
        "acts/32016R0679/02016R0679-20160504/"
    )
    assert event_href("32016R0679", "k").startswith(act_href("32016R0679"))


def test_an_event_page_sits_three_directories_down() -> None:
    """The number `pages/event.py` holds as a literal, because its path needs an entry to exist."""
    assert depth_of(event_href("32024R1689", "02024R1689-20260727")) == 3


def test_a_provision_is_addressed_under_its_act_by_its_location_slug() -> None:
    """The canonical string's slug, never a human reading of it: `Annex XVII` is what the
    page's title says and `an-xvii` is what its address says, and a second numbering for one
    coordinate would be a second thing to keep in step."""
    assert provision_href("32024R1689", "AR 6") == "acts/32024R1689/ar-6/"
    assert provision_href("32006R1907", "AN XVII") == "acts/32006R1907/an-xvii/"
    assert provision_href("32019R0881", "AN") == "acts/32019R0881/an/"
    assert provision_href("32013R0575", "TIT") == "acts/32013R0575/tit/"
    assert provision_href("32024R1689", "AR 6").startswith(act_href("32024R1689"))


def test_a_provision_page_sits_three_directories_down() -> None:
    """The number `pages/provision.py` holds as a literal, and the same depth as an event
    page: the two are siblings under the act, which is why one links the other with `../`."""
    assert depth_of(provision_href("32024R1689", "AR 6")) == 3
    assert depth_of(provision_href("32024R1689", "AR 6")) == depth_of(
        event_href("32024R1689", "02024R1689-20260727")
    )


def test_an_event_key_and_a_provision_slug_that_would_share_a_path_are_found() -> None:
    """The two vocabularies under one act are not disjoint by construction, so the collision
    is looked for rather than assumed away. Real keys and real slugs never meet: a key is a
    version identifier and a slug is a location code."""
    keys = ["02024R1689-20260727", "32024R1689"]
    assert shared_path(keys, ["AR 6", "AN XVII"]) is None
    assert shared_path(keys, []) is None
    assert shared_path(["ar-6"], ["AN I", "AR 6"]) == ("ar-6", "AR 6")


def test_an_amending_instrument_is_addressed_by_its_own_key() -> None:
    """The key, made path-safe by the function that names an act's directory, and nothing else.

    A year-and-number path would need this module to read the identifier, which is the corpus
    vocabulary the whole package is kept clear of; the human number lives in the page's title.
    """
    assert amendments_href() == "amendments/"
    assert amendment_href("32026R1744") == "amendments/32026R1744/"
    assert amendment_href("house-rules-amendment-1") == "amendments/house-rules-amendment-1/"
    assert amendment_href("a/b").count("/") == 2


def test_the_two_amendment_addresses_sit_one_and_two_directories_down() -> None:
    """The literals `pages/amendments_index.py` and `pages/amendment.py` hold."""
    assert depth_of(amendments_href()) == 1
    assert depth_of(amendment_href("32026R1744")) == 2


def test_a_domain_becomes_the_id_the_roster_and_the_act_pages_share() -> None:
    """One function, so the heading and the link that reaches it cannot drift apart. Two
    labels that differ only in the characters the slug drops share an id, which costs a
    repeated heading id and never a link that goes somewhere wrong; it is pinned rather than
    engineered away, as the same case in `location_slug` is."""
    assert domain_anchor("Digital") == "Digital"
    assert domain_anchor("Data & privacy") == domain_anchor("Data privacy") == "Data_privacy"
    assert domain_anchor("Chemicals") != domain_anchor("Health")
