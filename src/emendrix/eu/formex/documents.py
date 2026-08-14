"""Finding things: which members of a package are documents, and which elements are units.

Split out of the walk along a real seam — everything here answers *where do I start*, and
nothing here reads a provision.

**A package is a bag of documents, not a file**. A
consolidated act carries its annexes inline as `CONS.ANNEX`; the same act as published in the
OJ ships one `ANNEX` document per annex, and Regulation `1272/2008` ships 98 members whose
largest XML is an annex — so "the biggest file" is the wrong rule. The act is found by shape:
its root is `ACT`/`CONS.ACT`/`CONS.DOC` and it carries `ENACTING.TERMS`. Members are read in
name order so the unit sequence is stable across runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Final
from xml.etree.ElementTree import Element

from emendrix.eu.formex.locations import INLINE
from emendrix.eu.formex.model import CoverageCounter
from emendrix.eu.formex.text import SKIPPED_SUBTREES
from emendrix.eu.packages import FormexPackage
from emendrix.eu.xml_ import NOT_WELL_FORMED, fromstring

__all__ = [
    "ACT_ROOTS",
    "ANNEX_TAGS",
    "FormexDocuments",
    "act_documents",
    "documents_of",
    "unit_elements",
]

ACT_ROOTS: Final = frozenset({"ACT", "CONS.ACT", "CONS.DOC"})
"""Root tags an act's own document may carry. `ENACTING.TERMS` is the deciding evidence."""

ANNEX_TAGS: Final = frozenset({"CONS.ANNEX", "ANNEX"})
_UNIT_TAGS: Final = frozenset({"ARTICLE", *ANNEX_TAGS})
_IGNORED_ROOTS: Final = frozenset({"DOC", "PUBLICATION"})
"""The package's own wrappers: the `.doc` manifest and the `.toc` publication index."""

FormexDocuments = tuple[Element | None, tuple[Element, ...]]
"""The act's own document (if the package holds one) and its standalone annex documents."""


def act_documents(package: FormexPackage, counter: CoverageCounter) -> FormexDocuments:
    """Select the act document and the annex documents, in member-name order.

    A member that is not well-formed XML is counted and skipped: a corpus that serves a
    corrupt archive member is a coverage gap to report, not an exception to raise. A member
    the hardened parser declines to expand (`eu/xml_.py`) is counted the same way and for the
    same reason — it is equally a document this code could not read.
    """
    act: Element | None = None
    fallback: Element | None = None
    annexes: list[Element] = []
    for member in sorted(package.xml_members, key=lambda item: item.name):
        try:
            root = fromstring(member.data)
        except NOT_WELL_FORMED:
            counter.documents_unreadable += 1
            continue
        if root.tag in _IGNORED_ROOTS:
            continue
        counter.documents += 1
        if root.tag == "ANNEX":
            annexes.append(root)
        elif act is None and root.tag in ACT_ROOTS and root.find(".//ENACTING.TERMS") is not None:
            act = root
        elif fallback is None:
            fallback = root
    return (act if act is not None else fallback), tuple(annexes)


def documents_of(documents: FormexDocuments) -> tuple[Element, ...]:
    """The selected documents as one sequence, act first."""
    act, annexes = documents
    return annexes if act is None else (act, *annexes)


def unit_elements(element: Element) -> Iterator[tuple[Element, bool]]:
    """Every top-level unit in a document, as `(element, is_annex)`, in document order.

    Descent stops at a unit and at anything `INLINE` — which is what keeps an `ARTICLE`
    quoted inside an amending instruction out of that act's own provision tree.
    """
    if element.tag in _UNIT_TAGS:
        yield element, element.tag in ANNEX_TAGS
        return
    for child in element:
        if child.tag in SKIPPED_SUBTREES:
            continue
        if child.tag in _UNIT_TAGS:
            yield child, child.tag in ANNEX_TAGS
        elif child.tag not in INLINE:
            yield from unit_elements(child)
