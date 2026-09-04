"""An output repository whose third signal is wrong, built through the shipped machinery.

The suite needs an entry a repair actually has something to say about, and writing one by hand
would prove a repair against a document nothing wrote. So this takes the repository the shipped
command chain produced and puts the defect back into it with the same functions the repair uses
to take it out: an instruction signal that names a unit nothing else saw and misses one that
everything else saw, merged through `corroborate` and committed through `OutputRepo`.

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
from emendrix.eu.signals import instruction_signal_for
from emendrix.output import ChangelogEntry, OutputRepo
from emendrix.repair import RepairResult, RepairTarget, read_targets
from emendrix.repair.corroborate import amending_act_of, instructions_of, needs, repair
from emendrix.session import adapter_for
from eu_pins import FIXTURE_DIR, OBSERVED_ON

PHANTOM = ProvisionLocation.parse("AR 99")
"""A unit no version of the act has, which is the shape a misread instruction heading produces."""

NEIGHBOUR_FROM = VersionId("02017R0745-20170101")
NEIGHBOUR_TO = VersionId("02017R0745-20170505")
"""An older transition of the same act, so its entry sorts below the one under repair."""


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


def corrected(target: RepairTarget) -> RepairResult:
    """One target repaired against the instruction signal today's parser reads, offline.

    The composition step the shipped command does: resolve the amending act the payload names,
    parse its pinned package, and hand the signal to a repair that knows no corpus at all.
    """
    amender = amending_act_of(target.entry)
    assert amender is not None, target.path
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        signal = instruction_signal_for(adapter.client, celex_of(amender), target.entry.act)
    return repair(target, signal)


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
