"""Entries as they were published before the signal rules, and as the loop writes them today.

Each pair is built through the shipped machinery from pinned inputs: the loop's own signals
for one transition, then the same signals put back into the shape an entry published before
2026-10-08 carries them in, merged by `corroborate` exactly as the loop merged them then. The
repair is handed only the older entry, so a test can ask whether the payload alone carries it
to the entry the loop writes today.

Three older shapes, one per rule, each the shape the published record holds:

- **A legacy annex numeral.** REACH's notice writes `AN 4` and `AN 5` for the annexes the markup
  numbers `AN IV` and `AN V`. Entries published before the metadata's codes were read as units
  carry those claims as written, so the two diff changes ship disputed and two textless rows
  ship beside them.
- **A container key.** The notice keys one annotation of REACH's 2008-to-2009 window on
  `TIT XI`, a title. Before, it was a claim like any other and a textless row.
- **A silent instruction parse.** REACH's 2012 amender claims nothing in the window ending
  2012-10-09. Before, that was an available signal with no claims, and every unit the diff found
  shipped disputed against it.

The toy entry carries none of these and one instruction-only row, so the repair is shown to run
over a corpus that is not law with a normaliser that knows nothing.
"""

from __future__ import annotations

from datetime import date

from textless_rows import with_instruction_only_row

from emendrix.core import (
    Delta,
    ProvisionLocation,
    Signal,
    SignalClaim,
    SignalReport,
    VersionId,
)
from emendrix.corroborate import corroborate
from emendrix.diff import compute_delta
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.modmeta import ModificationRecord, metadata_signal, parse_branch_modifications
from emendrix.eu.signals import EuSignalSource
from emendrix.gate import GateOutcome
from emendrix.graph.report import EmittedChange, EmittedDelta
from emendrix.output import DIFF_ONLY_NOTE, ChangelogEntry
from emendrix.repair.corroborate import textless_change
from emendrix.repair.signals import SILENT
from eu_pins import OBSERVED_ON, REACH, package
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

__all__ = [
    "LEGACY_ANNEXES",
    "REACH_CONTAINER",
    "REACH_PAIRS",
    "TOY_PHANTOM",
    "entry_of",
    "reach_pair",
    "toy_entry",
]

REACH_ACT = act_id(Celex.parse(REACH))

LEGACY_ANNEXES = {"AN IV": "AN 4", "AN V": "AN 5"}
"""The markup's numerals against what REACH's legacy notice writes for the same annexes."""

REACH_CONTAINER = "TIT XI"
"""The one container key REACH's notice dates in the window ending 2009-01-20."""

REACH_PAIRS = (
    ("02006R1907-20071123", "02006R1907-20081012"),
    ("02006R1907-20081012", "02006R1907-20090120"),
    ("02006R1907-20120605", "02006R1907-20121009"),
)
"""One transition per older shape: the legacy numerals, the container, the silent parse."""

TOY_PHANTOM = ProvisionLocation.parse("AR 7")
"""A unit no version of the toy act has, named by the toy's instruction signal alone."""


def entry_of(
    delta: Delta, metadata: SignalReport | None, instructions: SignalReport | None
) -> ChangelogEntry:
    """One transition merged and wrapped as the loop wraps it, with no prose on any change.

    A change the diff observed carries the diff-only note; a textless one carries the reason
    the explain stage records against it, which is what every repair restates it to.
    """
    merged = corroborate(delta, metadata=metadata, instructions=instructions)
    changes = tuple(
        textless_change(change)
        if change.textless
        else EmittedChange(
            change=change, outcome=GateOutcome.UNEXPLAINED, unexplained=DIFF_ONLY_NOTE
        )
        for change in merged.delta.changes
    )
    return ChangelogEntry.of(
        EmittedDelta(
            act=merged.delta.act,
            from_version=merged.delta.from_version,
            to_version=merged.delta.to_version,
            summary=merged.delta.summary,
            changes=changes,
            corroboration=merged.report,
        ),
        detected_on=OBSERVED_ON,
    )


def reach_pair(
    client: CellarClient, before: str, after: str
) -> tuple[ChangelogEntry, ChangelogEntry]:
    """One REACH transition as published before the rules, and as the loop writes it today."""
    delta = compute_delta(
        parse_act(package(client, REACH, before)).tree,
        parse_act(package(client, REACH, after)).tree,
    )
    metadata, instructions = _signals_today(client, before, after)
    today = entry_of(delta, metadata, instructions)
    older = entry_of(
        delta, _older_metadata(client, metadata, before, after), _older_instructions(instructions)
    )
    return older, today


def toy_entry() -> ChangelogEntry:
    """The toy transition with an instruction-only row, in the shape published before the rule.

    The metadata names every unit the diff found and one it did not, so a textless row the merge
    still appends sits beside the one it no longer does.
    """
    adapter = ToyCorpusAdapter(observed_on=OBSERVED_ON)
    first, second = adapter.fetch_version(HOUSE_RULES, V1), adapter.fetch_version(HOUSE_RULES, V2)
    assert not isinstance(first, Exception) and not isinstance(second, Exception)
    delta = compute_delta(first, second)  # type: ignore[arg-type]
    claims = tuple(SignalClaim(location=change.unit) for change in delta.changes)
    metadata = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=(*claims, SignalClaim(location=ProvisionLocation.parse("AR 9"))),
        note="the toy's minutes",
    )
    instructions = SignalReport(
        signal=Signal.INSTRUCTION_PARSE,
        claims=(*claims, SignalClaim(location=TOY_PHANTOM)),
        note="the toy's rule change",
    )
    return with_instruction_only_row(entry_of(delta, metadata, instructions), TOY_PHANTOM)


# ------------------------------------------------------------------ the pieces


def _signals_today(
    client: CellarClient, before: str, after: str
) -> tuple[SignalReport, SignalReport | None]:
    """What the loop's own signal source says about one pair, offline.

    REACH's 2008-to-2009 window folds in an amender whose package is deliberately not pinned,
    so that pair is given no instruction signal, and its metadata is read the way the source
    reads it.
    """
    if (before, after) == REACH_PAIRS[1]:
        records = _records(client, before, after)
        note = f"{len(records)} annotations in ({_date_of(before)}, {_date_of(after)}]"
        return metadata_signal(records, note=note), None
    found = EuSignalSource(client).signals_for(REACH_ACT, VersionId(before), VersionId(after))
    assert found.metadata is not None
    return found.metadata, found.instructions


def _older_metadata(
    client: CellarClient, today: SignalReport, before: str, after: str
) -> SignalReport:
    """The metadata signal with its codes as the notice writes them, containers claimed."""
    assert today.available
    records = _records(client, before, after)
    claims = tuple(_respelled(record.to_claim()) for record in records)
    note = f"{len(records)} annotations in ({_date_of(before)}, {_date_of(after)}]"
    return today.model_copy(update={"claims": claims, "note": note})


def _records(client: CellarClient, before: str, after: str) -> tuple[ModificationRecord, ...]:
    notice = parse_branch_modifications(client.branch_notice(Celex.parse(REACH)))
    return notice.between(_date_of(before), _date_of(after))


def _respelled(claim: SignalClaim) -> SignalClaim:
    legacy = LEGACY_ANNEXES.get(claim.location.canonical)
    if legacy is None:
        return claim
    return claim.model_copy(update={"location": ProvisionLocation.parse(legacy)})


def _older_instructions(today: SignalReport | None) -> SignalReport | None:
    """An instruction signal that claims nothing, put back to available with its older note."""
    if today is None or today.available:
        return today
    assert today.note is not None and today.note.endswith(f", {SILENT}")
    return SignalReport(signal=today.signal, note=today.note.removesuffix(f", {SILENT}"))


def _date_of(version: str) -> date:
    digits = version.rsplit("-", 1)[1]
    return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
