"""The walk: a Formex 4 package → a `core.ProvisionTree`, plus what it could not place.

Pure and offline. It is handed the bytes the fetch layer retrieved and reads nothing else: no clock,
no network, no model — so two runs over the same package produce byte-identical trees. Which
members of the package it walks, and where the units are inside them, is `documents.py`.

**Verbatim means verbatim.** `ProvisionNode.text` is the characters of the element, normalised
nowhere and collapsed nowhere; the only thing added to them is a line break where the markup
opened a block and the source left no text at all, because Formex is a tree and there is no
character stream to transcribe (`text.py` measures which boundaries those are). The
comparison form, separated at every boundary and whitespace-collapsed, is built beside it at
extraction time and is the only thing the diff may compare.

**Annexes are structural best-effort.** A top-level annex is a unit with verbatim text, and
inside it numbered `GR.SEQ` sections, nested appendices and enumerated points do become
nodes (`AN I SCT A PO 1`). What does *not*: table interiors — a `TBL` contributes its prose
to every ancestor's text but no coordinates of its own, so a change inside a REACH annex
table lands on the enclosing section. That is a v0.1 gap, and it is counted, not hidden.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from emendrix.core import (
    ActId,
    LocationCode,
    LocationSegment,
    ProvisionLocation,
    ProvisionNode,
    ProvisionTree,
    VersionId,
)
from emendrix.eu.formex.documents import (
    ANNEX_TAGS,
    FormexDocuments,
    act_documents,
    documents_of,
    unit_elements,
)
from emendrix.eu.formex.locations import (
    INLINE,
    LOCATABLE,
    TRANSPARENT,
    annex_segment,
    article_value,
    decode_identifier,
    point_segment,
    section_value,
    title_of,
)
from emendrix.eu.formex.model import CoverageCounter, ParsedAct
from emendrix.eu.formex.text import (
    SKIPPED_SUBTREES,
    comparison_text,
    date_mentions,
    verbatim_text,
)
from emendrix.eu.packages import FormexPackage

__all__ = ["build_tree", "parse_act"]


def parse_act(package: FormexPackage) -> ParsedAct:
    """One version of one act as a provision tree, with the parser's coverage beside it."""
    counter = CoverageCounter()
    documents = act_documents(package, counter)
    tree = build_tree(documents, package, counter)
    return ParsedAct(tree=tree, coverage=counter.freeze())


def build_tree(
    documents: FormexDocuments, package: FormexPackage, counter: CoverageCounter
) -> ProvisionTree:
    """Turn already-selected documents into a tree of top-level units, in document order.

    The tree is labelled with `served_version`, not with what was asked for: when the
    requested consolidation has no English text the fetch falls back to the act as published
    (`eu/cellar.py`), and a tree that claimed the version it was asked for would lie.
    """
    roots: list[ProvisionNode] = []
    for document in documents_of(documents):
        for unit, is_annex in unit_elements(document):
            node = _unit(unit, is_annex, counter)
            if node is not None:
                roots.append(node)
    counter.units += len(roots)
    act: ActId = package.act
    version: VersionId = package.served_version
    return ProvisionTree(act=act, version=version, language=package.language, roots=tuple(roots))


def _unit(element: Element, is_annex: bool, counter: CoverageCounter) -> ProvisionNode | None:
    """One top-level provision (the unit of change), or `None` if it carries no number."""
    if is_annex:
        segment = annex_segment(element)
        if segment is None:
            counter.containers_flattened += 1
            return None
        code, value = segment
    else:
        number = article_value(element)
        if number is None:
            counter.unmapped_identifiers += 1
            return None
        _cross_check_article(element, number, counter)
        code, value = LocationCode.AR, number
    location = ProvisionLocation(segments=(LocationSegment(code=code, value=value),))
    return _node(element, location, is_annex, counter)


def _cross_check_article(element: Element, number: str, counter: CoverageCounter) -> None:
    """`TI.ART` and `@IDENTIFIER` are redundant signals; disagreement is a counted defect."""
    printed = title_of(element, "TI.ART").split()
    if printed and printed[-1].lower() != number:
        counter.heading_mismatches += 1


def _node(
    element: Element, location: ProvisionLocation, is_annex: bool, counter: CoverageCounter
) -> ProvisionNode:
    counter.nodes += 1
    dates, unreadable = date_mentions(element)
    counter.unreadable_dates += unreadable
    return ProvisionNode(
        location=location,
        heading=_heading(element),
        text=verbatim_text(element),
        comparison_text=comparison_text(element),
        dates=dates,
        children=_children(element, location, is_annex, counter, _Siblings(), None),
    )


@dataclass
class _Siblings:
    """The state shared by everything that lands under one located node.

    `ordinals` numbers the segments that carry no number of their own (`ALN 1`, `TIRE 2`).
    `taken` is the collision guard: a location is an identity, so the second element claiming
    one is descended through instead of placed. The 2006-generation REACH annexes need it —
    an untitled `GR.SEQ` grouping restarts its enumerators, and without the guard `AN VI
    SCT 6 PTA (a)` would name five different points.
    """

    ordinals: Counter[str] = field(default_factory=Counter)
    taken: set[str] = field(default_factory=set)


def _heading(element: Element) -> str | None:
    if element.tag == "ARTICLE":
        return title_of(element, "STI.ART", "TI.ART") or None
    if element.tag in ANNEX_TAGS:
        return title_of(element, "TITLE/STI", "TITLE/TI") or None
    if element.tag == "GR.SEQ":
        return title_of(element, "TITLE/TI") or None
    return None


def _children(
    element: Element,
    location: ProvisionLocation,
    is_annex: bool,
    counter: CoverageCounter,
    siblings: _Siblings,
    list_type: str | None,
) -> tuple[ProvisionNode, ...]:
    """The located provisions directly under `element`.

    `siblings` is shared across transparent containers, so alineas count per paragraph rather
    than per intervening element. Unknown tags are descended through and counted: their text
    is already inside every ancestor's verbatim form, so nothing is lost by not placing them.
    """
    nodes: list[ProvisionNode] = []
    for child in element:
        tag = child.tag
        if tag in SKIPPED_SUBTREES or tag in INLINE:
            continue
        placed = _placed(child, location, is_annex, counter, siblings, list_type)
        if placed is None:
            if tag not in TRANSPARENT and tag not in LOCATABLE:
                counter.unknown[tag] += 1
            nested = child.get("TYPE") if tag == "LIST" else list_type
            nodes.extend(_children(child, location, is_annex, counter, siblings, nested))
            continue
        nodes.append(_node(child, placed, is_annex, counter))
    return tuple(nodes)


def _placed(
    element: Element,
    location: ProvisionLocation,
    is_annex: bool,
    counter: CoverageCounter,
    siblings: _Siblings,
    list_type: str | None,
) -> ProvisionLocation | None:
    """Where `element` goes under `location`, or `None` to descend through it instead."""
    segment = _segment(element, is_annex, list_type, counter)
    if segment is None:
        return None
    code, value = segment
    if value is None:
        siblings.ordinals[str(code)] += 1
        value = str(siblings.ordinals[str(code)])
    child = location.child(code, value)
    if child.canonical in siblings.taken:
        counter.containers_flattened += 1
        return None
    siblings.taken.add(child.canonical)
    return child


def _segment(
    element: Element, is_annex: bool, list_type: str | None, counter: CoverageCounter
) -> tuple[LocationCode, str | None] | None:
    """The location segment `element` contributes, or `None` to descend through it."""
    tag = element.tag
    if tag == "PARAG":
        value = decode_identifier(element.get("IDENTIFIER")) or _paragraph_number(element)
        if value is None:
            counter.containers_flattened += 1
            return None
        return (LocationCode.PA, value)
    if tag == "ALINEA":
        return (LocationCode.ALN, None)
    if tag == "NP":
        point = point_segment(element, list_type)
        if point is None:
            counter.containers_flattened += 1
        return point
    if not is_annex:
        return None
    if tag == "GR.SEQ":
        section = section_value(element)
        if section is None:
            counter.containers_flattened += 1
            return None
        return (LocationCode.SCT, section)
    if tag in ANNEX_TAGS:
        nested = annex_segment(element)
        if nested is None:
            counter.containers_flattened += 1
        return nested
    return None


def _paragraph_number(element: Element) -> str | None:
    """`NO.PARAG` — `'1a.'` → `'1a'`. The fallback when `@IDENTIFIER` is absent or unreadable."""
    return title_of(element, "NO.PARAG").strip().rstrip(".").lower() or None
