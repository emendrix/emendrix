#!/usr/bin/env python
"""Which published explanations describe evidence today's parser no longer produces.

One-off validation code, kept so the reach of a corrective re-explanation is a reproducible
artifact rather than an assertion. Two parser fixes changed stored verbatim text after most of
the corpus was written: on 2026-08-12 the extractor stopped running words together across every
block boundary, and on 2026-09-01 it stopped splicing a footnote or a quoted passage into the
middle of the sentence it interrupts. An explanation is the one thing this pipeline cannot
recompute, so a change whose text moved carries prose written about evidence the page no longer
shows, and re-asking costs money.

**Nothing published records what the model was shown.** Entries written from 2026-09-05 carry an
evidence digest and answer this question by arithmetic; the ones written before that carry none
and never will, because deriving one would assert a fact about a call nobody witnessed. So for
the corpus that already exists the question is asked the long way, once, here:

1. read each committed payload and take its act and its two version tags;
2. re-derive both versions' provision trees through the same client, parser and disk cache the
   loop uses, one parse per version rather than one per event;
3. for each change, digest the verbatim texts the payload holds and the verbatim texts today's
   trees produce for the same location, and compare the two.

Each change lands in one of three answers: **matches**, **differs**, or **cannot be derived**,
the last where the version is not in the cache, is not readable in English, or holds no such
location any more. A textless change, which another signal named and the text comparison never
saw, carries no evidence on either side; it matches by construction and is reported separately
so it never pads the figure a rebuild is priced from.

**The left-hand side is the entry's own digest where it has one and its stored text otherwise**,
and the two are counted separately so a reader can tell them apart. The comparison is between
two texts either way, and it says nothing about provenance: a payload's stored text is a fact
the payload states, while what the model was shown is a fact only the run that made the call can
record. This script never writes a digest onto anything, and an entry that carries none is
reported as provenance unknown rather than quietly given one.

That rule and the state machine over it live in `emendrix.repair.staleness`, imported here
rather than repeated, because `emendrix repair evidence` selects the changes it pays to ask
about with the same comparison. Two notions of "differs", one measuring the reach of a
correction and one deciding what it costs, would drift within a month.

It writes nothing, calls no model and spends nothing. Offline by default: a package the disk
cache does not hold is counted as underivable and reported, and there is no path from a miss to
a socket unless `--fetch` is passed.

Usage, from the repository root::

    git clone https://github.com/emendrix/changelogs <somewhere>
    uv run python scripts/validation/evidence_staleness.py <somewhere>
    uv run python scripts/validation/evidence_staleness.py <somewhere> --verbose

The corpus is a separate repository and is never committed here, so the reading is dated by the
commit of the clone it was taken over, which the script prints if `git` can answer.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from emendrix.core import ProvisionLocation, ProvisionTree, VersionId
from emendrix.eu.cache import DiskResponseCache, FixtureMissing, default_cache_dir
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from emendrix.eu.http import CellarHttp
from emendrix.eu.identifiers import Celex
from emendrix.eu.packages import FormexPackage
from emendrix.explain import ExplainSettings
from emendrix.output import ChangelogEntry, EvidenceState, checked, recorded_digests
from emendrix.output.provenance import ChangeKey, digest_of_texts, keys_of
from emendrix.repair.staleness import stated

OBSERVED_ON = date(2026, 9, 5)
"""Passed in rather than read from a clock, exactly as the CLI boundary passes it."""


class OfflineDiskCache(DiskResponseCache):
    """The shared disk cache, refusing to fall through to the network."""

    @property
    def offline(self) -> bool:
        return True


class Trees:
    """Today's provision trees, one parse per version however many events ask for it.

    The corpus reuses a consolidation as the later side of one event and the earlier side of
    the next, so the 446 events published by 2026-09-05 name 520 distinct versions between
    them. Parsing per event would read most packages twice.
    """

    def __init__(self, client: CellarClient) -> None:
        self._client = client
        self._trees: dict[tuple[str, str], ProvisionTree | str] = {}

    def of(self, key: str, version: str) -> ProvisionTree | str:
        """One version's tree, or the stated reason there is none to compare against."""
        found = self._trees.get((key, version))
        if found is None:
            found = self._parse(key, version)
            self._trees[(key, version)] = found
        return found

    def _parse(self, key: str, version: str) -> ProvisionTree | str:
        try:
            fetched = self._client.fetch_formex(Celex.parse(key), VersionId(version))
        except (FixtureMissing, OSError, LookupError) as error:
            return f"not cached ({type(error).__name__})"
        if not isinstance(fetched, FormexPackage):
            return f"no readable text ({fetched.state})"
        return parse_act(fetched).tree


def _text(tree: ProvisionTree | str, location: ProvisionLocation) -> str | None:
    """The verbatim text today's tree carries at `location`, or `None` for no answer at all."""
    if isinstance(tree, str):
        return None
    node = tree.find(location)
    return None if node is None else str(node.text)


def _derived(entry: ChangelogEntry, trees: Trees) -> dict[ChangeKey, str | None]:
    """Today's evidence digest per change, `None` where today's text could not be produced.

    The before side is looked up under the location the provision had, which is its own for
    everything but a renumbering, and the after side under the location it has now. A side the
    change does not carry stays absent, so a deletion is not compared against a text some later
    version happens to hold at that number.
    """
    before = trees.of(entry.act.key, str(entry.from_version))
    after = trees.of(entry.act.key, str(entry.to_version))
    answers: dict[ChangeKey, str | None] = {}
    changes = [item.change for item in entry.changes]
    for key, change in zip(keys_of(changes), changes, strict=True):
        if change.textless:
            answers[key] = digest_of_texts(change.location.canonical, None, None)
            continue
        was = change.previous_location or change.location
        today_before = None if change.before is None else _text(before, was)
        today_after = None if change.after is None else _text(after, change.location)
        if (change.before is not None and today_before is None) or (
            change.after is not None and today_after is None
        ):
            answers[key] = None
            continue
        answers[key] = digest_of_texts(change.location.canonical, today_before, today_after)
    return answers


def _why(entry: ChangelogEntry, trees: Trees) -> str:
    """Why a transition could not be re-derived, from whichever side answered with a reason."""
    for version in (entry.from_version, entry.to_version):
        found = trees.of(entry.act.key, str(version))
        if isinstance(found, str):
            return found
    return "the location is gone from today's tree"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="a clone of the published changelog corpus")
    parser.add_argument("--fetch", action="store_true", help="allow network for uncached packages")
    parser.add_argument("--verbose", action="store_true", help="print every transition that moves")
    args = parser.parse_args()

    root = default_cache_dir() / "cellar"
    cache = DiskResponseCache(root) if args.fetch else OfflineDiskCache(root)
    http = CellarHttp(cache=cache)
    trees = Trees(CellarClient(http, observed_on=OBSERVED_ON))

    cap = ExplainSettings().text_char_cap
    states: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    events = witnessed = unknown = textless = differing_events = 0
    differing_chars = differing_prompt_chars = 0
    moved_lines: list[str] = []
    for path in sorted(args.corpus.glob("eu/*/changes/*.json")):
        entry = ChangelogEntry.model_validate_json(path.read_bytes())
        events += 1
        changes = [item.change for item in entry.changes]
        textless += sum(1 for change in changes if change.textless)
        recorded = recorded_digests(entry.evidence)
        witnessed += sum(1 for key in keys_of(changes) if key in recorded)
        unknown += sum(1 for key in keys_of(changes) if key not in recorded)
        answers = checked(changes, recorded=stated(entry), derived=_derived(entry, trees))
        states.update(answer.state.value for answer in answers)
        differs = [answer for answer in answers if answer.state is EvidenceState.DIFFERS]
        differing_chars += sum(answer.chars for answer in differs)
        keyed = dict(zip(keys_of(changes), changes, strict=True))
        for answer in differs:
            change = keyed[(answer.location, answer.occurrence)]
            differing_prompt_chars += sum(
                min(len(side), cap) for side in (change.before, change.after) if side is not None
            )
        reasons.update(
            _why(entry, trees) for answer in answers if answer.state is EvidenceState.UNDERIVABLE
        )
        if differs:
            differing_events += 1
            moved_lines.append(
                f"{path.parent.parent.name} {path.stem}  {len(differs)} of {len(answers)}: "
                f"{[answer.location for answer in differs]}"
            )
    http.close()

    print(f"\ncorpus                  {args.corpus}  {_revision(args.corpus)}")
    print(f"events                  {events}")
    print(f"changes                 {sum(states.values())}")
    print(f"  provenance recorded   {witnessed}")
    print(f"  provenance unknown    {unknown}")
    for state in (EvidenceState.MATCHES, EvidenceState.DIFFERS, EvidenceState.UNDERIVABLE):
        print(f"  {state.value:21s} {states[state.value]}")
    print(f"  of the matches, textless and so with no evidence either side  {textless}")
    print(f"transitions with a differing change               {differing_events}")
    print(f"characters of evidence on the differing changes   {differing_chars}")
    print(f"  of those, inside the {cap}-character prompt cap  {differing_prompt_chars}")
    for reason, count in sorted(reasons.items()):
        print(f"underivable because {reason:34s} {count}")
    print(f"network calls           {http.network_calls}")
    if args.verbose:
        for line in moved_lines:
            print(line)
    return 0


def _revision(corpus: Path) -> str:
    """The clone's own commit, so a reading is dated by the corpus it was taken over."""
    try:
        found = subprocess.run(
            ["git", "-C", str(corpus), "log", "-1", "--format=%h %ad", "--date=short"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "revision unknown"
    return found.stdout.strip()


if __name__ == "__main__":
    sys.exit(main())
