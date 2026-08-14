"""The corpus selection rules, on versions the pinned notices do not happen to contain.

`test_corpus.py` asserts what the committed corpus *is*; this asserts what the generator would
do with a notice unlike the four acts' own. Every real consolidation CELLAR publishes is dated,
because the date is part of the consolidated CELEX the record is built from, so the undated case
below is latent. It is tested anyway, because latent and silent is the combination this project
treats as worse than loud and broken.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from emendrix.core import VersionId
from emendrix.eu.identifiers import Celex, ResourceRef, act_id
from emendrix.eu.notices import Manifestation, TreeNotice, VersionRecord, WorkMetadata
from emendrix.eval_.build import _pairs, _skip, _usable

CELEX = Celex.parse("32024R1689")
FORMEX = Manifestation(
    language="ENG", format="fmx4", ref=ResourceRef(system="celex", identifier="x.ENG.fmx4")
)


def _version(
    raw: str,
    *,
    when: date | None,
    english: bool = True,
    kind: Literal["original", "consolidated"] = "consolidated",
) -> VersionRecord:
    return VersionRecord(
        version=VersionId(raw),
        kind=kind,
        version_date=when,
        manifestations=(FORMEX,) if english else (),
    )


def _notice(*versions: VersionRecord) -> TreeNotice:
    return TreeNotice(work=WorkMetadata(celex=CELEX, act=act_id(CELEX)), versions=versions)


def test_an_undated_version_cannot_close_a_window() -> None:
    """Its id would be `<celex>@99991231` and its window would have no ceiling.

    Two such transitions of one act mint the same `CorpusCase.id`, and `EvalCorpus.case`
    answers with the first, so a pinned explanation subset could be scored against a different
    transition than it was pinned against. Silently, which is the wrong failure direction.
    """
    undated = _version("02024R1689-XX", when=None)
    assert not _usable(undated)
    skip = _skip("32024R1689", undated)
    assert skip.reason == "version_date_unknown"
    assert skip.detail, "a skip that names no reason is a version dropped in silence"


def test_an_undated_version_is_bridged_exactly_like_an_unreadable_one() -> None:
    """Stepped over, never ending the chain, exactly like a version with no English text."""
    first = _version("02024R1689-20240101", when=date(2024, 1, 1))
    undated = _version("02024R1689-XX", when=None)
    textless = _version("02024R1689-20250101", when=date(2025, 1, 1), english=False)
    last = _version("02024R1689-20260727", when=date(2026, 7, 27))

    pairs = _pairs(_notice(first, undated, textless, last))
    assert [(before.version, after.version) for before, after in pairs] == [
        (first.version, last.version)
    ]


def test_a_version_with_no_english_still_skips_for_the_reason_it_actually_has() -> None:
    """The two rules answer separately: the older one keeps naming the state that is true."""
    skip = _skip(
        "32024R1689", _version("02024R1689-20250101", when=date(2025, 1, 1), english=False)
    )
    assert skip.reason == "structured_text_unavailable"


def test_the_original_version_may_be_undated_because_its_date_never_closes_a_window() -> None:
    """It sorts first and `opens` is `None` for it by design, so exempting it loses no case."""
    original = _version("32024R1689", when=None, kind="original")
    later = _version("02024R1689-20260727", when=date(2026, 7, 27))
    assert _usable(original)
    assert len(_pairs(_notice(original, later))) == 1
