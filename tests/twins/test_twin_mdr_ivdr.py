"""The MDR/IVDR twin map over the pinned 20250110 consolidations of both, read through a store.

The counts are measured facts of the two fixtures at the floor of 0.90. They agree with the
all-pairs survey in `scripts/validation/results/twin-floor-2026-10-19.txt`: 85 pairs and 75
equal headings for these two versions, and 1 identical pair and 1,019 aligned children for MDR
20260101 against the same IVDR text. 32 pairs are withheld when only the passages a page shows
count towards the share, measured 2026-10-19. A count that moves is a finding to
explain, not a number to update.
"""

from __future__ import annotations

import pytest

from emendrix import DISCLAIMER
from emendrix.core import ActId, ProvisionTree, VersionId
from emendrix.session import adapter_for
from emendrix.texts.store import TextStore
from emendrix.twins.build import render, twin_map
from emendrix.twins.model import TwinMap
from emendrix.twins.passages import CUT, MAX_PASSAGES, PASSAGE_CHARS, WITHHELD_SHARE
from eu_pins import FIXTURE_DIR, IVDR, IVDR_TWIN, MDR, MDR_TWIN, OBSERVED_ON


def _stored(store: TextStore, key: str, version: str) -> ProvisionTree:
    tree = store.tree("eu", key, version)
    assert isinstance(tree, ProvisionTree), tree
    return tree


@pytest.fixture(scope="module")
def trees(tmp_path_factory: pytest.TempPathFactory) -> tuple[ProvisionTree, ProvisionTree]:
    """Both versions fetched offline, written into a store and read back, as the command does."""
    store = TextStore.create_or_open(tmp_path_factory.mktemp("twins") / "store")
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        for key, version in ((MDR, MDR_TWIN), (IVDR, IVDR_TWIN)):
            fetched = adapter.fetch_version(ActId(corpus="eu", key=key), VersionId(version))
            assert isinstance(fetched, ProvisionTree), fetched
            store.write(fetched, version=version)
    return _stored(store, MDR, MDR_TWIN), _stored(store, IVDR, IVDR_TWIN)


@pytest.fixture(scope="module")
def built(trees: tuple[ProvisionTree, ProvisionTree]) -> TwinMap:
    return twin_map(*trees)


def test_the_map_names_both_sides_the_method_and_the_disclaimer(built: TwinMap) -> None:
    assert (built.a.key, built.a.version, built.b.key, built.b.version) == (
        MDR,
        MDR_TWIN,
        IVDR,
        IVDR_TWIN,
    )
    assert (built.method.measure, built.method.floor, built.method.verified_on) == (
        "word-ratio",
        0.90,
        "2026-10-19",
    )
    assert built.disclaimer == DISCLAIMER


def test_the_counts_are_the_measured_ones(
    built: TwinMap, trees: tuple[ProvisionTree, ProvisionTree]
) -> None:
    mdr, ivdr = trees
    assert (len(mdr.roots), len(ivdr.roots)) == (141, 129)
    assert len(built.pairs) == 85
    assert sum(pair.a.startswith("AR ") for pair in built.pairs) == 80
    assert [pair.a for pair in built.pairs if pair.a.startswith("AN ")] == [
        "AN III",
        "AN IV",
        "AN V",
        "AN VII",
        "AN XII",
    ]
    assert [(pair.a, pair.b) for pair in built.pairs if pair.identical] == [("AR 12", "AR 12")]
    assert sum(pair.passages_withheld for pair in built.pairs) == 32
    assert sum(pair.headings_equal for pair in built.pairs) == 75
    assert sum(len(pair.children) for pair in built.pairs) == 1019
    assert (len(built.unpaired_a), len(built.unpaired_b)) == (56, 44)
    assert all(row.best is None for row in (*built.unpaired_a, *built.unpaired_b))


def test_pairs_are_in_the_first_acts_order_and_never_matched_by_number(
    built: TwinMap, trees: tuple[ProvisionTree, ProvisionTree]
) -> None:
    order = [root.location.canonical for root in trees[0].roots]
    positions = [order.index(pair.a) for pair in built.pairs]
    assert positions == sorted(positions)
    assert any(pair.a != pair.b for pair in built.pairs)
    assert all(pair.ratio >= built.method.floor for pair in built.pairs)


def test_every_passage_obeys_the_caps(
    built: TwinMap, trees: tuple[ProvisionTree, ProvisionTree]
) -> None:
    mdr, ivdr = trees
    for pair in built.pairs:
        if pair.identical or pair.passages_withheld:
            assert (pair.passages, pair.passages_omitted) == ((), 0), pair.a
            continue
        assert 0 < len(pair.passages) <= MAX_PASSAGES, pair.a
        for passage in pair.passages:
            for side in (passage.a, passage.b):
                assert len(side) <= PASSAGE_CHARS + len(CUT)
                assert side.endswith(CUT) == (len(side) > PASSAGE_CHARS)
            assert passage.cut == (passage.a.endswith(CUT) or passage.b.endswith(CUT))
        texts = {
            "a": mdr.find(pair.a),
            "b": ivdr.find(pair.b),
        }
        for name, found in texts.items():
            assert found is not None
            shown = sum(len(getattr(passage, name)) for passage in pair.passages)
            assert shown <= WITHHELD_SHARE * len(found.comparison_text), (pair.a, name)


def test_a_rebuild_is_the_same_bytes_whichever_act_comes_first(
    built: TwinMap, trees: tuple[ProvisionTree, ProvisionTree]
) -> None:
    mdr, ivdr = trees
    text = render(built)
    assert text.endswith("}\n")
    assert render(twin_map(ivdr, mdr)) == text
    assert TwinMap.model_validate_json(text) == built
