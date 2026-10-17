"""The inverted index the substance pages are built from: registers and entry changes, by number.

Built over the toy act of `toy_substances.py`, whose keys, cells and numbers are invented, and
over registers read back from disk the way the build reads them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from toy_substances import entry_with_table, register, substance_site

from emendrix.core import ActId, Identifier
from emendrix.output import render_register
from emendrix.site_.act_site import ActSite
from emendrix.site_.substance_inputs import (
    collect_substances,
    identifier_order,
    read_registers,
)


def test_every_cas_and_ec_number_of_the_register_and_the_history_has_one_page() -> None:
    substances = substance_site().substances
    slugs = [one.slug for one in substances.substances]
    assert slugs == ["cas-toy-1", "cas-toy-2", "cas-toy-4", "cas-toy-9", "ec-toy-e1", "ec-toy-e2"]
    assert substances.pages == frozenset(slugs)
    assert all(one.scheme in ("cas", "ec") for one in substances.substances)


def test_a_removed_entry_keeps_its_history_and_its_page() -> None:
    gone = next(one for one in substance_site().substances.substances if one.value == "toy-9")
    assert gone.holdings == ()
    assert [moved.change.kind for moved in gone.history] == ["removed"]


def test_an_entry_and_its_change_are_both_found_under_each_number_they_print() -> None:
    found = {one.slug: one for one in substance_site().substances.substances}
    for slug in ("cas-toy-1", "ec-toy-e1"):
        assert [h.entry.key for h in found[slug].holdings] == ["k1"]
        assert [m.change.key for m in found[slug].history] == ["k1"]
    assert [h.entry.key for h in found["ec-toy-e2"].holdings] == ["k2", "k3"]
    assert [h.entry.key for h in found["cas-toy-4"].holdings] == [None]


def test_an_ec_page_repeating_exactly_one_cas_page_defers_to_it_and_no_other_does() -> None:
    found = {one.slug: one for one in substance_site().substances.substances}
    assert found["ec-toy-e1"].canonical == Identifier(scheme="cas", value="toy-1")
    assert found["ec-toy-e2"].canonical is None, "k3 prints the EC number and not the CAS one"
    assert all(found[slug].canonical is None for slug in found if slug.startswith("cas-"))


def test_an_index_no_lands_on_the_first_cas_number_its_entry_carries() -> None:
    substances = substance_site().substances
    (label,) = substances.labels
    assert (label.scheme, label.value) == ("index", "toy-i1")
    assert label.target == Identifier(scheme="cas", value="toy-1")
    assert substances.unlabelled == ()


def test_a_number_two_acts_print_lists_both_acts_entries_in_roster_order() -> None:
    entry = entry_with_table()
    first = ActSite(act=entry.act, label="A toy", entries=(entry,))
    second = ActSite(act=ActId(corpus="toy", key="second"), label="B toy")
    found = collect_substances((first, second), (register(), register("second", "w1")))
    toy = next(one for one in found.substances if one.slug == "cas-toy-1")
    assert [(h.act.label, h.version) for h in toy.holdings] == [("A toy", "v2"), ("B toy", "w1")]
    assert found.has_register(first) and found.has_register(second)
    ec = next(one for one in found.substances if one.slug == "ec-toy-e1")
    assert ec.canonical == Identifier(scheme="cas", value="toy-1"), "both acts, same entries"


def test_an_act_the_build_does_not_show_contributes_nothing() -> None:
    hidden = collect_substances((), (register(),))
    assert hidden.substances == () and hidden.registered == ()


def test_numbers_sort_by_their_digits_as_numbers() -> None:
    values = ["100-00-5", "50-00-0", "7440-02-0", "64-17-5"]
    assert sorted(values, key=lambda v: identifier_order("cas", v)) == [
        "50-00-0",
        "64-17-5",
        "100-00-5",
        "7440-02-0",
    ]


def test_registers_are_read_off_disk_and_a_broken_one_is_refused_by_name(tmp_path: Path) -> None:
    good = tmp_path / "toy" / "house-rules" / "register.json"
    good.parent.mkdir(parents=True)
    good.write_text(render_register(register()), encoding="utf-8")
    assert read_registers(tmp_path) == (register(),)
    broken = tmp_path / "toy" / "other" / "register.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match=r"other/register\.json is not a register"):
        read_registers(tmp_path)


def test_the_inputs_are_the_same_on_every_collection() -> None:
    assert substance_site().substances == substance_site().substances
