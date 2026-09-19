"""An annex's subject, read back from its stored text: the rule's cases, and its measurement.

The rule prints words on a page that says it is computed from published texts, so a wrong
subject is a false statement about the law and a missing one is only the coordinate alone. The
unit cases pin what it refuses; the measurement runs it over every committed Formex package
against a reading of the XML's own structure and pins how often it fires and that it is never
wrong.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from xml.etree.ElementTree import Element

import pytest

from emendrix.core import (
    Change,
    ChangeType,
    LocationCode,
    LocationSegment,
    ProvisionLocation,
    ProvisionRef,
    ProvisionText,
    VersionId,
)
from emendrix.eu.formex import parse_act
from emendrix.eu.formex.documents import act_documents, documents_of, unit_elements
from emendrix.eu.formex.locations import annex_segment
from emendrix.eu.formex.model import CoverageCounter
from emendrix.eu.formex.text import flat_text
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.packages import FormexPackage
from emendrix.site_ import subject
from emendrix.site_.subject import annex_subject, is_capitals, provision_title
from eu_pins import FIXTURE_DIR

FIC_SUBJECT = "SUBSTANCES OR PRODUCTS CAUSING ALLERGIES OR INTOLERANCES"
FIC_TEXT = f"ANNEX II\n{FIC_SUBJECT}\n1. Cereals containing gluten, namely: wheat, rye"
"""The shape of the FIC Regulation's Annex II as its 2025-04-01 change stores it."""


def _second(line: str) -> str | None:
    return annex_subject("ANNEX II", "Annex II", f"ANNEX II\n{line}\n1. Something")


def test_the_second_line_is_the_subject_when_the_first_is_the_annex_s_own_title() -> None:
    assert annex_subject("ANNEX II", "Annex II", FIC_TEXT) == FIC_SUBJECT
    assert annex_subject(None, "Annex II", FIC_TEXT) == FIC_SUBJECT
    assert annex_subject("Annex II", "Annex II", FIC_TEXT) == FIC_SUBJECT


def test_a_no_break_space_in_the_first_line_still_matches_the_coordinate() -> None:
    assert annex_subject(None, "Annex II", FIC_TEXT.replace(" ", "\xa0", 1)) == FIC_SUBJECT


def test_the_candidate_is_trimmed_at_its_two_ends_and_nothing_else_is_touched() -> None:
    assert _second("  CE MARKING  OF\xa0CONFORMITY ") == "CE MARKING  OF\xa0CONFORMITY"


@pytest.mark.parametrize(
    "line",
    ["CHAPTER I", "PART A", "FOREWORD", "ENTRY 43", "SECTION 1", "TABLE: LIMITS", "ANNEX III"],
)
def test_a_line_that_heads_a_division_is_not_the_subject(line: str) -> None:
    assert _second(line) is None


@pytest.mark.parametrize("line", ["1. GENERAL", "(a) SCOPE", "IV. LIMITS", "B) LIMITS", "(12) X"])
def test_a_numbered_line_is_a_first_provision_and_not_the_subject(line: str) -> None:
    assert _second(line) is None


def test_a_word_made_of_numeral_letters_is_still_a_word() -> None:
    assert _second("CIVIL AVIATION SECURITY") == "CIVIL AVIATION SECURITY"


@pytest.mark.parametrize(
    "line",
    ["Substances or products causing allergies", "EXEMPTIONS UNDER ARTICLE 2(7)(b)", "", "EU"],
)
def test_a_lower_case_letter_an_empty_line_or_no_word_is_refused(line: str) -> None:
    assert _second(line) is None


def test_the_length_limit_is_two_hundred_characters() -> None:
    assert _second("A" * 200) == "A" * 200
    assert _second("A" * 201) is None


def test_a_text_that_does_not_open_with_the_annex_s_title_says_nothing() -> None:
    assert annex_subject("ANNEX II", "Annex II", f"ANNEX III\n{FIC_SUBJECT}") is None
    assert annex_subject("ANNEX II", "Annex II", f"\nANNEX II\n{FIC_SUBJECT}") is None
    assert annex_subject("ANNEX II", "Annex II", "ANNEX II") is None
    assert annex_subject("ANNEX II", "Annex II", None) is None


def test_capitals_means_no_lower_case_letter() -> None:
    assert is_capitals(FIC_SUBJECT)
    assert is_capitals("CE MARKING 2(7)")
    assert not is_capitals("Processing of special categories")


def _change(location: str, heading: str | None, text: str | None = FIC_TEXT) -> Change:
    return Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(
            act=act_id(Celex.parse("32011R1169")),
            version=VersionId("v2"),
            location=ProvisionLocation.parse(location),
        ),
        heading=heading,
        before=None if text is None else ProvisionText(text),
        after=None if text is None else ProvisionText(text),
    )


def test_a_stored_heading_that_says_more_is_preferred_to_the_text() -> None:
    assert provision_title(_change("AN II", "Allergens")) == "Allergens"


def test_a_bare_annex_heading_takes_the_subject_its_text_opens_with() -> None:
    assert provision_title(_change("AN II", "ANNEX II")) == FIC_SUBJECT
    assert provision_title(_change("AN II", None)) == FIC_SUBJECT


def test_the_newest_side_is_read_first() -> None:
    inserted = _change("AN II", "ANNEX II").model_copy(
        update={"before": ProvisionText("ANNEX II\nOLD SUBJECT")}
    )
    assert provision_title(inserted) == FIC_SUBJECT
    deleted = inserted.model_copy(update={"after": None})
    assert provision_title(deleted) == "OLD SUBJECT"


def test_a_bare_article_heading_prints_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(heading: str | None, human: str, text: str | None) -> str | None:
        raise AssertionError("the annex rule was asked about a provision that is not an annex")

    monkeypatch.setattr(subject, "annex_subject", refuse)
    article = f"Art. 5\n{FIC_SUBJECT}"
    assert provision_title(_change("AR 5", None, article)) is None
    assert provision_title(_change("AR 5", "ART. 5", article)) is None
    assert provision_title(_change("AN II PT 1", None)) is None
    assert provision_title(_change("AR 5", "Quorum", article)) == "Quorum"


# The measurement. A structural reading of each annex, from the same package's XML: the title of
# the one `GR.SEQ` its `CONTENTS` holds. Imperfect too, which is why it is a reference and the
# rule is scored against it rather than replaced by it.


def _packages() -> Iterator[FormexPackage]:
    for path in sorted(FIXTURE_DIR.glob("*.fmx4.zip")):
        name = VersionId(path.name)
        yield FormexPackage.from_zip(
            path.read_bytes(),
            act=act_id(Celex.parse("32011R1169")),
            requested_version=name,
            served_version=name,
            language="ENG",
            source_url=path.name,
            fetched_at=datetime(2026, 9, 19, tzinfo=UTC),
        )


def _reference(annex: Element) -> str | None:
    contents = annex.find("CONTENTS")
    if contents is None:
        return None
    children = list(contents)
    if len(children) != 1 or children[0].tag != "GR.SEQ":
        return None
    title = children[0].find("TITLE/TI")
    return None if title is None else flat_text(title)


def _references(package: FormexPackage) -> dict[str, str | None]:
    """Each numbered annex's structural subject, by coordinate, first document first."""
    found: dict[str, str | None] = {}
    for document in documents_of(act_documents(package, CoverageCounter())):
        for unit, is_annex in unit_elements(document):
            segment = annex_segment(unit) if is_annex else None
            if segment is not None:
                code, value = segment
                location = ProvisionLocation(segments=(LocationSegment(code=code, value=value),))
                found.setdefault(location.canonical, _reference(unit))
    return found


Reading = tuple[str | None, str | None, str | None]
"""`(stored heading, structural reference, what the rule read)` for one annex."""


@pytest.fixture(scope="module")
def readings() -> frozenset[Reading]:
    """Every bare-headed top-level annex of the 44 packages, deduplicated across versions."""
    seen: set[Reading] = set()
    count = 0
    for package in _packages():
        count += 1
        references = _references(package)
        for node in parse_act(package).tree.roots:
            segments = node.location.segments
            if len(segments) != 1 or segments[0].code != LocationCode.AN:
                continue
            human = node.location.human
            if node.heading and node.heading.casefold().split() != human.casefold().split():
                continue
            fired = annex_subject(node.heading, human, node.text)
            seen.add((node.heading, references[node.location.canonical], fired))
    assert count == 44
    return frozenset(seen)


def _agrees(fired: str, reference: str | None) -> bool:
    return reference is not None and fired.casefold().split() == reference.casefold().split()


def test_the_rule_is_never_wrong_over_the_committed_packages(readings: frozenset[Reading]) -> None:
    """The counts, measured 2026-09-19 over the 44 committed Formex packages.

    25 distinct bare-headed annexes (by stored heading, reference and reading). The rule read
    a subject from 18, and the structure's reading agrees on all 18. It read none where the
    structure has no subject, and none that disagrees. The structure names a subject the rule
    does not read in 2: MDR Annex V, whose subject holds the lower-case `(b)` of a coordinate,
    and MDR Annex VI, whose subject runs past 200 characters. Both are the rule saying nothing
    when a line is not the plain capitals of a title, which is the side it errs on.

    The structure also names a subject for two annexes outside this set: REACH's unnumbered
    `Appendices 1 to 6`, whose one group is titled `FOREWORD`, and REACH `Appendix 10`, whose
    group title opens `Entry 43`. Neither is a numbered top-level annex, so neither is a unit, and
    the first is why the structure is the reference rather than the rule.

    **If a count moves, that is a finding to explain, not a test to update.**
    """
    fired = [(heading, ref, got) for heading, ref, got in readings if got is not None]
    wrong = [item for item in fired if not _agrees(item[2], item[1])]
    reference_only = [item for item in readings if item[2] is None and item[1] is not None]
    assert wrong == []
    assert len(readings) == 25
    assert len(fired) == 18
    assert sum(_agrees(got, ref) for _, ref, got in fired) == 18
    assert len(reference_only) == 2
