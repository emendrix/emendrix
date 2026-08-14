"""The unit pass: which top-level provisions were inserted, deleted, modified or renumbered.

This is the algorithm that scored F1 = 1.000 against the corpus's own modification metadata on
2026-08-05, still asserted every run by `tests/corroborate/test_eu_corroboration.py`. It compares
the **comparison form** of each unit, never the verbatim text, which is kept unnormalised for
quoting; and it knows nothing about any particular corpus, so the same code runs on the toy
corpus in `tests/toy_corpus.py`.

**Ordering** (the changelog rendering depends on it, so it is a contract):

- The order is the document order of the *new* version. A unit that exists in the new version
  is emitted at its position there.
- A deleted unit has no anchor in the new version, so it is emitted immediately before the slot
  of the next old-version unit that survived, which is to say straight after its nearest
  surviving predecessor. Deletions before any survivor come first; deletions sharing an anchor
  keep the old version's document order.

**Renumbering** is detected between the leftover insertions and deletions only, and it is
capped. No renumbering occurs in any of the seven transitions traced against the live endpoints
on 2026-08-05, and no corpus role code plausibly means it, so every bound below is sized for an
unobserved case. Reporting it is in scope; rewriting the cross-references it breaks is not.
"""

from __future__ import annotations

import difflib
from typing import Final

from pydantic import BaseModel, ConfigDict

from emendrix.core import ChangeType, ProvisionNode, ProvisionTree

__all__ = [
    "RENUMBER_CANDIDATE_CAP",
    "RENUMBER_MIN_LENGTH",
    "RENUMBER_PREFIX_LIMIT",
    "RENUMBER_SIMILARITY",
    "UnitDiff",
    "UnitMatch",
    "diff_units",
]

RENUMBER_SIMILARITY: Final = 0.95
"""How alike two comparison forms must be to call a delete/insert pair one renumbering.

A provision that both moved *and* was substantively rewritten is past the v0.1 cap: it stays
`DELETED` + `INSERTED` and three-way corroboration gets to flag it.
"""

RENUMBER_MIN_LENGTH: Final = 100
"""Below this many characters, similarity is not evidence and exact equality is required.

Short provisions are mostly boilerplate: "This Regulation shall enter into force on the
twentieth day following that of its publication" is 0.97-similar to a dozen of its neighbours.
"""

RENUMBER_PREFIX_LIMIT: Final = 2000
"""Similarity is measured on at most this much of each text. An amending act's Article 1 can
be 180 kB (`32026R1744`); quadratic matching over that, for
every candidate pair, is not a cost this step is willing to pay for an unobserved case."""

RENUMBER_CANDIDATE_CAP: Final = 50
"""Above this many leftover insertions or deletions, the similarity pass is skipped entirely.

The exact-equality pass still runs, being a dictionary lookup. This bounds the fuzzy pass at
`50 x 50` comparisons of `RENUMBER_PREFIX_LIMIT` characters, which is milliseconds.
"""


class UnitMatch(BaseModel):
    """One top-level unit, paired across the two versions and classified structurally."""

    model_config = ConfigDict(frozen=True)

    change_type: ChangeType
    before: ProvisionNode | None = None
    after: ProvisionNode | None = None


class UnitDiff(BaseModel):
    """Every unit that changed, in the emission order documented above, and how many did not."""

    model_config = ConfigDict(frozen=True)

    matches: tuple[UnitMatch, ...] = ()
    unchanged_units: int = 0


def diff_units(before: ProvisionTree, after: ProvisionTree) -> UnitDiff:
    """Match the two versions' top-level units and classify each pairing."""
    old = {node.location.canonical: node for node in before.roots}
    new = {node.location.canonical: node for node in after.roots}
    modified, unchanged = _common(old, new)
    renumbered = _renumberings(
        [node for key, node in old.items() if key not in new],
        [node for key, node in new.items() if key not in old],
    )
    return UnitDiff(
        matches=_in_order(before, after, modified, renumbered), unchanged_units=unchanged
    )


def _common(
    old: dict[str, ProvisionNode], new: dict[str, ProvisionNode]
) -> tuple[dict[str, ProvisionNode], int]:
    """Units present under the same location in both versions, split by whether they differ."""
    modified: dict[str, ProvisionNode] = {}
    unchanged = 0
    for key, node in new.items():
        counterpart = old.get(key)
        if counterpart is None:
            continue
        if counterpart.comparison_text == node.comparison_text:
            unchanged += 1
        else:
            modified[key] = counterpart
    return modified, unchanged


def _in_order(
    before: ProvisionTree,
    after: ProvisionTree,
    modified: dict[str, ProvisionNode],
    renumbered: list[tuple[ProvisionNode, ProvisionNode]],
) -> tuple[UnitMatch, ...]:
    """Assemble the emission order: new-version document order, deletions at their old anchor."""
    slots = {node.location.canonical: index for index, node in enumerate(after.roots)}
    landed = {old.location.canonical: new.location.canonical for old, new in renumbered}
    came_from = {new.location.canonical: old for old, new in renumbered}
    old_keys = {node.location.canonical for node in before.roots}

    deletions = _anchored_deletions(before, slots, landed)
    matches: list[UnitMatch] = []
    for index, node in enumerate(after.roots):
        matches.extend(deletions.get(index, ()))
        key = node.location.canonical
        if key in came_from:
            matches.append(
                UnitMatch(change_type=ChangeType.RENUMBERED, before=came_from[key], after=node)
            )
        elif key in modified:
            matches.append(
                UnitMatch(change_type=ChangeType.MODIFIED, before=modified[key], after=node)
            )
        elif key not in old_keys:
            matches.append(UnitMatch(change_type=ChangeType.INSERTED, after=node))
    matches.extend(deletions.get(len(after.roots), ()))
    return tuple(matches)


def _anchored_deletions(
    before: ProvisionTree, slots: dict[str, int], landed: dict[str, str]
) -> dict[int, list[UnitMatch]]:
    """Deleted units, grouped by the new-version slot they are emitted in front of.

    A unit survives when the new version still has its location, or when renumbering found it
    under another one. Everything else is gone, and is anchored to the slot just past its
    nearest surviving predecessor, or slot 0 when it had none.
    """
    grouped: dict[int, list[UnitMatch]] = {}
    anchor = 0
    for node in before.roots:
        key = node.location.canonical
        landing = slots.get(landed.get(key, key))
        if landing is not None:
            anchor = landing + 1
        else:
            grouped.setdefault(anchor, []).append(
                UnitMatch(change_type=ChangeType.DELETED, before=node)
            )
    return grouped


def _renumberings(
    removed: list[ProvisionNode], inserted: list[ProvisionNode]
) -> list[tuple[ProvisionNode, ProvisionNode]]:
    """Pair leftover deletions with leftover insertions that carry (near-)identical text."""
    if not removed or not inserted:
        return []
    pairs: list[tuple[ProvisionNode, ProvisionNode]] = []
    taken_old: set[str] = set()
    taken_new: set[str] = set()
    by_text: dict[str, list[ProvisionNode]] = {}
    for node in removed:
        by_text.setdefault(str(node.comparison_text), []).append(node)
    for node in inserted:
        for candidate in by_text.get(str(node.comparison_text), ()):
            if candidate.location.canonical not in taken_old:
                taken_old.add(candidate.location.canonical)
                taken_new.add(node.location.canonical)
                pairs.append((candidate, node))
                break
    pairs.extend(_similar(removed, inserted, taken_old, taken_new))
    return pairs


def _similar(
    removed: list[ProvisionNode],
    inserted: list[ProvisionNode],
    taken_old: set[str],
    taken_new: set[str],
) -> list[tuple[ProvisionNode, ProvisionNode]]:
    """The bounded fuzzy pass over what exact equality did not pair.

    Only texts of meaningful length take part; below `RENUMBER_MIN_LENGTH` the exact pass is
    the whole of renumber detection. Pairs are taken greedily by descending similarity, ties
    broken by canonical location, so the result never depends on dictionary order.
    """
    old = [node for node in removed if _eligible(node, taken_old)]
    new = [node for node in inserted if _eligible(node, taken_new)]
    if not old or not new or max(len(old), len(new)) > RENUMBER_CANDIDATE_CAP:
        return []
    scored: list[tuple[float, str, str]] = []
    nodes = {node.location.canonical: node for node in old + new}
    for left in old:
        head = str(left.comparison_text)[:RENUMBER_PREFIX_LIMIT]
        for right in new:
            tail = str(right.comparison_text)[:RENUMBER_PREFIX_LIMIT]
            matcher = difflib.SequenceMatcher(None, head, tail, autojunk=False)
            if matcher.real_quick_ratio() < RENUMBER_SIMILARITY:
                continue
            if matcher.quick_ratio() < RENUMBER_SIMILARITY:
                continue
            ratio = matcher.ratio()
            if ratio >= RENUMBER_SIMILARITY:
                scored.append((-ratio, left.location.canonical, right.location.canonical))
    pairs: list[tuple[ProvisionNode, ProvisionNode]] = []
    for _, old_key, new_key in sorted(scored):
        if old_key in taken_old or new_key in taken_new:
            continue
        taken_old.add(old_key)
        taken_new.add(new_key)
        pairs.append((nodes[old_key], nodes[new_key]))
    return pairs


def _eligible(node: ProvisionNode, taken: set[str]) -> bool:
    return (
        node.location.canonical not in taken
        and len(str(node.comparison_text)) >= RENUMBER_MIN_LENGTH
    )
