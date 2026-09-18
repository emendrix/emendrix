"""The one grouping of acts by sector that every page listing acts by sector reads."""

from __future__ import annotations

from emendrix.core import ActId
from emendrix.site_.inputs import ActSite
from emendrix.site_.sectors import UNGROUPED, groups, sector_key, sector_of


def _act(key: str, domain: str = "") -> ActSite:
    return ActSite(act=ActId(corpus="toy", key=key), label=key, domain=domain)


def test_an_act_with_no_declared_domain_is_listed_under_other() -> None:
    assert sector_of(_act("a")) == UNGROUPED == "Other"
    assert sector_of(_act("a", "Agri-food")) == "Agri-food"


def test_sectors_sort_case_folded_with_other_last_and_acts_keep_their_order() -> None:
    acts = (
        _act("z", "banking"),
        _act("y"),
        _act("x", "Agri-food"),
        _act("w", "banking"),
        _act("v", "Banking"),
    )
    grouped = groups(acts)
    assert [name for name, _ in grouped] == ["Agri-food", "Banking", "banking", "Other"]
    assert [act.label for act in dict(grouped)["banking"]] == ["z", "w"]
    assert sector_key("Other") > sector_key("zzz")
