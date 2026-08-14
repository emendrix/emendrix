"""The XML parsing policy, and the reason there is one.

Every document the adapter reads is bytes from a remote endpoint. The stdlib's ElementTree
does not resolve external entities, so XXE is not reachable, but it does expand internal ones,
and `test_the_stdlib_parser_is_the_reason_this_module_exists` is that claim measured rather
than asserted. The threat is availability of a batch job against one government endpoint over
HTTPS, not disclosure; the fix is cheap enough that the modest severity does not argue against
it.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from defusedxml import DefusedXmlException

from emendrix.eu.packages import FormexMember, consolidation_info
from emendrix.eu.xml_ import NOT_WELL_FORMED, fromstring

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

BOMB = b"""<?xml version="1.0"?>
<!DOCTYPE r [
  <!ENTITY a "xxxxxxxxxx">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
]>
<r>&c;</r>"""
"""Three levels of a billion-laughs document, at 300-odd bytes.

Each further level multiplies the expansion by ten.
"""


def test_the_stdlib_parser_is_the_reason_this_module_exists() -> None:
    """Not a theoretical concern: measured here, so the swap has a number behind it."""
    expanded = ET.fromstring(BOMB).text or ""
    assert len(expanded) == 1000
    assert len(expanded) > len(BOMB)


def test_the_hardened_parser_refuses_what_the_stdlib_expands() -> None:
    with pytest.raises(DefusedXmlException):
        fromstring(BOMB)


def test_a_refusal_and_a_corrupt_document_are_the_same_kind_of_finding() -> None:
    """Why `NOT_WELL_FORMED` is a tuple: the two failures are different exception families.

    `ParseError` is a `SyntaxError` and defusedxml's refusals are `ValueError`s, so a call site
    that widened only one of them would turn a counted coverage gap into a crash, which is the
    failure mode this project explicitly does not accept.
    """
    for bad in (BOMB, b"<r><unclosed>"):
        with pytest.raises(NOT_WELL_FORMED):
            fromstring(bad)


def test_ordinary_formex_is_untouched_by_the_hardening() -> None:
    """The swap is only worth making because it costs nothing that was ever being read."""
    root = fromstring(
        b'<ACT><ARTICLE IDENTIFIER="004A"><TI.ART>Article 4a</TI.ART></ARTICLE></ACT>'
    )
    assert root.tag == "ACT"
    assert root.find(".//TI.ART") is not None


def _fixture_documents() -> Iterator[tuple[str, bytes]]:
    """Every committed document, as `(where it is, its bytes)`, inside the archives too.

    Most of the corpus is zipped, and a compressed member does not contain the byte string
    `<!DOCTYPE` in any form a scan would find, so reading the archives as opaque bytes would
    quietly check nothing at all.
    """
    for path in sorted(FIXTURES.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix != ".zip":
            yield path.relative_to(FIXTURES).as_posix(), path.read_bytes()
            continue
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    name = f"{path.relative_to(FIXTURES).as_posix()}!{info.filename}"
                    yield name, archive.read(info)


def test_no_committed_document_carries_a_dtd_or_an_entity() -> None:
    """The evidence that no real document loses coverage, checked rather than assumed.

    Formex 4 in the wild does not use entity declarations. This is what makes that claim
    something the build re-checks every time a fixture is re-recorded, rather than a sentence
    somebody wrote once, and it is the whole reason the swap can be called free.
    """
    offenders = [
        name for name, data in _fixture_documents() if b"<!DOCTYPE" in data or b"<!ENTITY" in data
    ]
    assert offenders == []


def test_every_committed_document_still_parses_through_the_hardened_reader() -> None:
    """The direct form of the same claim: nothing in the corpus is refused."""
    refused = []
    for name, data in _fixture_documents():
        if data.lstrip()[:1] != b"<":
            continue
        try:
            fromstring(data)
        except DefusedXmlException:
            refused.append(name)
        except ET.ParseError:
            pass  # Not well-formed is a counted coverage gap, and a different question.
    assert refused == []


def test_the_pull_parser_refuses_a_doctype_it_cannot_see_the_end_of() -> None:
    """`eu/packages.py` keeps `XMLPullParser`, which defusedxml ships no wrapper for, so it guards.

    The guard is on `DOCTYPE` rather than on `ENTITY` because the parser is fed a truncated
    8 KB head: a declaration may be cut off mid-token, and the `DOCTYPE` is the only reliable
    signal that there is an internal subset here at all. Provenance is best-effort, so the
    answer is `None`, the same answer a member with no provenance block gives.
    """
    hostile = (
        b'<?xml version="1.0"?><!DOCTYPE CONS.DOC [<!ENTITY a "x">]>'
        b'<CONS.DOC><INFO.CONSLEG CONSLEG.REF="02024R1689" /></CONS.DOC>'
    )
    assert consolidation_info((FormexMember(name="a.xml", data=hostile),)) is None

    benign = b'<CONS.DOC><INFO.CONSLEG CONSLEG.REF="02024R1689" /></CONS.DOC>'
    found = consolidation_info((FormexMember(name="a.xml", data=benign),))
    assert found is not None
    assert found.reference == "02024R1689"
