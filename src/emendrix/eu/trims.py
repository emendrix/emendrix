"""Reproducible trims: how a pinned response is cut down before it is committed.

A fixture is a real response, and where a real response is too big to commit it is cut by a
rule that lives here rather than by hand in an editor. Two rules, both mechanical:

- **`notice-*`** keeps the elements `eu/notices.py` actually reads and drops the rest,
  including whitespace-only text nodes (a notice is served pretty-printed, and it is data).
  A big act's notices are 1.5 to 3.7 MB, of which the read part is a few per cent.
- **`formex-xml-only`** rebuilds a Formex package with its XML members, dropping the `.tif`
  page scans of the printed Journal — 89 of the 98 members of `32008R1272`, 8.9 MB in one
  REACH consolidation. Nothing parses them. Names are sorted and timestamps fixed so the
  rebuilt archive is byte-identical on every run.

What is deliberately *not* trimmed: provision text. The Formex documents are committed whole,
because the numbers the parser and the eval assert are computed over all of them.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET  # types and serialisation; parsing goes through `eu/xml_.py`
import zipfile
from collections.abc import Mapping
from copy import deepcopy
from typing import Final, cast

from emendrix.eu.notices import CONSOLIDATION_RELATIONS
from emendrix.eu.packages import check_package_size
from emendrix.eu.xml_ import fromstring

__all__ = ["BRANCH_SPEC", "TREE_SPEC", "Spec", "trim_formex_zip", "trim_notice"]

type Spec = Mapping[str, Spec | None]
"""Which children to keep, recursively. `None` in place of a spec keeps a subtree whole."""

_KEEP_WHOLE: Final[Spec | None] = None

# A manifestation link is kept down to `IDENTIFIER` + `TYPE`, which is all `eu/notices.py`
# reads of it; the sibling `VALUE` repeats the same thing as a full URL and, at 68 versions
# times 24 languages times 3 formats, is most of what a big act's tree notice weighs.
_MANIFESTATION_LINK: Final[Spec] = {"SAMEAS": {"URI": {"IDENTIFIER": None, "TYPE": None}}}
_EXPRESSION: Final[Spec] = {
    "EXPRESSION_USES_LANGUAGE": _KEEP_WHOLE,
    "EXPRESSION_TITLE": _KEEP_WHOLE,
    "EXPRESSION_MANIFESTED_BY_MANIFESTATION": _MANIFESTATION_LINK,
    "SAMEAS": _KEEP_WHOLE,
}
_CONSOLIDATION_LINK: Final[Spec] = {
    "SAMEAS": _KEEP_WHOLE,
    "URI": _KEEP_WHOLE,
    "EMBEDDED_NOTICE": {
        "WORK": {"ID_CELEX": _KEEP_WHOLE, "WORK_DATE_DOCUMENT": _KEEP_WHOLE},
        "EXPRESSION": _EXPRESSION,
    },
}
TREE_SPEC: Final[Spec] = {
    "WORK": {
        "URI": _KEEP_WHOLE,
        "SAMEAS": _KEEP_WHOLE,
        "ID_CELEX": _KEEP_WHOLE,
        "WORK_DATE_DOCUMENT": _KEEP_WHOLE,
        "RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE": _KEEP_WHOLE,
        # Both consolidation relations, including the links that belong to *other* acts —
        # with their embedded notice pruned to identity, so the parser's act filter and its
        # two-relation union stay exercised by the fixture.
        **dict.fromkeys(CONSOLIDATION_RELATIONS, _CONSOLIDATION_LINK),
    },
    "EXPRESSION": _EXPRESSION,
}
BRANCH_SPEC: Final[Spec] = {
    "WORK": {
        "URI": _KEEP_WHOLE,
        "SAMEAS": _KEEP_WHOLE,
        "ID_CELEX": _KEEP_WHOLE,
        "WORK_DATE_DOCUMENT": _KEEP_WHOLE,
        # The modification annotations corroboration reads, and nothing else: an act's branch
        # notice is 1.5-3.7 MB, of which this is a few per cent.
        "RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL": {
            "SAMEAS": _KEEP_WHOLE,
            "URI": _KEEP_WHOLE,
            "ANNOTATION": _KEEP_WHOLE,
        },
    },
}


def _prune(element: ET.Element, spec: Spec | None) -> ET.Element:
    """Copy `element`, keeping only the children `spec` names. `None` keeps a subtree whole."""
    if spec is None:
        return deepcopy(element)
    kept = ET.Element(element.tag, dict(element.attrib))
    kept.text = element.text
    for child in element:
        if child.tag in spec:
            kept.append(_prune(child, spec[child.tag]))
    return kept


def _drop_layout(element: ET.Element) -> ET.Element:
    """Drop whitespace-only text nodes — a notice is served pretty-printed, and it is data."""
    for node in element.iter():
        if node.text is not None and not node.text.strip():
            node.text = None
        if node.tail is not None and not node.tail.strip():
            node.tail = None
    return element


def trim_notice(body: bytes, spec: Spec) -> bytes:
    """Prune a CELLAR notice to the elements this project reads."""
    pruned = _drop_layout(_prune(fromstring(body), spec))
    # `tostring` is typed as returning `Any` for any encoding but the two it special-cases.
    return cast("bytes", ET.tostring(pruned, encoding="utf-8", xml_declaration=True))


def trim_formex_zip(body: bytes) -> bytes:
    """Rebuild a Formex package with its XML members only (see the module docstring).

    Bounded by the same `MAX_PACKAGE_BYTES` ceiling `eu/packages.py` states, because this is
    the other place a package off the network is decompressed into memory — and it is the
    *first* one, since `fetch_fixtures.py` trims a response before anything else reads it.
    """
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(body)) as source,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as target,
    ):
        check_package_size(source)
        for name in sorted(n for n in source.namelist() if n.lower().endswith(".xml")):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, source.read(name))
    return out.getvalue()
