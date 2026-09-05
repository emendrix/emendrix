#!/usr/bin/env python
"""How many published instruction claims the consolidation window takes back.

One-off validation code, kept so the reach of the window scoping is a reproducible artifact
rather than an assertion. Two readings of this quantity were published on 2026-09-05, 85 of
1 309 claims across 13 events and 151 of 1 309 across 76, and neither could be reproduced
because neither script was committed. This is that script.

It reads a **clone of the published changelog corpus**, one JSON payload per event, and for
each one:

1. takes the window `(after, until]` from the payload's own `from_version` and `to_version`,
   a consolidated version identifier being `<celex>-<YYYYMMDD>`, and `None` for the lower
   bound where the earlier side is the act as published;
2. takes the amending act from the payload's own instruction claims, which is the one place a
   written event records which document the third signal read;
3. re-reads that act's instructions through the package the loop reads, off the same disk
   cache, and asks which of the claims the payload published the window would exclude today.

What is counted is **units no other signal named**: the top-level provisions this signal alone
claimed, which are exactly the ones the corroborator appends a change for, so withdrawing one
takes a row off a page. A unit the structural diff found or the annotations listed is
corroborated whatever this signal says, and a claim on it is not counted here. That is the
denominator both published readings were taken over, 1 309 over the corpus as it stood on
2026-08-14.

It writes nothing, calls no model and spends nothing. Offline by default: an act the disk
cache does not hold is counted as unresolved and reported, and there is no path from a miss to
a socket unless `--fetch` is passed.

Usage, from the repository root::

    git clone https://github.com/emendrix/changelogs <somewhere>
    uv run python scripts/validation/instruction_claim_scoping.py <somewhere>
    uv run python scripts/validation/instruction_claim_scoping.py <somewhere> --verbose

The corpus is a separate repository and is never committed here, so the reading is dated by
the commit of the clone it was taken over, which the script prints if `git` can answer.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from emendrix.core import ActId, ProvisionLocation
from emendrix.eu.cache import DiskResponseCache, FixtureMissing, default_cache_dir
from emendrix.eu.cellar import CellarClient
from emendrix.eu.http import CellarHttp
from emendrix.eu.identifiers import Celex
from emendrix.eu.instructions import InstructionParse, Window, parse_instructions
from emendrix.eu.packages import FormexPackage
from emendrix.eu.signals import act_dates

OBSERVED_ON = date(2026, 9, 5)
"""Passed in rather than read from a clock, exactly as the CLI boundary passes it."""


class OfflineDiskCache(DiskResponseCache):
    """The shared disk cache, refusing to fall through to the network."""

    @property
    def offline(self) -> bool:
        return True


def version_date(identifier: str) -> date | None:
    """`02017R0745-20240709` → the day. The act as published carries no day and answers `None`."""
    _, _, stamp = identifier.partition("-")
    if len(stamp) != 8 or not stamp.isdigit():
        return None
    return date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:]))


class Event:
    """One published payload, read for the three things this measurement needs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        payload = json.loads(path.read_text())
        self.act = ActId(corpus="eu", key=str(payload["act"]["key"]))
        self.window: Window | None = None
        until = version_date(str(payload["to_version"]))
        if until is not None:
            self.window = (version_date(str(payload["from_version"])), until)
        signals = {item["signal"]: item for item in payload["corroboration"]["signals"]}
        self.claims = tuple(signals["instruction_parse"]["claims"])
        self.named = {
            unit
            for name in ("structural_diff", "corpus_metadata")
            for unit in signals[name]["units"]
        }
        keys = {
            str(claim["amending_act"]["key"]) for claim in self.claims if claim.get("amending_act")
        }
        self.amending = keys.pop() if len(keys) == 1 else None

    @property
    def uncorroborated(self) -> tuple[str, ...]:
        """The units this signal alone claimed, in the order the payload lists them."""
        claimed = {
            ProvisionLocation.parse(str(claim["location"])).top_level.canonical: None
            for claim in self.claims
        }
        return tuple(unit for unit in claimed if unit not in self.named)


def parsed(client: CellarClient, key: str) -> InstructionParse | str:
    """One amending act's instructions, or why there are none to read."""
    celex = Celex.parse(key)
    try:
        fetched = client.fetch_formex(celex, celex.version, allow_original_fallback=False)
        dates = act_dates(client, celex)
    except (FixtureMissing, OSError, LookupError) as error:
        return f"not cached ({type(error).__name__})"
    if not isinstance(fetched, FormexPackage):
        return f"no readable text ({fetched.state})"
    return parse_instructions(fetched, dates=dates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="a clone of the published changelog corpus")
    parser.add_argument("--fetch", action="store_true", help="allow network for uncached packages")
    parser.add_argument("--verbose", action="store_true", help="print every event that moves")
    args = parser.parse_args()

    root = default_cache_dir() / "cellar"
    cache = DiskResponseCache(root) if args.fetch else OfflineDiskCache(root)
    http = CellarHttp(cache=cache)
    client = CellarClient(http, observed_on=OBSERVED_ON)

    parses: dict[str, InstructionParse | str] = {}
    skipped: Counter[str] = Counter()
    events = claims = uncorroborated = excluded = 0
    moved_events = 0
    for path in sorted(args.corpus.glob("eu/*/changes/*.json")):
        event = Event(path)
        events += 1
        claims += len(event.claims)
        held = event.uncorroborated
        uncorroborated += len(held)
        if event.amending is None or event.window is None:
            skipped["no single amending act" if event.window else "no dated window"] += 1
            continue
        found = parses.setdefault(event.amending, parsed(client, event.amending))
        if isinstance(found, str):
            skipped[found] += 1
            continue
        kept = {
            record.unit.canonical for record in found.in_window(event.act, event.window).records
        }
        gone = [unit for unit in held if unit not in kept]
        excluded += len(gone)
        if gone:
            moved_events += 1
            if args.verbose:
                print(f"{path.parent.parent.name} {path.stem}  {len(gone)} of {len(held)}: {gone}")
    http.close()

    print(f"\ncorpus                {args.corpus}  {_revision(args.corpus)}")
    print(f"events                {events}")
    for reason, count in sorted(skipped.items()):
        print(f"  unresolved, {reason:32s} {count}")
    print(f"instruction claims    {claims}")
    print(f"units no other signal named  {uncorroborated}")
    rate = excluded / uncorroborated if uncorroborated else 0.0
    print(f"excluded by the window {excluded} ({rate:.3f}) across {moved_events} events")
    print(f"network calls         {http.network_calls}")
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
