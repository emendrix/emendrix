"""Two trees to one twin map, and the map to the bytes that are committed.

The map is a function of the two trees and the constants in `pair.py` and `passages.py`, and of
nothing else: no clock, no model, no corpus. Whichever order the trees arrive in, the act with
the lower key is side A, so one pair of acts has one map.
"""

from __future__ import annotations

from emendrix import DISCLAIMER
from emendrix.core import ProvisionNode, ProvisionTree
from emendrix.twins.model import (
    TWINS_SCHEMA,
    AlignedChild,
    TwinMap,
    TwinMethod,
    TwinPair,
    TwinSide,
    Unpaired,
    ordered,
)
from emendrix.twins.numbering import numbering_only
from emendrix.twins.pair import (
    TWIN_FLOOR,
    TWIN_FLOOR_VERIFIED_ON,
    Aligned,
    align_children,
    pair_nodes,
)
from emendrix.twins.passages import excerpt

__all__ = ["headings_equal", "render", "twin_map"]


def _heading(heading: str | None) -> str:
    return " ".join((heading or "").casefold().split()).rstrip(".:;").strip()


def headings_equal(a: ProvisionNode, b: ProvisionNode) -> bool:
    """Equal once case-folded, whitespace collapsed and trailing `.:;` dropped; none equals none."""
    left = _heading(a.heading)
    return bool(left) and left == _heading(b.heading)


def _rounded(ratio: float) -> float:
    return round(ratio, 3)


def _pair(pair: Aligned, *, floor: float) -> TwinPair:
    a_text, b_text = str(pair.a.comparison_text), str(pair.b.comparison_text)
    shown = excerpt(a_text, b_text)
    return TwinPair(
        a=pair.a.location.canonical,
        b=pair.b.location.canonical,
        ratio=_rounded(pair.ratio),
        identical=a_text == b_text,
        numbering_only=numbering_only(a_text, b_text),
        children=tuple(
            AlignedChild(
                a=child.a.location.canonical,
                b=child.b.location.canonical,
                ratio=_rounded(child.ratio),
            )
            for child in align_children(pair.a, pair.b, floor=floor)
        ),
        passages=shown.passages,
        passages_omitted=shown.omitted,
        passages_withheld=shown.withheld,
        headings_equal=headings_equal(pair.a, pair.b),
    )


def _unpaired(
    rows: tuple[tuple[ProvisionNode, ProvisionNode | None, float | None], ...],
) -> tuple[Unpaired, ...]:
    ordered_rows = sorted(rows, key=lambda row: row[0].location.sort_key)
    return tuple(
        Unpaired(
            unit=node.location.canonical,
            best=None if best is None else best.location.canonical,
            ratio=None if ratio is None else _rounded(ratio),
        )
        for node, best, ratio in ordered_rows
    )


def _side(tree: ProvisionTree) -> TwinSide:
    return TwinSide(corpus=tree.act.corpus, key=tree.act.key, version=str(tree.version))


def twin_map(first: ProvisionTree, second: ProvisionTree) -> TwinMap:
    """Pair the two trees' units at `TWIN_FLOOR`, align their children, excerpt the rest."""
    floor = TWIN_FLOOR
    low, _ = ordered(first.act, second.act)
    tree_a, tree_b = (first, second) if low is first.act else (second, first)
    pairing = pair_nodes(tree_a.roots, tree_b.roots, floor=floor)
    return TwinMap(
        twins_schema=TWINS_SCHEMA,
        disclaimer=DISCLAIMER,
        method=TwinMethod(measure="word-ratio", floor=floor, verified_on=TWIN_FLOOR_VERIFIED_ON),
        a=_side(tree_a),
        b=_side(tree_b),
        pairs=tuple(_pair(pair, floor=floor) for pair in pairing.pairs),
        unpaired_a=_unpaired(pairing.unpaired_a),
        unpaired_b=_unpaired(pairing.unpaired_b),
    )


def render(document: TwinMap) -> str:
    """The committed text: indented JSON in declaration order, one trailing newline."""
    return document.model_dump_json(indent=2) + "\n"
