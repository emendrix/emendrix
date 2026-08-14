"""Citation URLs: the exact EUR-Lex anchor, character for character."""

from __future__ import annotations

import pytest

from emendrix.core import ProvisionLocation, ProvisionRef, VersionId
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.links import anchor_for, render_citation
from eu_pins import AI_ACT, AI_ACT_V2

AI_ACT_ID = act_id(Celex.parse(AI_ACT))
V2 = VersionId(AI_ACT_V2)


def ref(location: str, version: VersionId = V2) -> ProvisionRef:
    return ProvisionRef(act=AI_ACT_ID, version=version, location=ProvisionLocation.parse(location))


def test_the_verified_url_character_for_character() -> None:
    """Verified 2026-08-05: provision-level ELI 404s and this EUR-Lex anchor resolves."""
    citation = render_citation(ref("AR 5"))
    assert citation.url == (
        "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02024R1689-20260727#art_5"
    )


@pytest.mark.parametrize(
    ("location", "anchor"),
    [
        # Verified 2026-08-06 against the XHTML manifestation of 02024R1689-20260727:
        # 119 `art_*` anchors and 14 `anx_*` anchors.
        ("AR 1", "art_1"),
        ("AR 113", "art_113"),
        ("AR 4a", "art_4a"),
        ("AR 75d", "art_75d"),
        ("AN I", "anx_I"),
        ("AN XIV", "anx_XIV"),
        # Deeper coordinates ride along in the label; EUR-Lex has no anchor for them.
        ("AR 5 PA 1 ALN 1 PTA (bb)", "art_5"),
        ("AN VI PRT C SCT 6.6.2", "anx_VI"),
        # `AR 3.20` is Article 3 point 20, so the anchor is the article's.
        ("AR 3.20", "art_3"),
    ],
)
def test_anchors_for_every_shape_the_corpus_emits(location: str, anchor: str) -> None:
    assert anchor_for(ProvisionLocation.parse(location)) == anchor


@pytest.mark.parametrize("location", ["TIT XI", "CONSID 61", "AR", "AN"])
def test_no_anchor_is_invented_where_eur_lex_publishes_none(location: str) -> None:
    """A title or a recital has no anchor; the citation points at the document instead."""
    parsed = ProvisionLocation.parse(location)
    assert anchor_for(parsed) is None
    citation = render_citation(ref(location))
    assert "#" not in citation.url
    assert citation.url.endswith(AI_ACT_V2)


def test_the_label_stays_as_deep_as_the_change_is() -> None:
    """The link is as deep as the corpus allows; the label is as deep as the change."""
    citation = render_citation(ref("AR 5 PA 1 ALN 1 PTA (bb)"))
    assert citation.url.endswith("#art_5")
    assert citation.label.startswith("Art. 5(1)")
    assert citation.label.endswith(f", {AI_ACT_V2}")


def test_the_original_act_is_cited_by_its_own_celex() -> None:
    citation = render_citation(ref("AR 5", VersionId(AI_ACT)))
    assert citation.url == (
        "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32024R1689#art_5"
    )
