#!/usr/bin/env python
"""How often an amending act says when its instructions take effect.

One-off validation code, kept so the coverage number behind `eu/instructions/effect.py` is a
reproducible artifact rather than an assertion. Unlike `trace.py` it imports the package
instead of reimplementing it, because the thing being measured *is* the package: it reads the
same `CellarClient`, the same disk cache and the same parser the loop uses, and reports what
the five-tier read reached over a set of real amending acts.

It writes nothing, calls no model and spends nothing. It is offline by default: the cache
answers or the act is reported as not cached, and there is no path from a miss to a socket
unless `--fetch` is passed.

Usage, from the repository root::

    uv run python scripts/validation/instruction_effect_dates.py
    uv run python scripts/validation/instruction_effect_dates.py --fetch
    uv run python scripts/validation/instruction_effect_dates.py 32019R2033 32024R1860
    uv run python scripts/validation/instruction_effect_dates.py --verbose 32019R2033
    uv run python scripts/validation/instruction_effect_dates.py --markup 32021R2117

`--markup` prints the act's final-provisions articles as the package holds them, one element
per line, and reads nothing else. It is how a statement shape gets into `tests/fixtures/eu/`
without being retyped: the file committed there is this command's output, redirected.

With no act named the population is every act whose tree notice the disk cache already holds,
which is the set this machine has fetched through the loop, the eval corpus and the repair
passes. An act that yields no instruction record is not an amending act and is counted apart.

The dates the act's own notice publishes are read through `eu/signals.py`, the same
composition root the loop reads them in, so this measures the tier order that ships rather
than a copy of it. The two counts under the tiers are what the notice could not place: an act
with a staged date, and an act with an implausible value such as the `1001-01-01` the corpus
writes for a day a later decision will fix.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import tostring

from emendrix.eu.cache import DiskResponseCache, FixtureMissing, default_cache_dir
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex.documents import act_documents, documents_of, unit_elements
from emendrix.eu.formex.model import CoverageCounter
from emendrix.eu.http import CellarHttp
from emendrix.eu.identifiers import Celex
from emendrix.eu.instructions import (
    ActDates,
    EffectDateSource,
    InstructionParse,
    parse_instructions,
)
from emendrix.eu.instructions.effect import prose
from emendrix.eu.instructions.final_provisions import FINAL_PROVISIONS
from emendrix.eu.packages import FormexPackage
from emendrix.eu.signals import act_dates

CELEX_URL = re.compile(r"/resource/celex/(3\d{4}[A-Z]\d{4})$")
OBSERVED_ON = date(2026, 9, 5)
"""Passed in rather than read from a clock, exactly as the CLI boundary passes it."""


class OfflineDiskCache(DiskResponseCache):
    """The shared disk cache, refusing to fall through to the network."""

    @property
    def offline(self) -> bool:
        return True


def cached_acts(root: Path) -> list[str]:
    """Every original-act CELEX whose tree notice is in the disk cache, in CELEX order."""
    found: set[str] = set()
    for sidecar in root.rglob("*.json"):
        entry = json.loads(sidecar.read_text())
        if entry.get("status_code") != 200:
            continue
        if not str(entry.get("accept") or "").startswith("application/xml;notice=tree"):
            continue
        matched = CELEX_URL.search(str(entry.get("url") or ""))
        if matched is not None:
            found.add(matched.group(1))
    return sorted(found)


def markup(client: CellarClient, key: str) -> int:
    """Print the act's final-provisions articles as the package holds them, and nothing else."""
    celex = Celex.parse(key)
    fetched = client.fetch_formex(celex, celex.version, allow_original_fallback=False)
    if not isinstance(fetched, FormexPackage):
        print(f"{key}: no readable text ({fetched.state})", file=sys.stderr)
        return 1
    documents = act_documents(fetched, CoverageCounter())
    for document in documents_of(documents):
        for unit, is_annex in unit_elements(document):
            if not is_annex and FINAL_PROVISIONS.search(prose(unit)):
                print(tostring(unit, encoding="unicode"))
    return 0


def read(client: CellarClient, key: str) -> tuple[InstructionParse, ActDates] | str:
    """The instruction parse of one act and the dates its notice publishes, or why there is none.

    A package the cache does not hold is a result to count, not a failure: offline, that is what
    the refusal to reach the network says. Anything else is left to raise.
    """
    celex = Celex.parse(key)
    try:
        fetched = client.fetch_formex(celex, celex.version, allow_original_fallback=False)
        dates = act_dates(client, celex)
    except (FixtureMissing, OSError) as error:
        return f"not cached ({type(error).__name__})"
    if not isinstance(fetched, FormexPackage):
        return f"no readable text ({fetched.state})"
    return parse_instructions(fetched, dates=dates), dates


def report(key: str, parse: InstructionParse, *, verbose: bool) -> Counter[str]:
    """One act's line, and its records by which answer dated them."""
    tiers = Counter(str(record.effect_source) for record in parse.records)
    dates = {record.effect_date for record in parse.records if record.effect_date is not None}
    print(
        f"{key}  records {parse.matched:4d}  dated {parse.dated:4d} "
        f"({parse.effect_date_coverage:.3f})  "
        + "  ".join(f"{name} {count}" for name, count in sorted(tiers.items()))
        + ("  dates " + ", ".join(sorted(str(one) for one in dates)) if dates else "")
    )
    if verbose:
        for record in parse.records:
            print(
                f"    {record.source_ref:24s} {record.location.canonical:28s} "
                f"{record.effect_date or '-'!s:12s} {record.effect_source}"
            )
    return tiers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("acts", nargs="*", help="CELEX identifiers; default: every cached act")
    parser.add_argument("--fetch", action="store_true", help="allow network for uncached packages")
    parser.add_argument("--verbose", action="store_true", help="print every record")
    parser.add_argument(
        "--markup", action="store_true", help="print the final-provisions articles and stop"
    )
    args = parser.parse_args()

    root = default_cache_dir() / "cellar"
    keys = args.acts or cached_acts(root)
    cache = DiskResponseCache(root) if args.fetch else OfflineDiskCache(root)
    http = CellarHttp(cache=cache)
    client = CellarClient(http, observed_on=OBSERVED_ON)

    if args.markup:
        failed = sum(markup(client, key) for key in keys)
        http.close()
        return 1 if failed else 0

    tiers: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    amending = records = dated = 0
    acts_dated = acts_defaulted = 0
    staged_acts = staged_records = 0
    rejected_acts = rejected_values = 0
    for key in keys:
        found = read(client, key)
        if isinstance(found, str):
            skipped[found] += 1
            continue
        parse, dates = found
        if parse.matched == 0:
            skipped["no instruction record"] += 1
            continue
        amending += 1
        records += parse.matched
        dated += parse.dated
        acts_dated += 1 if parse.dated else 0
        acts_defaulted += (
            1
            if any(record.effect_source is EffectDateSource.ACT_DEFAULT for record in parse.records)
            else 0
        )
        if dates.unplaced:
            staged_acts += 1
            staged_records += parse.matched
        if dates.implausible:
            rejected_acts += 1
            rejected_values += len(dates.implausible)
        tiers += report(key, parse, verbose=args.verbose)
    http.close()

    print(f"\nacts asked            {len(keys)}")
    for reason, count in sorted(skipped.items()):
        print(f"  skipped, {reason:34s} {count}")
    print(f"amending acts read    {amending}")
    print(f"  with any dated record  {acts_dated}")
    print(f"  with a default date    {acts_defaulted}")
    print(f"instruction records   {records}")
    print(f"  dated                  {dated} ({dated / records if records else 1.0:.3f})")
    for name, count in sorted(tiers.items()):
        print(f"  {name:22s} {count} ({count / records if records else 0.0:.3f})")
    print(f"notice unplaced       {staged_acts} acts, {staged_records} records")
    print(f"notice implausible    {rejected_acts} acts, {rejected_values} values")
    print(f"network calls         {http.network_calls}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
