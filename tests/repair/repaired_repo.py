"""Output repositories with a defect put back into them, built through the shipped machinery.

The suite needs an entry a repair actually has something to say about, and writing one by hand
would prove a repair against a document nothing wrote. So this takes the repository the shipped
command chain produced and puts the defect back into it with the same functions the repair uses
to take it out.

Three defects, one per repair kind. `poisoned_repo` gives the entry an instruction signal that
names a unit nothing else saw and misses one that everything else saw, merged through
`corroborate` and committed through `OutputRepo`. `unexplained_repo` takes the prose off the
first few changes and puts each of the counted reasons a change can carry no explanation in its
place, which is the state the explanation repair has to tell apart. `raw_reason_repo` does the
same with the notes a change carried before the curated reasons existed: two of them a library's
own error text, two of them the house register, so a selector that reached wider than it should
would be caught by the pair.

A second entry is written into the same act's `CHANGELOG.md` so that "every other entry keeps
its bytes" is a claim with a neighbour to check it against. Its version identifiers are the only
thing that differs from the first, which is all the file's layout reads.

A sibling of `tests/site_/site_entries.py` rather than a shared module: the test tree has one
conftest and no `__init__.py`, so a module here imports its own directory's neighbours by name,
and two modules of one name anywhere under `tests/` are ambiguous to `mypy --strict`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from emendrix.core import ActId, ProvisionLocation, Signal, SignalClaim, SignalReport, VersionId
from emendrix.eu.identifiers import celex_of
from emendrix.eu.instructions import Window
from emendrix.eu.signals import instruction_signal_for
from emendrix.explain import (
    MODEL_FAILED,
    NO_EVIDENCE_PAST_CAP,
    NOTHING_TO_EXPLAIN,
    PROVIDER_UNAVAILABLE,
)
from emendrix.gate import GateOutcome
from emendrix.graph.report import EmittedChange
from emendrix.output import ChangelogEntry, OutputRepo
from emendrix.repair import RepairResult, RepairTarget, delta_of, read_targets, rebuild
from emendrix.repair.cli import window_of
from emendrix.repair.corroborate import amending_act_of, instructions_of, needs, repair
from emendrix.session import adapter_for
from eu_pins import FIXTURE_DIR, OBSERVED_ON

PHANTOM = ProvisionLocation.parse("AR 99")
"""A unit no version of the act has, which is the shape a misread instruction heading produces."""

NEIGHBOUR_FROM = VersionId("02017R0745-20170101")
NEIGHBOUR_TO = VersionId("02017R0745-20170505")
"""An older transition of the same act, so its entry sorts below the one under repair."""

RAW_MODEL_FAILURE = "UnexpectedModelBehavior: Exceeded maximum output retries (1)"
"""A malformed answer as the provider library named it, verbatim.

Written out here rather than imported, so a change to the set the repair matches on is a test
failure rather than two constants agreeing with each other. Measured 2026-09-04 over the
published changelogs, where it is the only raw text of this shape any entry carries."""

RAW_PROVIDER_FAILURE = "ModelAPIError: Connection error."
"""The other raw text those entries carry: a provider that never answered, not a bad answer."""

UNEXPLAINED = (
    (MODEL_FAILED, "model_failed"),
    (MODEL_FAILED, ""),
    (NOTHING_TO_EXPLAIN, "nothing_to_explain"),
    (NO_EVIDENCE_PAST_CAP, "no_evidence_past_cap"),
    (PROVIDER_UNAVAILABLE, "provider_unavailable"),
)
"""The five states a change with no prose can be in, in the order they are injected.

The first two are the same failure written under two schemas: a change written since the kind
existed carries it, and one written before carries the curated reason alone. Both are the
explanation repair's business and the other three are not.
"""

RAW_REASONS = (
    (RAW_MODEL_FAILURE, ""),
    (RAW_PROVIDER_FAILURE, ""),
    (NOTHING_TO_EXPLAIN, ""),
    (MODEL_FAILED, ""),
)
"""Four notes carrying no kind, in the order they are injected.

The first is the one the restating repair addresses and the second is the one it must count and
refuse to stamp. The last two are the trap: reasons this project curated, carried by a change
written before the kind existed, and a selector matching on anything looser than the exact text
of the first would take them with it.
"""


def poisoned_repo(source: Path, destination: Path) -> Path:
    """A copy of `source` whose one entry carries a phantom unit and one avoidable dispute.

    Two defects, because a corrected signal fixes two different things: a unit it invented,
    which leaves the entry entirely, and a unit it failed to see, whose change was marked
    disputed and whose explanation was written under a prompt saying the signals disagreed.
    """
    shutil.copytree(source, destination)
    repository = OutputRepo.open(destination)
    for target in read_targets(repository.path):
        spoiled = repair(target, _misread(target))
        assert spoiled.entry is not None, target.path
        repository.write(spoiled.entry)
        repository.write(_neighbour(spoiled.entry))
    return repository.path


def unexplained_repo(source: Path, destination: Path) -> Path:
    """A copy of `source` whose one entry has lost its prose on one change of each state.

    Written back through `rebuild` and `OutputRepo`, so the document under test is one the
    shipped machinery produced and the counts in its header match the changes it holds.
    """
    shutil.copytree(source, destination)
    repository = OutputRepo.open(destination)
    for target in read_targets(repository.path):
        # The neighbour keeps its prose, so it is an entry this repair has nothing to say
        # about and a real check that a pass leaves such an entry alone.
        repository.write(_neighbour(target.entry))
        repository.write(_stripped(target.entry))
    return repository.path


def raw_reason_repo(source: Path, destination: Path) -> Path:
    """A copy of `source` whose one entry carries the notes written before the kinds existed.

    Built the same way and for the same reason: the document under test is one the shipped
    writer produced, so what a repair reads is what a reader is served.
    """
    shutil.copytree(source, destination)
    repository = OutputRepo.open(destination)
    for target in read_targets(repository.path):
        repository.write(_neighbour(target.entry))
        repository.write(_stripped(target.entry, RAW_REASONS))
    return repository.path


def unexplained_target(root: Path) -> RepairTarget:
    """The one entry of such a repository whose first change lost its prose."""
    found = [target for target in read_targets(root) if target.entry.changes[0].unexplained]
    assert len(found) == 1, [str(target.path) for target in found]
    return found[0]


def _stripped(
    entry: ChangelogEntry, states: tuple[tuple[str, str], ...] = UNEXPLAINED
) -> ChangelogEntry:
    changes = list(entry.changes)
    assert len(changes) > len(states), "the entry needs a change left over as a sibling"
    for index, (reason, kind) in enumerate(states):
        assert changes[index].sentences, "a change with no prose proves nothing here"
        changes[index] = EmittedChange(
            change=changes[index].change,
            outcome=GateOutcome.UNEXPLAINED,
            unexplained=reason,
            unexplained_kind=kind,
        )
    return rebuild(
        entry, delta=delta_of(entry), corroboration=entry.corroboration, changes=tuple(changes)
    )


def poisoned_target(root: Path) -> RepairTarget:
    """The one entry of a poisoned repository the repair has something to say about.

    Named rather than indexed: the neighbour written beside it sorts first by path, and a test
    that reached for it by position would silently assert about the wrong document.
    """
    found = [target for target in read_targets(root) if needs(target)]
    assert len(found) == 1, [str(target.path) for target in found]
    return found[0]


def restored_unit(target: RepairTarget) -> str:
    """The unit the poisoned signal dropped, which a corrected parse hands back."""
    return target.entry.changes[0].change.unit.canonical


def with_stale_reason(target: RepairTarget, reason: str) -> RepairTarget:
    """The same entry with an older wording on every change that carries no text.

    The shape of an entry written before this project reworded the one sentence such a change
    can carry, which is the state a pass over an already-published corpus meets.
    """
    changes = tuple(
        EmittedChange(change=item.change, outcome=item.outcome, unexplained=reason)
        if item.change.textless
        else item
        for item in target.entry.changes
    )
    assert any(item.change.textless for item in changes), target.path
    entry = rebuild(
        target.entry,
        delta=delta_of(target.entry),
        corroboration=target.entry.corroboration,
        changes=changes,
    )
    return RepairTarget(path=target.path, entry=entry)


def _misread(target: RepairTarget) -> SignalReport:
    """The committed instruction signal as a parser reading the wrong coordinate would leave it."""
    committed = instructions_of(target.entry)
    assert committed is not None and committed.available, target.path
    dropped = restored_unit(target)
    return committed.model_copy(
        update={
            "claims": (
                *(claim for claim in committed.claims if claim.unit.canonical != dropped),
                SignalClaim(location=PHANTOM, amending_act=_amender(committed)),
            )
        }
    )


def _amender(committed: SignalReport) -> ActId | None:
    return next((claim.amending_act for claim in committed.claims if claim.amending_act), None)


def _neighbour(entry: ChangelogEntry) -> ChangelogEntry:
    """A second entry for the same act, so the file under repair has a sibling block.

    It carries no corroboration, which is the shape of an event whose window named no amending
    act, so the repair has nothing to say about it and it is a sibling worth checking.
    """
    return entry.model_copy(
        update={
            "from_version": NEIGHBOUR_FROM,
            "to_version": NEIGHBOUR_TO,
            "corroboration": None,
        }
    )


def instruction_units(entry: ChangelogEntry) -> tuple[str, ...]:
    """The units the entry's committed instruction signal names, in its own order."""
    report = instructions_of(entry)
    return () if report is None else tuple(unit.canonical for unit in report.units)


def units_of(entry: ChangelogEntry) -> tuple[str, ...]:
    """Every top-level unit the entry ships a change for, in the entry's own order."""
    return tuple(dict.fromkeys(item.change.unit.canonical for item in entry.changes))


def signal_of(entry: ChangelogEntry, signal: Signal) -> tuple[str, ...]:
    """One signal's units as the committed corroboration report publishes them."""
    report = entry.corroboration
    assert report is not None
    return tuple(unit.canonical for unit in report.units_of(signal))


def signal_for(entry: ChangelogEntry, window: Window | None) -> SignalReport:
    """Today's parse of the amending act one entry names, scoped to `window`, offline.

    The window is a value the caller holds, exactly as the command holds one: nothing below
    here reads a version inventory or a clock to find out which consolidation this is.
    """
    amender = amending_act_of(entry)
    assert amender is not None, entry.to_version
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        return instruction_signal_for(adapter.client, celex_of(amender), entry.act, window=window)


def corrected(target: RepairTarget) -> RepairResult:
    """One target repaired against the instruction signal today's parser reads, offline.

    The composition step the shipped command does, window and all: resolve the amending act the
    payload names, read the consolidation window off the same payload, parse the pinned package
    under it, and hand the signal to a repair that knows no corpus at all.
    """
    return repair(target, signal_for(target.entry, window_of(target.entry)))


def copied(source: Path, destination: Path) -> Path:
    """A repository a test may commit into without disturbing the module-scoped original."""
    shutil.copytree(source, destination)
    return destination


def log(repo: Path) -> list[str]:
    """Every revision in the repository, newest first."""
    return _git("log", "--format=%H", cwd=repo).split()


def porcelain(repo: Path) -> str:
    """What git considers uncommitted. Empty is a clean working tree."""
    return _git("status", "--porcelain", cwd=repo)


def _git(*arguments: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout
