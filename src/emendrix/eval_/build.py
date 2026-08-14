"""Generating the labelled corpus — the only part of the eval layer that may touch the network.

`emendrix eval build-corpus` walks each act's tree notice (which versions exist, and in which
formats) and its branch notice (the modification annotations that are the reference label set),
applies the selection rules of `corpus.py`, and, with `pins.py`, writes three committed
artifacts:

```
tests/fixtures/eu/eval_pins.json   the documents the corpus needs, for eu/fetch_fixtures.py
tests/fixtures/eu/…                those documents, pinned and trimmed by that script
src/emendrix/eval_/corpus.json     the case list, with each case's inputs pinned by digest
```

After that the whole eval runs offline from the fixture set, which is why `runner.py` contains no
network at all and CI can run the full deterministic eval on every push.

**Fixture volume, decided deliberately.** The corpus commits every input it scores rather than
priming a cache in CI, which is smaller in the repository and mysterious everywhere else: the
published numbers would depend on documents nobody could see. Inputs are trimmed by the
reproducible rules in `eu/trims.py` (Formex packages keep only their XML members; notices keep
only the elements the parsers read), with one cap: an amending act's own Formex is pinned for the
third signal only when it stays under `MAX_INSTRUCTION_BYTES`. The CLP Regulation `32008R1272` is
3.3 MB of Formex and is the reason the cap exists; a case that loses the third signal to it
records that as its `instruction_note` and ships the signal as `UNAVAILABLE`.
"""

from __future__ import annotations

from datetime import date
from itertools import pairwise
from typing import Final

from emendrix.eu.cellar import CellarClient
from emendrix.eu.identifiers import Celex
from emendrix.eu.modmeta import ModificationSet, parse_branch_modifications
from emendrix.eu.notices import FORMEX_FORMAT, TreeNotice, VersionRecord
from emendrix.eval_.corpus import (
    REACH_SAMPLE,
    CorpusAct,
    CorpusCase,
    CorpusSkip,
    EvalCorpus,
    sample_indices,
)

__all__ = ["ACTS", "MAX_INSTRUCTION_BYTES", "build_corpus"]

REACH: Final = "32006R1907"

ACTS: Final[tuple[tuple[str, int | None], ...]] = (
    ("32024R1689", None),
    ("32017R0745", None),
    (REACH, REACH_SAMPLE),
    ("32022R2065", None),
)
"""The four scored acts, with the sample size where one applies. `None` means every transition."""

MAX_INSTRUCTION_BYTES: Final = 512 * 1024
"""Cap on an amending act's own Formex, trimmed, before it is pinned for the third signal.

Measured 2026-08-06: the pinned amending acts weigh 7 KB (`32020R0561`) and 44 KB
(`32026R1744`); the CLP Regulation `32008R1272` weighs 3.3 MB. The cap sits far above the first
and far below the last, so it excludes exactly the outlier and nothing that is merely ordinary.
"""

_NO_TEXT: Final = "structured_text_unavailable"
_NO_DATE: Final = "version_date_unknown"


def _has_text(record: VersionRecord) -> bool:
    """Whether the notice offers this version as English Formex — the only form the diff reads."""
    return record.manifestation("ENG", FORMEX_FORMAT) is not None


def _has_date(record: VersionRecord) -> bool:
    """Whether this version can close a window.

    A case is identified by the date it moves *to*, and its metadata window is
    `(date(A), date(B)]`, so an undated later version has neither an id nor a ceiling — and
    both failures are silent ones. Two undated transitions of one act would mint the same
    `CorpusCase.id`, and `EvalCorpus.case` answers with the first, so a subset could be pinned
    against one and scored against another; the open ceiling would meanwhile sweep every later
    annotation the act ever received into the window. The original version is exempt: it sorts
    first and can only ever *open* a window, where `opens` is `None` for it by design, so its
    own date never enters the arithmetic.
    """
    return record.version_date is not None or record.kind == "original"


def _usable(record: VersionRecord) -> bool:
    """Whether this version can be an endpoint of a measured transition at all."""
    return _has_text(record) and _has_date(record)


def _skip(act: str, record: VersionRecord) -> CorpusSkip:
    if not _has_text(record):
        formats = record.formats("ENG")
        detail = (
            f"the tree notice offers {', '.join(formats)} in English"
            if formats
            else f"the tree notice offers no English expression, only {', '.join(record.languages)}"
        )
        reason = _NO_TEXT
    else:
        detail = "the tree notice dates no version of this consolidation, so no window closes here"
        reason = _NO_DATE
    return CorpusSkip(
        act=act,
        version=str(record.version),
        version_date=record.version_date,
        reason=reason,
        detail=detail,
    )


def _pairs(notice: TreeNotice) -> tuple[tuple[VersionRecord, VersionRecord], ...]:
    """Consecutive pairs of the versions that can be endpoints — readable, and dated.

    A version with no English Formex is bridged over rather than ending the chain, because the
    question "what changed since the last text a reader could see?" is the one worth asking and
    because the metadata window `(date(A), date(B)]` folds in every amending act between them
    correctly. The bridge is never silent: the skipped versions are listed on the case and in the
    report's skip table. This is also what makes the flagship transition exist at all — the AI
    Act's middle consolidation is published in eleven languages, English not among them.

    An undated version is bridged the same way and for the same reason (`_has_date`).
    """
    return tuple(pairwise([record for record in notice.versions if _usable(record)]))


def _bridged(notice: TreeNotice, before: VersionRecord, after: VersionRecord) -> tuple[str, ...]:
    """Versions this pair steps over because their text could not be read."""
    inside = False
    skipped: list[str] = []
    for record in notice.versions:
        if record.version == before.version:
            inside = True
            continue
        if record.version == after.version:
            break
        if inside and not _usable(record):
            skipped.append(str(record.version))
    return tuple(skipped)


def _case(
    notice: TreeNotice,
    mods: ModificationSet,
    pair: tuple[VersionRecord, VersionRecord],
    selection: str,
) -> CorpusCase:
    before, after = pair
    celex = notice.work.celex.value
    opens = None if before.kind == "original" else before.version_date
    until = after.version_date
    if until is None:  # pragma: no cover - `_pairs` never offers an undated later version
        raise ValueError(f"{after.version} closes a window but the notice does not date it")
    window = mods.between(opens, until)
    amending = tuple(sorted({record.amending_celex for record in window if record.amending_celex}))
    return CorpusCase(
        id=f"{celex}@{until.strftime('%Y%m%d')}",
        act=celex,
        act_title=notice.work.title,
        from_version=str(before.version),
        to_version=str(after.version),
        from_date=before.version_date,
        to_date=until,
        from_original=before.kind == "original",
        bridged=_bridged(notice, before, after),
        amending_acts=amending,
        annotations=len(window),
        instruction_source=amending[0] if len(amending) == 1 else None,
        instruction_note=(
            ""
            if len(amending) == 1
            else f"the window names {len(amending)} amending acts; the third signal reads one"
        ),
        selection=selection,
    )


def build_corpus(client: CellarClient, *, built_on: date) -> EvalCorpus:
    """Select every case and every skip from the acts' own notices.

    Network, unless the client was built on a fixture cache.
    """
    acts: list[CorpusAct] = []
    cases: list[CorpusCase] = []
    skips: list[CorpusSkip] = []
    for celex, sample in ACTS:
        parsed = Celex.parse(celex)
        notice = client.tree_notice(parsed)
        mods = parse_branch_modifications(client.branch_notice(parsed))
        skips.extend(_skip(celex, record) for record in notice.versions if not _usable(record))
        pairs = _pairs(notice)
        chosen = tuple(range(len(pairs))) if sample is None else sample_indices(len(pairs), sample)
        label = "all" if sample is None else f"sample {sample} of {len(pairs)}, evenly spread"
        cases.extend(_case(notice, mods, pairs[index], label) for index in chosen)
        acts.append(
            CorpusAct(
                celex=celex,
                title=notice.work.title,
                versions=len(notice.versions),
                versions_usable=sum(1 for record in notice.versions if _usable(record)),
                transitions_possible=len(pairs),
                transitions_selected=len(chosen),
                annotations=len(mods.records),
                amending_acts=len(mods.amending_acts),
                note=(
                    "no transition: the corpus publishes no second readable version — a corpus "
                    "member for future amendments"
                    if not pairs
                    else ""
                ),
            )
        )
    return EvalCorpus(
        built_on=built_on,
        note=(
            "Generated by `emendrix eval build-corpus` from the acts' own CELLAR tree and branch "
            "notices. No label in this file was written by hand."
        ),
        acts=tuple(acts),
        cases=tuple(sorted(cases, key=lambda case: case.id)),
        skips=tuple(sorted(skips, key=lambda skip: (skip.act, skip.version))),
    )
