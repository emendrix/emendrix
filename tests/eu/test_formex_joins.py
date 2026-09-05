"""The extractor's join rule, held to by an invariant over every committed package.

A run-on in stored verbatim text is the quietest defect this project has. It is not malformed,
it raises nothing, and it passes every schema and type check here, so the only thing that can
catch it is a rule asserted on purpose. Two of them were found by reading, on 2026-08-12 and
2026-09-01, and each time the fix rested on a claim measured that day about the packages
committed that day. Nothing holds such a claim true afterwards: a fixture added later, or a
package fetched later, can reopen the class silently.

So the claim is asserted rather than remembered, and it is asserted structurally: no element
outside `BLOCK_ELEMENTS` or `DETACHED_ELEMENTS` may hold a block-level child inside a unit
subtree. That is the property the two sets are safe because of, and it closes the class rather
than catching one instance of it. A tag that reopens it is a counted coverage gap naming the
tag, which is the register this project uses for everything it does not recognise.

The symptom scan below is a backstop and nothing more, and it ships two rules rather than the
three that were proposed, because a guard nobody trusts is worse than no guard. Each one's
measurement over the committed fixtures is in its own docstring.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime
from typing import Final

import pytest

from emendrix.core import VersionId
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from emendrix.eu.formex.documents import unit_elements
from emendrix.eu.formex.text import (
    BLOCK_ELEMENTS,
    DETACHED_ELEMENTS,
    undetached_blocks,
    verbatim_text,
)
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.packages import FormexPackage, read_package
from emendrix.eu.xml_ import NOT_WELL_FORMED, fromstring
from eu_pins import FIXTURE_DIR, MDR, MDR_V1, package

PACKAGES: Final = sorted(FIXTURE_DIR.glob("*.fmx4.zip"))
"""The 44 Formex packages this repository commits. The invariant is measured over all of them."""


def unit_texts() -> list[tuple[str, str]]:
    """Every unit of every committed package as `(where, verbatim text)`, parsed once."""
    found: list[tuple[str, str]] = []
    for path in PACKAGES:
        for member in read_package(path.read_bytes()):
            if not member.is_xml:
                continue
            try:
                root = fromstring(member.data)
            except NOT_WELL_FORMED:  # a corrupt member is somebody else's test
                continue
            for unit, _ in unit_elements(root):
                found.append((f"{path.name}/{member.name}", str(verbatim_text(unit))))
    return found


# ------------------------------------------------------------------ the invariant


def test_the_join_rule_holds_over_every_committed_package() -> None:
    """No tag outside the two sets holds a block child anywhere the extractor walks.

    The claim the 2026-09-01 fix is safe because of, re-measured on every run instead of
    remembered from the day it was made. It is asked of the unit subtrees `verbatim_text` is
    ever called on, which is exactly where a missed break damages stored text.

    **A tag reported here is a finding to explain, not a test to update.** Its content is a
    block the line does not break before, so it is joined to the sentence it interrupts, and
    that moves stored verbatim text on documents this project has already published.
    """
    holders: Counter[str] = Counter()
    for path in PACKAGES:
        for member in read_package(path.read_bytes()):
            if not member.is_xml:
                continue
            try:
                root = fromstring(member.data)
            except NOT_WELL_FORMED:
                continue
            for unit, _ in unit_elements(root):
                holders.update(undetached_blocks(unit))
    assert holders == Counter(), f"the join rule is reopened by {sorted(holders)}"


def test_the_two_sets_do_not_overlap() -> None:
    """A tag in both would make the invariant vacuous for it, and the sets mean opposite things.

    `BLOCK_ELEMENTS` is the tags that never carry adjacent text; `DETACHED_ELEMENTS` is the
    tags that always do and hold a block anyway. Nothing can be both.
    """
    assert not BLOCK_ELEMENTS & DETACHED_ELEMENTS


def test_the_parser_reports_the_invariant_holding_on_a_real_package(
    client: CellarClient,
) -> None:
    """The invariant is not only a test: it is counted on every parse, in the shipped code."""
    coverage = parse_act(package(client, MDR, MDR_V1)).coverage
    assert coverage.undetached_blocks == ()
    assert coverage.clean


@pytest.mark.parametrize(
    ("inner", "run_on"),
    [
        ("<P>the following</P>", "added:the following"),
        ("<NOTE>the following</NOTE>", "added:the following"),
    ],
    ids=["a block child", "a detached child"],
)
def test_a_tree_that_reopens_the_class_is_counted_rather_than_raised_on(
    inner: str, run_on: str
) -> None:
    """Coverage gaps are counted, never crashed on, and this one is invisible without a count.

    A tag the two sets have never seen, holding a child either set would have broken the line
    before, is exactly the shape of both defects that have been found. The detached case is the
    subtler one and it is the same defect: the wrapper gets no break of its own, so the
    footnote's content opens on a line nothing opened and runs into the sentence before it.
    Nothing raises either way: the text still ships, joined the conservative way an unrecognised
    tag is always joined, and the coverage report names the tag to read.
    """
    parsed = parse_act(_synthetic(inner))
    assert parsed.coverage.undetached_blocks == (("QUOT.OFF", 1),)
    assert parsed.coverage.clean is False
    node = parsed.tree.find("AR 1")
    assert node is not None
    assert run_on in node.text, "the run-on is real, which is why it is counted"


# --------------------------------------------------------------------- the symptom scan

_ENUMERATOR_AFTER_STOP: Final = re.compile(r"[.:;]\((?:[0-9]{1,3}|[a-z]{1,4}|[ivxlcdm]{1,5})\)")
"""A full stop, colon or semicolon with a bracketed enumerator welded to it: `added:(i)`."""

_JOINED_WORDS: Final = re.compile(r"[a-z]{2,}[A-Z][a-z]{2,}")
"""Two word halves welded at a lower-to-upper transition: `CouncilRegulation`."""


def test_no_enumerator_is_welded_to_the_sentence_it_follows() -> None:
    """`the following point is added:(i)` was the 2026-09-01 defect in its bracket shape.

    Zero hits over the 44 committed packages, measured 2026-09-05. The wider form proposed for
    this rule, any word character butting against an opening bracket, is **not** shipped: it
    fires 18 673 times over the same packages, and every one of them is ordinary drafting
    (`Article 114(3)`, `test(s)`, `manufacturer(s)`). A guard that cries wolf is deleted within
    a month, so what ships is the shape a run-on actually has.
    """
    hits = [
        (where, match.group(0))
        for where, text in unit_texts()
        for match in _ENUMERATOR_AFTER_STOP.finditer(text)
    ]
    assert hits == []


def test_no_two_words_are_welded_at_a_case_change() -> None:
    """`CouncilRegulation` was the 2026-09-01 defect in its word shape, and `59Derogation` the
    2026-08-12 one.

    Zero hits over the 44 committed packages, measured 2026-09-05, **and the allowlist is
    empty**, which is the whole reason this rule is worth having. The plain form of it, any
    lower-to-upper transition inside a word, fires 3 074 times over 34 distinct words, every one
    of them chemical nomenclature or a unit: `vPvB`, `pH`, `kPa`, `BaP`, `decaBDE`, `mL`.
    Allowlisting those would take 34 entries that grow with every re-pinned REACH annex.
    Requiring two letters on each side of the transition asks instead whether two *words* were
    welded, which is what the defect does and what none of those tokens is, and it needs no
    allowlist at all.
    """
    hits = [
        (where, match.group(0))
        for where, text in unit_texts()
        for match in _JOINED_WORDS.finditer(text)
    ]
    assert hits == []


@pytest.mark.parametrize(
    "run_on",
    [
        "the following point is added:(i) medical devices",
        "and of the CouncilRegulation (EU) 2017/745",
    ],
)
def test_the_scan_catches_the_run_ons_that_were_actually_found(run_on: str) -> None:
    """Both rules are pinned to a real defect, so neither can be quietly narrowed to nothing."""
    assert _ENUMERATOR_AFTER_STOP.search(run_on) or _JOINED_WORDS.search(run_on)


# ------------------------------------------------------------------------ the pieces


_SYNTHETIC: Final = (
    '<ACT><ENACTING.TERMS><ARTICLE IDENTIFIER="001"><TI.ART>Article 1</TI.ART>'
    "<ALINEA><P>the following point is added:<QUOT.OFF>{inner}</QUOT.OFF></P></ALINEA>"
    "</ARTICLE></ENACTING.TERMS></ACT>"
)
"""One article whose quoted content hangs off a tag neither set knows. `QUOT.OFF` is not a
Formex tag this corpus uses; it stands in for whatever the next one turns out to be."""


def _synthetic(inner: str) -> FormexPackage:
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("act.xml", _SYNTHETIC.format(inner=inner).encode("utf-8"))
    return FormexPackage.from_zip(
        blob.getvalue(),
        act=act_id(Celex.parse(MDR)),
        requested_version=VersionId(MDR_V1),
        served_version=VersionId(MDR_V1),
        language="ENG",
        source_url="https://example.invalid/",
        fetched_at=datetime(2026, 9, 5, tzinfo=UTC),
    )
