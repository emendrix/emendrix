"""Which provisions of two trees are textual twins: scored, paired, and aligned below.

The measure is the word ratio, `difflib.SequenceMatcher(None, a_words, b_words,
autojunk=False).ratio()` over `comparison_text.split()`. `real_quick_ratio()` and
`quick_ratio()` are upper bounds of `ratio()`, so a pair either bound puts below the floor is
skipped without changing any pair at or above it.

A pair is a twin when each node is the other's best match and the ratio reaches the floor.
Only nodes of one kind are compared (the code of the location's last segment: an article with
an article, an annex with an annex, a paragraph with a paragraph), and never by number: a
numbering offset between two acts is what the score finds, not an input. Ties go to the lower
canonical location string. Ratios are compared unrounded; rounding is for the published map.
"""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from emendrix.core import ProvisionNode

__all__ = [
    "TWIN_FLOOR",
    "TWIN_FLOOR_VERIFIED_ON",
    "Aligned",
    "Pairing",
    "align_children",
    "kind_of",
    "pair_nodes",
    "word_ratio",
]

# The lowest floor >= 0.50 at which at least 95% of mutual-best MDR/IVDR unit pairs share a
# normalised heading, else 0.90. None reached 0.95 on 2026-10-19 (0.882 at 0.90), so 0.90.
TWIN_FLOOR: Final = 0.90
TWIN_FLOOR_VERIFIED_ON: Final = "2026-10-19"


def kind_of(node: ProvisionNode) -> str:
    """The code of the node's last location segment: `AR`, `AN`, `PA`, ..."""
    return str(node.location.segments[-1].code)


def _bounded(matcher: difflib.SequenceMatcher[str], floor: float) -> float | None:
    if matcher.real_quick_ratio() < floor or matcher.quick_ratio() < floor:
        return None
    return matcher.ratio()


def word_ratio(a: Sequence[str], b: Sequence[str], *, floor: float) -> float | None:
    """The word ratio of two word lists, or None when an upper bound is below `floor`."""
    return _bounded(difflib.SequenceMatcher(None, list(a), list(b), autojunk=False), floor)


@dataclass(frozen=True)
class Aligned:
    """Two nodes, each the other's best match, and their unrounded ratio."""

    a: ProvisionNode
    b: ProvisionNode
    ratio: float


@dataclass(frozen=True)
class Pairing:
    """One level's answer: the twins, and each side's nodes that found none.

    An unpaired node carries its best match at or above the floor, if it has one; that match
    then preferred another node. A node with nothing at the floor carries None.
    """

    pairs: tuple[Aligned, ...]
    unpaired_a: tuple[tuple[ProvisionNode, ProvisionNode | None, float | None], ...]
    unpaired_b: tuple[tuple[ProvisionNode, ProvisionNode | None, float | None], ...]


def _keep(
    best: dict[int, tuple[int, float]], at: int, other: int, ratio: float, names: Sequence[str]
) -> None:
    """Hold `other` as `at`'s best when its ratio is higher, or equal at a lower location."""
    held = best.get(at)
    if held is None or (-ratio, names[other]) < (-held[1], names[held[0]]):
        best[at] = (other, ratio)


def pair_nodes(
    left: Sequence[ProvisionNode], right: Sequence[ProvisionNode], *, floor: float
) -> Pairing:
    """Mutual-best pairs of same-kind nodes at or above `floor`, in `left`'s order."""
    words_a = [str(node.comparison_text).split() for node in left]
    kinds_a = [kind_of(node) for node in left]
    names_a = [node.location.canonical for node in left]
    names_b = [node.location.canonical for node in right]
    best_a: dict[int, tuple[int, float]] = {}
    best_b: dict[int, tuple[int, float]] = {}
    matcher: difflib.SequenceMatcher[str] = difflib.SequenceMatcher(None, autojunk=False)
    for j, b in enumerate(right):
        # `set_seq2` indexes its argument, so each right node is indexed once.
        matcher.set_seq2(str(b.comparison_text).split())
        kind = kind_of(b)
        for i in range(len(left)):
            if kinds_a[i] != kind:
                continue
            matcher.set_seq1(words_a[i])
            ratio = _bounded(matcher, floor)
            if ratio is None or ratio < floor:
                continue
            _keep(best_a, i, j, ratio, names_b)
            _keep(best_b, j, i, ratio, names_a)
    mutual = {i: j for i, (j, _) in best_a.items() if best_b.get(j, (-1, 0.0))[0] == i}
    pairs = tuple(
        Aligned(a=left[i], b=right[mutual[i]], ratio=best_a[i][1]) for i in sorted(mutual)
    )
    paired_b = set(mutual.values())
    unpaired_a = tuple(
        (node, *_best(best_a.get(i), right)) for i, node in enumerate(left) if i not in mutual
    )
    unpaired_b = tuple(
        (node, *_best(best_b.get(j), left)) for j, node in enumerate(right) if j not in paired_b
    )
    return Pairing(pairs=pairs, unpaired_a=unpaired_a, unpaired_b=unpaired_b)


def _best(
    held: tuple[int, float] | None, other: Sequence[ProvisionNode]
) -> tuple[ProvisionNode | None, float | None]:
    return (None, None) if held is None else (other[held[0]], held[1])


def align_children(a: ProvisionNode, b: ProvisionNode, *, floor: float) -> tuple[Aligned, ...]:
    """Descendants of a pair, aligned level by level below aligned parents, in pre-order."""
    if not a.children or not b.children:
        return ()
    aligned: list[Aligned] = []
    for pair in pair_nodes(a.children, b.children, floor=floor).pairs:
        aligned.append(pair)
        aligned.extend(align_children(pair.a, pair.b, floor=floor))
    return tuple(aligned)
