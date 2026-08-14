"""Citation URLs: EUR-Lex HTML anchors, because ELI does not resolve at provision level.

Provision-level ELI URIs do not resolve: `…/eli/reg/2024/1689/oj/art_5` → **404** (verified
2026-08-05). What does resolve is the EUR-Lex rendition of the consolidated act, whose anchors
are stable:

```
https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02024R1689-20260727#art_5
```

**Anchor vocabulary, verified 2026-08-06** against the XHTML manifestation of
`02024R1689-20260727` (`consolidation/2024R1689%2F20260727.ENG.xhtml` — the same rendition
EUR-Lex serves, fetched from CELLAR because eur-lex.europa.eu answers programmatic clients
with a `202` challenge page): **119** article anchors, `art_1` … `art_113`, including the
lettered insertions `art_4a`, `art_60a`, `art_75a` to `art_75d`; and **14** annex anchors,
`anx_I` … `anx_XIV`. Articles lower-case their letter suffix, annexes keep upper-case roman
numerals.

**The anchor is per top-level unit — there is no deeper one.** EUR-Lex publishes nothing for
a paragraph or a point, so `AR 5 PA 1 ALN 1 PTA (bb)` links to `#art_5` while its label stays
exact: `Art. 5(1)(bb)`. The link is as deep as the corpus allows; the label is as deep as the
change is. Losing the second to match the first would be the wrong trade.
"""

from __future__ import annotations

import re
from typing import Final

from emendrix.core import Citation, LocationCode, ProvisionLocation, ProvisionRef, VersionId

__all__ = ["EURLEX_HTML", "anchor_for", "document_url", "render_citation"]

EURLEX_HTML: Final = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:"

_ARTICLE_NUMBER: Final = re.compile(r"^(\d+[A-Za-z]?)")
_ANNEX_NUMBER: Final = re.compile(r"^([IVXLCDM]+|\d+[A-Za-z]?)$", re.IGNORECASE)


def document_url(version: VersionId) -> str:
    """The EUR-Lex HTML rendition of one version of one act."""
    return f"{EURLEX_HTML}{version}"


def anchor_for(location: ProvisionLocation) -> str | None:
    """The deepest EUR-Lex anchor for a location, or `None` when there is no anchor for it.

    `None` is the honest answer for anything whose top-level unit is neither an article nor
    an annex (a title, a recital, a code outside the vocabulary): the citation then points at
    the document, and the label still says exactly where.
    """
    head = location.segments[0]
    if head.value is None:
        return None
    if head.code is LocationCode.AR:
        # `AR 3.20` is Article 3 point 20 — the anchor is the article's.
        matched = _ARTICLE_NUMBER.match(head.value)
        return f"art_{matched[1].lower()}" if matched else None
    if head.code is LocationCode.AN:
        return f"anx_{head.value.upper()}" if _ANNEX_NUMBER.fullmatch(head.value) else None
    return None


def render_citation(ref: ProvisionRef) -> Citation:
    """A clickable, human-labelled citation for one provision of one version."""
    anchor = anchor_for(ref.location)
    url = document_url(ref.version)
    return Citation(
        ref=ref,
        url=f"{url}#{anchor}" if anchor else url,
        label=f"{ref.location.human}, {ref.version}",
    )
