"""The Formex 4 parser, against the seven pinned Formex packages.

Several numbers here are measured twice by unrelated code: on 2026-08-05 by the standalone
validation script (`scripts/validation/trace.py`, reports under `scripts/validation/results/`)
and on 2026-08-06 by this parser. Where the two agree, two independent implementations agree.
**If one of these numbers moves, that is a finding to explain, not a test to update.**
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, date, datetime
from xml.etree.ElementTree import Element

import pytest

from emendrix.core import ProvisionLocation, ProvisionTree, VersionId, normalize_for_comparison
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import Formex4Parser, parse_act
from emendrix.eu.formex.documents import act_documents
from emendrix.eu.formex.model import CoverageCounter
from emendrix.eu.formex.text import BLOCK_ELEMENTS, SKIPPED_SUBTREES
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.packages import FormexPackage, read_package
from emendrix.eu.xml_ import NOT_WELL_FORMED, fromstring
from eu_pins import (
    AI_ACT,
    AI_ACT_V2,
    FIXTURE_DIR,
    MDR,
    MDR_V1,
    MDR_V2,
    REACH,
    REACH_2008,
    REACH_2009,
    package,
)

# The act as published in the OJ is its own version tag (`eu/identifiers.py`).
AI_ACT_OJ = AI_ACT

MDR_2026 = "02017R0745-20260101"
"""The MDR consolidation whose Article 59(1) carries two `DATE` elements mid-sentence."""


def tree_of(client: CellarClient, celex: str, version: str) -> ProvisionTree:
    return parse_act(package(client, celex, version)).tree


def units(tree: ProvisionTree) -> dict[str, str]:
    """Top-level unit → its comparison form. The map the diff is computed over."""
    return {node.location.canonical: node.comparison_text for node in tree.roots}


def codes(tree: ProvisionTree, prefix: str) -> list[str]:
    return [unit.canonical for unit in tree.unit_locations() if unit.canonical.startswith(prefix)]


# --------------------------------------------------------------------------- shape


@pytest.mark.parametrize(
    ("celex", "version", "articles", "annexes"),
    [
        # `units in v(original): 126` / `units in v(20260727): 133`, validated 2026-08-06.
        (AI_ACT, AI_ACT_OJ, 113, 13),
        (AI_ACT, AI_ACT_V2, 119, 14),
        (MDR, MDR_V1, 123, 17),
        (MDR, MDR_V2, 123, 17),
        # `units in v(20081012): 158`, which is 141 articles and 17 annexes.
        (REACH, REACH_2008, 141, 17),
        (REACH, REACH_2009, 141, 17),
    ],
)
def test_every_pinned_document_yields_the_validated_unit_counts(
    client: CellarClient, celex: str, version: str, articles: int, annexes: int
) -> None:
    tree = tree_of(client, celex, version)
    assert len(codes(tree, "AR ")) == articles
    assert len(codes(tree, "AN ")) == annexes
    assert len(tree.roots) == articles + annexes


def test_the_inserted_article_of_the_flagship_transition_is_found_by_identifier(
    client: CellarClient,
) -> None:
    """`IDENTIFIER="004A"` → `AR 4a`, and the same act's version 1 has no such article."""
    v2 = tree_of(client, AI_ACT, AI_ACT_V2)
    assert v2.find("AR 4a") is not None
    assert tree_of(client, AI_ACT, AI_ACT_OJ).find("AR 4a") is None


def test_an_unnumbered_annex_is_not_a_unit(client: CellarClient) -> None:
    """REACH opens with a `LIST OF ANNEXES` and the MDR with `ANNEXES`; neither is a provision."""
    for celex, version in ((REACH, REACH_2008), (MDR, MDR_V1)):
        tree = tree_of(client, celex, version)
        assert [unit for unit in tree.unit_locations() if unit.canonical == "AN"] == []
        assert tree.find("AN I") is not None


def test_reach_appendices_ride_inside_their_annex_rather_than_beside_it(
    client: CellarClient,
) -> None:
    """Ten `Appendix n` documents nest inside `CONS.ANNEX`; they are sub-provisions, not units."""
    annex = tree_of(client, REACH, REACH_2008).find("AN XVII")
    assert annex is not None
    appendices = [child.location.canonical for child in annex.children]
    assert "AN XVII APP 1" in appendices
    assert "AN XVII APP 10" in appendices


# ------------------------------------------------------------------------ locations


@pytest.mark.parametrize(
    "location",
    [
        # Locations the AI Act's own CELLAR modification metadata publishes for this version
        # (`tests/fixtures/eu/celex_32024R1689.branch.xml`, read 2026-08-06).
        "AR 5 PA 1 ALN 1 PTA (bb)",
        "AR 5 PA 1 ALN 1 PTA (ba)",
        "AR 5 PA 1a",
        "AR 96 PA 1 ALN 1 PTA (g)",
        "AR 25 PA 4 ALN 1",
        "AN I SCT A PO 1",
        "AN VIII SCT B PO 7",
        "AN I SCT B PO 21",
    ],
)
def test_metadata_locations_resolve_against_the_parsed_tree(
    client: CellarClient, location: str
) -> None:
    assert tree_of(client, AI_ACT, AI_ACT_V2).find(location) is not None


def test_the_metadata_elides_intermediate_segments_the_structure_keeps(
    client: CellarClient,
) -> None:
    """`AR 3 PO 14` in the metadata is `AR 3 ALN 1 PO 14` in the markup.

    Reconciling the two is corroboration's job, not the parser's: the unit of change is the
    top-level provision and both forms agree on that. Pinned here so the discrepancy is
    a documented fact rather than a surprise.
    """
    tree = tree_of(client, AI_ACT, AI_ACT_V2)
    assert tree.find("AR 3 PO 14") is None
    assert tree.find("AR 3 ALN 1 PO 14") is not None
    assert tree.find("AR 113 ALN 3 PTA (a)") is not None


def test_roman_and_alphabetic_points_are_told_apart_by_their_list(client: CellarClient) -> None:
    """`LIST TYPE="roman"` → `PTI (i)`; everything lettered → `PTA (a)`. AI Act Art. 113(c)."""
    tree = tree_of(client, AI_ACT, AI_ACT_V2)
    assert tree.find("AR 113 ALN 3 PTA (c) PTI (i)") is not None
    assert tree.find("AR 113 ALN 3 PTA (c) PTI (ii)") is not None


def test_every_location_round_trips_and_is_unique(client: CellarClient) -> None:
    """The canonical string is the identity: parsing it back must give the same location."""
    for celex, version in ((AI_ACT, AI_ACT_V2), (REACH, REACH_2008)):
        tree = tree_of(client, celex, version)
        canonical = [node.location.canonical for node in tree.walk()]
        assert len(canonical) == len(set(canonical))
        assert all(ProvisionLocation.parse(raw).canonical == raw for raw in canonical)


# ----------------------------------------------------------------------------- text


def test_stored_text_is_verbatim_and_the_comparison_form_is_built_separately(
    client: CellarClient,
) -> None:
    """The two forms are built at extraction, not one string normalised twice.

    Deriving the comparison form from the stored text is the bug that reports all 143
    comparable REACH units as modified against 40 real ones. The document's own no-break space
    inside `Article\xa04` survives into the stored text and is collapsed only in the form built
    for comparing, which is what "verbatim" is protecting. On a provision with no inline
    element at any boundary the two forms do collapse to the same string, and that is expected
    rather than a sign that one was derived from the other; the test below is where they part.
    """
    node = tree_of(client, AI_ACT, AI_ACT_V2).find("AR 4")
    assert node is not None
    assert node.text.startswith("Article\xa04\nAI literacy\n")
    assert node.comparison_text.startswith("Article 4 AI literacy")


def test_a_provision_reads_the_way_the_document_prints_it(client: CellarClient) -> None:
    """Formex leaves no text between one block and the next, so extraction has to supply it.

    Read off the 2017-05-05 consolidation on 2026-08-12: `</TI.ART><STI.ART>`,
    `</STI.ART><PARAG>` and `</NO.PARAG><ALINEA>` are directly adjacent in the source, so a
    join with nothing produces `59Derogation`, `procedures1.By` and `health.2.The`, sequences
    that appear neither in the document nor in any published rendering of the law.
    """
    node = tree_of(client, MDR, MDR_V1).find("AR 59")
    assert node is not None
    assert node.text.startswith(
        "Article\xa059\nDerogation from the conformity assessment procedures\n1. By way of"
    )
    for run_together in ("59Derogation", "procedures1.", "health.2."):
        assert run_together not in node.text


def test_an_inline_element_is_still_joined_with_nothing(client: CellarClient) -> None:
    """`<DATE>` sits mid-clause, and a blanket separator would break the sentence around it.

    Measured on the 2026-01-01 consolidation: Article 59(1) reads `for the period from
    24 April 2020 to 25 May 2021, by way of derogation`, where both dates and the comma after
    the second are `DATE` elements and their tails. A separator at every boundary spaces them
    out; the block-level one leaves them alone.

    That inline boundary is also where the two stored forms genuinely part: the comparison
    form separates there too, so it carries `2021 ,` where the stored text carries `2021,`.
    Collapsing the stored text can therefore never reproduce it, which is why both are built
    at extraction and neither is derived from the other.
    """
    node = tree_of(client, MDR, MDR_2026).find("AR 59")
    assert node is not None
    assert "for the period from 24 April 2020 to 25 May 2021, by way of derogation" in node.text
    assert "25 May 2021 , by way of derogation" in node.comparison_text
    assert normalize_for_comparison(node.text) != node.comparison_text


def test_no_block_separator_lands_inside_a_run_of_text() -> None:
    """The block set, checked against every committed package rather than against one article.

    A separator is inserted only immediately before a `BLOCK_ELEMENTS` child, so the way it
    could damage a sentence is for such a child to sit inside its parent's flowing text. This
    walks all 44 committed Formex packages, every member, every element, and asserts that no
    tag in the set ever carries text immediately before or after it. That is the whole safety
    argument for the set, and it is a measurement rather than a claim: 670867 such boundaries
    on 2026-08-12, none of them inside a run of text.
    """
    boundaries = 0
    for path in sorted(FIXTURE_DIR.glob("*.fmx4.zip")):
        for member in read_package(path.read_bytes()):
            if not member.is_xml:
                continue
            try:
                root = fromstring(member.data)
            except NOT_WELL_FORMED:  # a corrupt member is somebody else's test
                continue
            boundaries += _block_boundaries(root, path.name)
    assert boundaries == 670867


def _block_boundaries(parent: Element, where: str) -> int:
    """Every block boundary under `parent`, asserting each is free of adjacent text."""
    found = 0
    children = list(parent)
    for index, child in enumerate(children):
        if child.tag in SKIPPED_SUBTREES:
            continue
        if child.tag in BLOCK_ELEMENTS:
            found += 1
            lead = (parent.text if index == 0 else children[index - 1].tail) or ""
            trail = child.tail or ""
            assert not lead.strip(), f"{where}: {parent.tag}/{child.tag} follows {lead[-40:]!r}"
            assert not trail.strip(), f"{where}: {parent.tag}/{child.tag} precedes {trail[:40]!r}"
        found += _block_boundaries(child, where)
    return found


@pytest.mark.parametrize(
    ("celex", "version"),
    [
        (AI_ACT, AI_ACT_V2),
        (MDR, MDR_V1),
        (MDR, MDR_V2),
        (REACH, REACH_2008),
        (REACH, REACH_2009),
    ],
)
def test_a_provisions_text_contains_every_sub_provisions_text(
    client: CellarClient, celex: str, version: str
) -> None:
    """The property `explain/context.py` computes its `shown` set from, asserted not reasoned.

    A separator is inserted by the element doing the walking, into its own stream, never into
    a child's, so a child's fragments still land contiguously inside its parent's. `_support`
    depends on that: it decides whether a sub-provision was visible in the capped evidence by
    testing its own verbatim text for literal containment in the unit's.
    """
    for node in tree_of(client, celex, version).walk():
        for inner in node.walk():
            if inner is node or not str(inner.text).strip():
                continue
            assert str(inner.text) in str(node.text), (
                f"{inner.location.canonical} is not inside {node.location.canonical}"
            )


def test_publication_metadata_is_not_provision_text(client: CellarClient) -> None:
    """A standalone `ANNEX` document carries a `BIB.INSTANCE` its consolidation does not.

    Including it fabricates annex changes: the same annex, unchanged between the OJ
    act and the consolidation, would compare unequal.
    """
    published = units(tree_of(client, AI_ACT, AI_ACT_OJ))
    consolidated = units(tree_of(client, AI_ACT, AI_ACT_V2))
    assert published["AN II"] == consolidated["AN II"]
    assert "L_202401689EN" not in published["AN II"]


def test_dates_are_extracted_with_their_surrounding_text(client: CellarClient) -> None:
    """AI Act Art. 113 carries the deferred application dates. They are quoted, never read."""
    node = tree_of(client, AI_ACT, AI_ACT_V2).find("AR 113")
    assert node is not None
    values = [mention.value for mention in node.dates]
    assert date(2027, 12, 2) in values
    assert date(2028, 8, 2) in values
    deferred = next(mention for mention in node.dates if mention.value == date(2027, 12, 2))
    assert "high-risk" in deferred.context


def test_parsing_is_deterministic(client: CellarClient) -> None:
    """Changelogs are diffed in git, so two runs must produce the same tree, byte for byte."""
    fetched = package(client, AI_ACT, AI_ACT_V2)
    assert parse_act(fetched).tree == parse_act(fetched).tree


# ------------------------------------------------------------------------- the diff


@pytest.mark.parametrize(
    ("celex", "before", "after", "inserted", "modified", "deleted", "unchanged"),
    [
        # All three re-derived through this parser on 2026-08-06.
        (AI_ACT, AI_ACT_OJ, AI_ACT_V2, 7, 38, 0, 88),
        (MDR, MDR_V1, MDR_V2, 0, 9, 0, 131),
        (REACH, REACH_2008, REACH_2009, 0, 40, 0, 118),
    ],
)
def test_the_comparison_form_reproduces_the_validated_structural_diff(
    client: CellarClient,
    celex: str,
    before: str,
    after: str,
    inserted: int,
    modified: int,
    deleted: int,
    unchanged: int,
) -> None:
    """The set difference the diff computes, computed here on the parser's output alone.

    This is the regression guard for text extraction: get the separator wrong and `modified`
    explodes (143 instead of 40 on the REACH pair); get `BIB.INSTANCE` wrong and the
    annexes move.
    """
    old, new = units(tree_of(client, celex, before)), units(tree_of(client, celex, after))
    common = set(old) & set(new)
    changed = {unit for unit in common if old[unit] != new[unit]}
    assert len(set(new) - set(old)) == inserted
    assert len(set(old) - set(new)) == deleted
    assert len(changed) == modified
    assert len(common - changed) == unchanged


def test_the_flagship_insertions_are_exactly_the_ones_the_digital_omnibus_published(
    client: CellarClient,
) -> None:
    old, new = (
        units(tree_of(client, AI_ACT, AI_ACT_OJ)),
        units(tree_of(client, AI_ACT, AI_ACT_V2)),
    )
    assert sorted(set(new) - set(old)) == [
        "AN XIV",
        "AR 4a",
        "AR 60a",
        "AR 75a",
        "AR 75b",
        "AR 75c",
        "AR 75d",
    ]


# --------------------------------------------------------------------- coverage


@pytest.mark.parametrize(
    ("celex", "version", "documents", "nodes", "flattened"),
    [
        # Parser coverage as measured on 2026-08-06. `containers_flattened` is the honest
        # degradation number: it rises from 20 on the 2023-schema AI Act to 229 on the
        # 2006-schema REACH text, whose annexes group prose under untitled `GR.SEQ`s that
        # restart their own enumerators.
        (AI_ACT, AI_ACT_OJ, 14, 1872, 14),
        (AI_ACT, AI_ACT_V2, 1, 2079, 20),
        (MDR, MDR_V1, 1, 2585, 118),
        (MDR, MDR_V2, 1, 2590, 118),
        (REACH, REACH_2008, 1, 1859, 229),
        (REACH, REACH_2009, 1, 1863, 229),
    ],
)
def test_parser_coverage_is_a_measured_number(
    client: CellarClient, celex: str, version: str, documents: int, nodes: int, flattened: int
) -> None:
    coverage = parse_act(package(client, celex, version)).coverage
    assert coverage.documents == documents
    assert coverage.nodes == nodes
    assert coverage.containers_flattened == flattened
    # Across all five documents and two Formex generations: nothing outside the vocabulary,
    # no identifier that would not decode, no unreadable date, and no article whose `TI.ART`
    # contradicts its `IDENTIFIER`.
    assert coverage.unknown_elements == ()
    assert coverage.unmapped_identifiers == 0
    assert coverage.unreadable_dates == 0
    assert coverage.heading_mismatches == 0
    assert coverage.clean


def test_a_member_that_is_not_xml_is_counted_rather_than_raised_on(client: CellarClient) -> None:
    """Coverage gaps are counted, not crashed on, including a corrupt archive member."""
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("broken.xml", b"<ACT><ENACTING.TERMS></ACT>")
    fetched = FormexPackage.from_zip(
        blob.getvalue(),
        act=act_id(Celex.parse(AI_ACT)),
        requested_version=VersionId(AI_ACT_V2),
        served_version=VersionId(AI_ACT_V2),
        language="ENG",
        source_url="https://example.invalid/",
        fetched_at=datetime(2026, 8, 6, tzinfo=UTC),
    )
    counter = CoverageCounter()
    assert act_documents(fetched, counter) == (None, ())
    assert counter.freeze().documents_unreadable == 1
    assert parse_act(fetched).tree.roots == ()


def test_the_adapter_default_parser_is_the_real_one(client: CellarClient) -> None:
    """No stub left: constructing the parser with no arguments parses the pinned act."""
    tree = Formex4Parser().parse_version(package(client, AI_ACT, AI_ACT_V2))
    assert len(tree.roots) == 133
    assert tree.version == VersionId(AI_ACT_V2)
    assert tree.language == "ENG"
