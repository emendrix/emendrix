"""Reading the committed twin maps, and the index the pages look a twin up in.

A map that does not validate is named, not raised, and a map naming an act the site does not
show is left out and named: both are inputs the build states and survives.
"""

from __future__ import annotations

from pathlib import Path

from site_entries import attributed_entry
from toy_twins import SISTER, pair, sister_of, toy_map, toy_site

from emendrix.core import ActId
from emendrix.site_.twin_inputs import TwinMaps, read_twin_maps
from emendrix.twins.build import render
from emendrix.twins.model import twins_path
from toy_corpus import HOUSE_RULES


def test_maps_are_read_in_path_order_and_a_broken_one_is_named_not_raised(tmp_path: Path) -> None:
    first, second = (
        toy_map(pair("AR 2", "AR 2")),
        toy_map(pair("AR 2", "AR 7"), b=ActId(corpus="toy", key="house-rules-twin")),
    )
    for document in (second, first):
        target = tmp_path / twins_path(
            ActId(corpus=document.a.corpus, key=document.a.key),
            ActId(corpus=document.b.corpus, key=document.b.key),
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(document), encoding="utf-8")
    (tmp_path / "twins" / "toy-broken--toy-map.json").write_text("{}", encoding="utf-8")
    read = read_twin_maps(tmp_path)
    assert [document.b.key for document in read.maps] == ["house-rules-sister", "house-rules-twin"]
    assert read.unreadable == ("twins/toy-broken--toy-map.json",)


def test_a_repository_with_no_twins_directory_reads_as_no_maps(tmp_path: Path) -> None:
    assert read_twin_maps(tmp_path) == TwinMaps()


def test_a_map_naming_an_act_the_site_does_not_show_is_ignored_and_named() -> None:
    lonely = toy_map(pair("AR 2", "AR 2"))
    site = toy_site(attributed_entry(), maps=TwinMaps(maps=(lonely,)))
    assert site.twins.units == {}
    assert site.twins.ignored == (f"{HOUSE_RULES} and {SISTER}",)


def test_units_are_indexed_from_both_sides_with_their_aligned_children() -> None:
    document = toy_map(
        pair("AN I", "AN II", 0.93, children=(("AN I SLOT 2", "AN II SLOT 5", 0.912),)),
    )
    maps = TwinMaps(maps=(document,), urls={"v2": {"AN II SLOT 5": "https://example.invalid/#x"}})
    entry = attributed_entry()
    site = toy_site(entry, sister_of(entry), maps=maps)
    (mine,) = site.twins.twins(HOUSE_RULES, "AN I")
    assert (mine.sister.act, mine.twin.location, mine.twin.ratio) == (SISTER, "AN II", 0.93)
    child = mine.children["AN I SLOT 2"]
    assert (child.location, child.ratio, child.url) == (
        "AN II SLOT 5",
        0.912,
        "https://example.invalid/#x",
    )
    assert mine.page is False
    (theirs,) = site.twins.twins(SISTER, "AN II")
    assert (theirs.sister.act, theirs.twin.location) == (HOUSE_RULES, "AN I")
    assert theirs.children["AN II SLOT 5"].location == "AN I SLOT 2"
    assert theirs.page is True
    assert site.twins.twins(HOUSE_RULES, "AR 2") == ()
