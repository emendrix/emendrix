"""Where inside a changed unit the text actually moved: detail below the unit of change.

The unit of change is the top-level provision. This module answers the follow-up question,
*which paragraph, point or subparagraph*, and answers it the same deterministic way the unit
pass does: by matching coordinates and comparing the comparison form.

A node is reported when **its own** text changed, not merely when something under it did. Own
text is the node's comparison form with each child's comparison form removed: every child's
comparison text is a contiguous substring of its parent's, verified on 2026-08-06 over 6 097
parent/child pairs across three acts and two markup generations, with zero misses. Where that
does not hold the residual simply stays whole, which reports the parent as changed: a false
*coordinate*, never a false unit, never a crash.

Children are matched by their last location segment rather than by canonical string, so the
same walk works for a renumbered unit whose whole subtree carries a different first segment.
"""

from __future__ import annotations

from emendrix.core import ProvisionLocation, ProvisionNode

__all__ = ["changed_sublocations", "residual_text"]


def residual_text(node: ProvisionNode) -> str:
    """The node's comparison text with each located child's comparison text removed.

    Removal is first-occurrence and in document order, so repeated identical children (an
    annex point that reads `—` twice) each remove their own occurrence.
    """
    text = str(node.comparison_text)
    for child in node.children:
        fragment = str(child.comparison_text)
        if not fragment:
            continue
        position = text.find(fragment)
        if position >= 0:
            text = text[:position] + text[position + len(fragment) :]
    return " ".join(text.split())


def changed_sublocations(
    before: ProvisionNode, after: ProvisionNode
) -> tuple[ProvisionLocation, ...]:
    """The coordinates inside a changed unit whose own text differs, in document order.

    Document order means: a node before its children, children in the order the *new* version
    prints them, and children that exist only in the old version last among their siblings.
    The result is empty exactly when the two subtrees compare equal, which is how a
    `RENUMBERED` change records that the provision merely moved.

    Coordinates are the new version's, except for a sub-provision that exists only in the old
    one: that keeps the coordinate it actually had, so it resolves in the version it belongs to
    rather than naming a location nothing ever published.
    """
    if before.comparison_text == after.comparison_text:
        return ()
    found: list[ProvisionLocation] = []
    _descend(before, after, found)
    # The texts differ, so something did: if the residuals all matched anyway, the difference
    # is one the substring bookkeeping could not place and the unit itself is the answer.
    return tuple(found) if found else (after.location,)


def _descend(before: ProvisionNode, after: ProvisionNode, found: list[ProvisionLocation]) -> None:
    old = {_key(child): child for child in before.children}
    new = {_key(child): child for child in after.children}
    if residual_text(before) != residual_text(after):
        found.append(after.location)
    for key, child in new.items():
        counterpart = old.get(key)
        if counterpart is None:
            found.append(child.location)
        elif counterpart.comparison_text != child.comparison_text:
            _descend(counterpart, child, found)
    for key, child in old.items():
        if key not in new:
            found.append(child.location)


def _key(node: ProvisionNode) -> str:
    """A child's identity among its siblings: its own last segment, parent path aside."""
    return str(node.location.segments[-1])
