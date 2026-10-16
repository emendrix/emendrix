#!/usr/bin/env python
"""Whether the amending act that made a change prints the table entries the row diff says moved.

One-off validation code, kept so the agreement between two readings of one change is a
reproducible artifact rather than an assertion. `substance_tables.py` reads the rows of every
annex table that carries CAS, EC or Index numbers and diffs them by key between two consolidated
versions. That diff is a reading of the consolidation. The amending act is the other reading: a
CLP adaptation to technical progress, a REACH Annex XVII restriction regulation or a Cosmetics
annex amendment prints the rows it inserts or replaces as a table of its own. This script asks,
per published change of the six acts whose unit holds such a table:

    when the consolidated row diff says entry K was added or amended, does an amending act the
    change names print entry K?

**Population.** Every change in a clone of the published changelog corpus whose unit holds one
of the profiled tables below. The consolidated row diff is taken between the change's own
`from_version` and `to_version`, both read from the disk cache through `substance_tables.py`,
whose row reader, grouping and diff this script imports rather than copies. Only the key is
chosen differently: each table is keyed by the column its profile names, as read off the markup
on 2026-10-16, never by the automatic choice, so a renumbered table is a counted gap.

**The amending acts.** The ones the change names (`change.amending_acts`); where it names none,
the ones the transition's metadata claims name, counted apart. Each is read through the project
client off the same cache, every table in every document of it (annex or article, quoted or not)
through the same row reader. Annex numbers are never mapped onto the consolidated ones: the
match is on row keys only, recognised by the profile's key form:

- `index` (CLP Index No): any Index-shaped token in a table cell of the amending act;
- `number` (an entry or reference number): the leading number of a row's first non-empty cell;
- `cas`: any CAS-shaped token in a table cell;
- `text` (a name, or an EC number used as a key): a cell whose text is the key.

A match is **exact** when the key is printed as the consolidation prints it, and **by notation**
when it matches only once case, quotes, hyphen forms and footnote markers such as `(#)` or `(+)`
are set aside. Both count as printed; the second is reported because a key that changes with its
footnote marker is a profile question.

**Classes.** A consolidated `added` or `amended` key is **printed** when a named amending act
prints it in a table row; **named in prose** when no table row carries it but the act's text
outside its tables names it (the shape "in entry K, ... is replaced by"); **not printed** when
every named act was read and none does either; **no amending act readable** when none is named,
one of them does not answer with an English Formex package, or none holds a table and none names
the key. A key a named act prints that the consolidated diff did not move, and that the newer
version holds in the same unit, is **printed but unmoved**. Keys whose cells changed in
whitespace alone are counted apart and never enter the agreement, which is
(printed + named in prose) / (printed + named in prose + not printed).

**Causes.** Each disagreement is given the first cause that applies, read deterministically:

- **typography only**: the entry's cells are the same once spaces, dash forms and accents are
  set aside (`Eye Dam. ;` against `Eye Dam.;`, an empty cell's hyphen against an em dash), so a
  re-typesetting moved the row and no act did;
- **identifier under another key**: a CAS or EC number of the consolidated entry sits in a
  named act's table under another key, as when a Cosmetics act prints a new row numbered `x`
  that the consolidation numbers itself (weak where an act prints many identifiers);
- **folded, not named**: an act the newer consolidation lists among its modifiers, the older
  one does not, and the change does not name, prints or names the key;
- **earlier modifier**: an act both consolidations list prints or names the key; whether an
  instruction of it took effect later or the consolidation corrected itself is not told apart;
- **only a whole-table reprint**: the two causes above leave out an act that prints at least
  half the keys of the consolidated table, since such an act prints nearly every key, and this
  is a key only such an act prints;
- **corrigendum in the window**: the newer consolidation lists a corrigendum the older one does
  not;
- **unclassified**: what a person reads, to classify the cause and never to label the law.

Modifier and corrigendum lists are read from each consolidated package's own `MOD.ACT` and
`CORRIG` elements; a listed CELEX number the identifier grammar does not accept is set aside and
printed.

**What a figure does not mean.** Agreement is about keys, not about content: a printed key whose
row the consolidation transcribed differently would still agree. A `number` key printed for one
annex matches the same number in another annex of the same act, so agreement on Cosmetics and
REACH Annex XVII is an upper bound and `printed but unmoved` there is inflated by the same cause.

It writes nothing, calls no model and spends nothing. Offline by default: an amending act the
disk cache does not hold is counted, and only `--fetch` reaches the network, through the
project's own client with its polite delay.

Usage, from the repository root::

    git clone https://github.com/emendrix/changelogs <somewhere>
    uv run python scripts/validation/substance_crosscheck.py <somewhere>
    uv run python scripts/validation/substance_crosscheck.py <somewhere> --act 32008R1272 --verbose
    uv run python scripts/validation/substance_crosscheck.py <somewhere> --fetch
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import Element

import substance_tables as tables

from emendrix.eu.cache import DiskResponseCache, FixtureMissing, default_cache_dir
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex.documents import act_documents, documents_of
from emendrix.eu.formex.model import CoverageCounter
from emendrix.eu.formex.text import verbatim_text
from emendrix.eu.http import CellarHttp
from emendrix.eu.identifiers import Celex
from emendrix.eu.packages import FormexPackage
from emendrix.eu.xml_ import NOT_WELL_FORMED, fromstring

OBSERVED_ON = date(2026, 10, 16)
"""Passed in rather than read from a clock, exactly as the CLI boundary passes it."""

SHOWN = 20
"""Disagreements printed per act without `--verbose`."""


@dataclass(frozen=True)
class Profile:
    """Which column numbers a table's rows, and how its key is read; verified 2026-10-16."""

    unit: str
    container: str
    table: int
    key_col: int
    form: str


def _profiles() -> dict[str, list[Profile]]:
    reach = [
        Profile("AN IV", "AN IV", 1, 1, "text"),
        Profile("AN XIV", "AN XIV", 1, 1, "number"),
        Profile("AN XVII", "AN XVII", 1, 1, "number"),
        *[Profile("AN XVII", f"AN XVII APP {n}", 1, 2, "index") for n in (1, 2, 4, 5, 6)],
        Profile("AN XVII", "AN XVII APP 8", 1, 1, "number"),
        Profile("AN XVII", "AN XVII APP 12", 1, 2, "index"),
        Profile("AN XVII", "AN XVII APP 13", 1, 3, "cas"),
    ]
    return {
        "32006R1907": reach,
        "32008R1272": [Profile("AN VI", "AN VI SCT 3", n, 1, "index") for n in (1, 2)],
        "32009R1223": [
            Profile(unit, unit, 1, 1, "number")
            for unit in ("AN II", "AN III", "AN IV", "AN V", "AN VI")
        ],
        "32012R0528": [Profile("AN I", "AN I", 1, 2, "text")],
        "32012R0649": [Profile("AN I", "AN I", n, 1, "text") for n in (1, 2, 3)]
        + [Profile("AN V", "AN V", 1, 2, "text"), Profile("AN V", "AN V", 2, 1, "number")],
        "32019R1021": [Profile(unit, unit, 1, 1, "text") for unit in ("AN I", "AN IV")],
    }


PROFILES = _profiles()
"""The profiles `substance_tables.py` proposed for the six acts, keyed as proposed there."""

QUOTES = "".join(chr(code) for code in (0x2018, 0x2019, 0x201C, 0x201D, 0x27, 0x22))
STRIP = QUOTES + " .,;:"
MARKERS = re.compile(r"\s*\(\s*[#+*]+\s*\)|\s*\*+$")
"""Footnote markers a table prints after a name: `(#)`, `(+)`, `(*)`, `(**)`, a trailing `*`."""
PROSE_ENTRY = r"\b(?:entry|entries|reference numbers?|numbers?|points?)\b[^.;:]{0,80}?"


def exact(value: str) -> str:
    """A cell or key as printed, whitespace and surrounding quotes aside."""
    return tables.norm(value).strip(STRIP)


def loose(value: str) -> str:
    """A cell or key with case, hyphen forms, quotes and footnote markers set aside too."""
    return MARKERS.sub("", exact(value).translate(tables.HYPHENS)).strip(STRIP).casefold()


# --------------------------------------------------------------------------- consolidated side


@dataclass
class Keyed:
    """One consolidated version: profiled tables keyed by profile, and the acts it lists."""

    analyses: dict[tuple[str, str, int], tables.Analysis]
    missing: list[Profile]
    modifiers: frozenset[str]
    corrigenda: frozenset[str]
    malformed: frozenset[str]


def keyed(cache: DiskResponseCache, item: tables.Cached, profiles: list[Profile]) -> Keyed | None:
    package = tables.load(cache, item)
    if package is None:
        return None
    found_tables, _, _ = tables.tables_of(package)
    by_identity = {table.identity: tables.analyse(table) for table in found_tables}
    found: dict[tuple[str, str, int], tables.Analysis] = {}
    missing: list[Profile] = []
    for profile in profiles:
        identity = (profile.unit, profile.container, profile.table)
        analysis = by_identity.get(identity)
        if analysis is None or analysis.table.width < profile.key_col or not analysis.body:
            missing.append(profile)
            continue
        analysis.key, analysis.form = profile.key_col - 1, profile.form
        analysis.entries, analysis.unkeyed, analysis.duplicates = {}, [], []
        tables.group(analysis)
        found[identity] = analysis
    modifiers, corrigenda = listed_acts(package)
    malformed = frozenset(key for key in modifiers if not parses(key))
    return Keyed(found, missing, modifiers - malformed, corrigenda, malformed)


def parses(key: str) -> bool:
    try:
        Celex.parse(key)
    except ValueError:
        return False
    return True


def listed_acts(package: FormexPackage) -> tuple[frozenset[str], frozenset[str]]:
    """The CELEX numbers a consolidated version lists as its modifiers and its corrigenda."""
    modifiers: set[str] = set()
    corrigenda: set[str] = set()
    for member in package.xml_members:
        try:
            root = fromstring(member.data)
        except NOT_WELL_FORMED:
            continue
        for tag, into in (("MOD.ACT", modifiers), ("CORRIG", corrigenda)):
            for element in root.iter(tag):
                celex = element.find(".//NO.CELEX")
                if celex is not None and celex.text:
                    into.add(celex.text.strip())
    return frozenset(modifiers), frozenset(corrigenda)


# --------------------------------------------------------------------------- amending side


@dataclass
class Printed:
    """What one amending act prints, read per key form, and its text outside its tables."""

    tables: int = 0
    rows: int = 0
    exact: dict[str, set[str]] = field(default_factory=dict)
    loose: dict[str, set[str]] = field(default_factory=dict)
    cas: set[str] = field(default_factory=set)
    ec: set[str] = field(default_factory=set)
    prose: str = ""

    def add(self, form: str, value: str) -> None:
        self.exact.setdefault(form, set()).add(exact(value))
        self.loose.setdefault(form, set()).add(loose(value))

    def prints(self, key: str, form: str) -> str | None:
        """`exact`, `notation`, or `None` when no table row of the act carries the key."""
        if exact(key) in self.exact.get(form, set()):
            return "exact"
        if loose(key) in self.loose.get(form, set()):
            return "notation"
        return None

    def names(self, key: str, form: str) -> bool:
        if form == "number":
            pattern = PROSE_ENTRY + rf"(?<![\w-]){re.escape(key)}(?![\w-])"
            return re.search(pattern, self.prose, re.IGNORECASE) is not None
        if form == "text":
            return loose(key) in self.prose.casefold()
        found = re.search(rf"(?<![\w-]){re.escape(key)}(?![\w-])", self.prose, re.IGNORECASE)
        return found is not None


def read_printed(package: FormexPackage) -> Printed:
    """Every table row of every document of one amending act, and its text outside tables."""
    printed = Printed()
    prose: list[str] = []
    for document in documents_of(act_documents(package, CoverageCounter())):
        prose.append(tables.norm(verbatim_text(without_tables(document))).translate(tables.HYPHENS))
        for tbl in tables._outer_tables(document):
            read_rows(printed, tables.read_table(tbl, "", "", 0, ""))
    printed.prose = "\n".join(prose)
    return printed


def read_rows(printed: Printed, table: tables.Table) -> None:
    printed.tables += 1
    for row in table.rows:
        if row.header:
            continue
        printed.rows += 1
        first = True
        for text, mark in zip(row.cells, row.marks, strict=True):
            if mark != "":
                continue
            plain = tables.norm(text).translate(tables.HYPHENS)
            for match in tables.INDEX.finditer(plain):
                printed.add("index", match[0])
            for match in tables.CAS.finditer(plain):
                printed.add("cas", match[0])
                printed.cas.add(match[0])
            printed.ec.update(match[0] for match in tables.EC.finditer(plain))
            stripped = plain.strip(STRIP)
            if not stripped:
                continue
            printed.add("text", stripped)
            if first:
                first = False
                lead = tables.NUMBER_LEAD.match(plain.lstrip(QUOTES + " "))
                if lead is not None:
                    printed.add("number", lead[1])


def without_tables(document: Element) -> Element:
    copy = deepcopy(document)
    for parent in list(copy.iter()):
        for child in list(parent):
            if child.tag == "TBL":
                parent.remove(child)
    return copy


class Amending:
    """Amending acts read once each, through the project client, off the shared cache."""

    def __init__(self, client: CellarClient) -> None:
        self.client = client
        self.read: dict[str, Printed | str] = {}

    def get(self, key: str) -> Printed | str:
        if key not in self.read:
            self.read[key] = self._read(key)
        return self.read[key]

    def _read(self, key: str) -> Printed | str:
        try:
            celex = Celex.parse(key)
            fetched = self.client.fetch_formex(celex, celex.version, allow_original_fallback=False)
        except FixtureMissing:
            return "not cached"
        except (OSError, LookupError, ValueError) as error:
            return f"unreadable ({type(error).__name__})"
        if not isinstance(fetched, FormexPackage):
            return f"no English Formex ({type(fetched).__name__})"
        return read_printed(fetched)


# --------------------------------------------------------------------------- the classification


CLASSES = ("printed", "named in prose", "not printed", "no amending act readable")
CAUSES = (
    "typography only",
    "identifier under another key",
    "folded, not named",
    "earlier modifier",
    "only a whole-table reprint",
    "corrigendum in the window",
    "unclassified",
)


@dataclass
class Tally:
    """Counts for one act, or for all six."""

    classes: Counter[str] = field(default_factory=Counter)
    kinds: Counter[tuple[str, str]] = field(default_factory=Counter)
    notation: int = 0
    spacing: Counter[str] = field(default_factory=Counter)
    unreadable: Counter[str] = field(default_factory=Counter)
    causes: Counter[str] = field(default_factory=Counter)
    unmoved: int = 0
    unmoved_by: Counter[str] = field(default_factory=Counter)
    changes: Counter[str] = field(default_factory=Counter)
    removed: int = 0
    removed_named: int = 0
    sources: Counter[str] = field(default_factory=Counter)
    folded_changes: int = 0
    amending: Counter[str] = field(default_factory=Counter)

    def add(self, other: Tally) -> None:
        for name in ("classes", "kinds", "spacing", "unreadable", "causes", "changes", "sources"):
            getattr(self, name).update(getattr(other, name))
        self.amending.update(other.amending)
        for name in ("notation", "unmoved", "removed", "removed_named", "folded_changes"):
            setattr(self, name, getattr(self, name) + getattr(other, name))

    @property
    def agreement(self) -> tuple[int, int]:
        agree = self.classes["printed"] + self.classes["named in prose"]
        return agree, agree + self.classes["not printed"]


@dataclass(frozen=True)
class Disagreement:
    """One consolidated key no named amending act prints."""

    old: str
    new: str
    container: str
    table: int
    kind: str
    key: str
    amending: tuple[str, ...]
    cause: str
    folded: tuple[str, ...]

    def line(self) -> str:
        where = f"{self.container} #{self.table}"
        also = f": {', '.join(self.folded)}" if self.folded else ""
        return (
            f"    {self.old} -> {self.new} {where} {self.kind} {tables.show(self.key, 60)}  "
            f"by {', '.join(self.amending)}  [{self.cause}{also}]"
        )


@dataclass
class Event:
    """One published payload: its versions and, per unit, the amending acts named."""

    old: str
    new: str
    units: dict[str, tuple[tuple[str, ...], str]]


def events(record: Path, act: str) -> list[Event]:
    found: list[Event] = []
    for path in sorted((record / "eu" / act / "changes").glob("*.json")):
        payload = json.loads(path.read_text())
        signals = {item["signal"]: item for item in payload["corroboration"]["signals"]}
        metadata = tuple(
            sorted(
                {
                    str(claim["amending_act"]["key"])
                    for claim in signals["corpus_metadata"]["claims"]
                    if claim.get("amending_act")
                }
            )
        )
        units: dict[str, tuple[tuple[str, ...], str]] = {}
        for one in payload["changes"]:
            change = one["change"]
            unit = str(change["provision"]["location"])
            named = tuple(sorted(str(item["key"]) for item in change["amending_acts"]))
            if named:
                units[unit] = (named, "the change")
            elif metadata:
                units[unit] = (metadata, "the transition's metadata")
            else:
                units[unit] = ((), "none")
        found.append(Event(str(payload["from_version"]), str(payload["to_version"]), units))
    return found


@dataclass
class Context:
    """What one change is checked against: its named acts, read, and the window's other acts."""

    named: tuple[str, ...]
    printed: list[Printed]
    reasons: list[str]
    folded: Callable[[], dict[str, Printed]]
    earlier: Callable[[], dict[str, Printed]]
    corrigendum: bool

    def prints(self, key: str, form: str) -> str | None:
        found = [one.prints(key, form) for one in self.printed]
        return "exact" if "exact" in found else ("notation" if "notation" in found else None)

    def classify(self, key: str, form: str, tally: Tally) -> str:
        how = self.prints(key, form)
        if how is not None:
            tally.notation += how == "notation"
            return "printed"
        if any(one.names(key, form) for one in self.printed):
            return "named in prose"
        if self.reasons:
            tally.unreadable[self.reasons[0]] += 1
            return "no amending act readable"
        if not self.printed:
            tally.unreadable["none named"] += 1
            return "no amending act readable"
        if not any(one.tables for one in self.printed):
            tally.unreadable["no table in any named act"] += 1
            return "no amending act readable"
        return "not printed"

    def cause(
        self, key: str, form: str, old: tables.Analysis | None, new: tables.Analysis | None
    ) -> tuple[str, tuple[str, ...]]:
        if old is not None and new is not None and same_but_typography(old, new, key):
            return "typography only", ()
        if new is not None and key in new.entries:
            for value in new.identifiers(key):
                scheme, number = value.split(":", 1)
                if any(number in (one.cas if scheme == "cas" else one.ec) for one in self.printed):
                    return "identifier under another key", ()
        others = {**self.earlier(), **self.folded()}
        whole = {act_key for act_key, one in others.items() if new and reprints(one, new)}
        for name, group in (("folded, not named", self.folded), ("earlier modifier", self.earlier)):
            found = tuple(
                act_key
                for act_key, one in sorted(group().items())
                if act_key not in whole and (one.prints(key, form) or one.names(key, form))
            )
            if found:
                return name, found
        found = tuple(sorted(act_key for act_key in whole if others[act_key].prints(key, form)))
        if found:
            return "only a whole-table reprint", found
        if self.corrigendum:
            return "corrigendum in the window", ()
        return "unclassified", ()


def reprints(one: Printed, table: tables.Analysis) -> bool:
    """Whether an act prints at least half the keys a consolidated table holds."""
    keys = list(table.entries)
    return bool(keys) and 2 * sum(1 for key in keys if one.prints(key, table.form)) >= len(keys)


DASHES = str.maketrans(
    {chr(code): "-" for code in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2212)}
)


def same_but_typography(old: tables.Analysis, new: tables.Analysis, key: str) -> bool:
    """Whether an entry's cells are the same once spaces, dash forms and accents are set aside."""

    def squeezed(analysis: tables.Analysis) -> list[str]:
        cells = (cell for row in analysis.entries.get(key, []) for cell in row.cells)
        return [plain(cell) for cell in cells]

    return squeezed(old) == squeezed(new)


def plain(cell: str) -> str:
    decomposed = unicodedata.normalize("NFKD", tables.norm(cell).translate(DASHES))
    return "".join(
        char for char in decomposed if not char.isspace() and not unicodedata.combining(char)
    )


def context(named: tuple[str, ...], before: Keyed, after: Keyed, amending: Amending) -> Context:
    read = {key: amending.get(key) for key in named}
    printed = [one for one in read.values() if isinstance(one, Printed)]
    reasons = sorted({one for one in read.values() if isinstance(one, str)})

    def readable(keys: frozenset[str]) -> Callable[[], dict[str, Printed]]:
        def read_them() -> dict[str, Printed]:
            found = {key: amending.get(key) for key in sorted(keys - set(named))}
            return {key: one for key, one in found.items() if isinstance(one, Printed)}

        return read_them

    folded = readable(after.modifiers - before.modifiers)
    earlier = readable(after.modifiers & before.modifiers)
    corrigendum = bool(after.corrigenda - before.corrigenda)
    return Context(named, printed, reasons, folded, earlier, corrigendum)


def check_change(
    event: Event,
    unit: str,
    before: Keyed,
    after: Keyed,
    amending: Amending,
    tally: Tally,
    disagreements: list[Disagreement],
) -> None:
    named, source = event.units[unit]
    tally.sources[source] += 1
    tally.amending.update(named)
    found = context(named, before, after, amending)
    tally.folded_changes += bool(after.modifiers - before.modifiers - set(named))
    identities = sorted(
        {identity for identity in (*before.analyses, *after.analyses) if identity[0] == unit}
    )
    moved_any = False
    moved_keys: set[str] = set()
    unchanged: dict[str, str] = {}
    for identity in identities:
        old, new = before.analyses.get(identity), after.analyses.get(identity)
        either = new if new is not None else old
        form = either.form if either is not None else "text"
        moved = tables.diff(old, new)
        moved_any = moved_any or bool(moved.moved)
        for key in moved.spacing:
            tally.spacing["keys"] += 1
            tally.spacing["printed"] += found.prints(key, form) is not None
        tally.removed += len(moved.removed)
        tally.removed_named += sum(
            1
            for key in moved.removed
            if found.prints(key, form) or any(one.names(key, form) for one in found.printed)
        )
        for kind, keys in (("added", moved.added), ("amended", moved.amended)):
            for key in keys:
                moved_keys.add(key)
                label = found.classify(key, form, tally)
                tally.classes[label] += 1
                tally.kinds[(kind, label)] += 1
                if label != "not printed":
                    continue
                cause, folded = found.cause(key, form, old, new)
                tally.causes[cause] += 1
                disagreements.append(
                    Disagreement(
                        event.old,
                        event.new,
                        identity[1],
                        identity[2],
                        kind,
                        key,
                        named,
                        cause,
                        folded,
                    )
                )
        if new is not None:
            for key in new.entries:
                if key not in moved.added and key not in moved.amended:
                    unchanged[key] = form
    unmoved = sum(
        1
        for key, form in unchanged.items()
        if key not in moved_keys and found.prints(key, form) is not None
    )
    tally.unmoved += unmoved
    if unmoved:
        tally.unmoved_by[f"{event.old} -> {event.new} {unit} by {', '.join(named)}"] = unmoved
    tally.changes["rows moved" if moved_any else "no row moved"] += 1


# --------------------------------------------------------------------------- per act


def check_act(
    act: str, record: Path, cache: DiskResponseCache, amending: Amending, verbose: bool
) -> Tally:
    profiles = PROFILES[act]
    units = {profile.unit for profile in profiles}
    items = {item.version: item for item in tables.cached_packages(cache.root).get(act, [])}
    read: dict[str, Keyed | None] = {}

    def version(name: str) -> Keyed | None:
        if name not in read:
            item = items.get(name)
            read[name] = None if item is None else keyed(cache, item, profiles)
        return read[name]

    tally = Tally()
    disagreements: list[Disagreement] = []
    unread: Counter[str] = Counter()
    for event in events(record, act):
        for unit in sorted(event.units):
            if unit not in units:
                continue
            before, after = version(event.old), version(event.new)
            if before is None or after is None:
                missing = [one for one, got in ((event.old, before), (event.new, after)) if not got]
                unread[f"version not readable from the cache: {', '.join(missing)}"] += 1
                continue
            if not any(identity[0] == unit for identity in (*before.analyses, *after.analyses)):
                unread["no profiled table in the unit in either version"] += 1
                continue
            check_change(event, unit, before, after, amending, tally, disagreements)
    report(act, tally, unread, disagreements, amending, verbose)
    absent = Counter(
        f"{profile.container} #{profile.table}"
        for one in read.values()
        if one is not None
        for profile in one.missing
    )
    if absent:
        print(
            "  profiled tables absent from a version read here (versions): "
            + ", ".join(f"{name} {count}" for name, count in sorted(absent.items()))
            + "\n"
        )
    malformed = sorted({key for one in read.values() if one is not None for key in one.malformed})
    if malformed:
        print(f"  modifier CELEX numbers the grammar refuses, set aside: {', '.join(malformed)}\n")
    return tally


def rate(pair: tuple[int, int]) -> str:
    agree, total = pair
    return f"{agree}/{total} ({agree / total:.3f})" if total else f"{agree}/0 (n/a)"


def report(
    act: str,
    tally: Tally,
    unread: Counter[str],
    disagreements: list[Disagreement],
    amending: Amending,
    verbose: bool,
) -> None:
    print(f"== {act} {tables.SIX_ACTS.get(act, '')}".rstrip())
    checked = sum(tally.changes.values())
    print(
        f"  published changes checked {checked} (rows moved {tally.changes['rows moved']}, "
        f"none {tally.changes['no row moved']}); not checked {sum(unread.values())}"
    )
    for reason, count in sorted(unread.items()):
        print(f"    not checked, {reason}: {count}")
    print(
        "  amending acts named by "
        + ", ".join(f"{name}: {count}" for name, count in sorted(tally.sources.items()))
    )
    print(f"  changes whose window folds an act they do not name: {tally.folded_changes}")
    states = Counter(
        "read" if isinstance(amending.read.get(key), Printed) else str(amending.read.get(key))
        for key in tally.amending
    )
    print(
        f"  distinct amending acts named {len(tally.amending)}: "
        + ", ".join(f"{name} {count}" for name, count in sorted(states.items()))
    )
    for key in sorted(tally.amending):
        state = amending.read.get(key)
        if not isinstance(state, Printed):
            print(f"    {key}: {state}")
    print_tally(tally)
    for where, count in tally.unmoved_by.most_common(5):
        print(f"    printed but unmoved {count:5d}: {where}")
    print(f"  disagreements {len(disagreements)}:")
    for one in disagreements[: None if verbose else SHOWN]:
        print(one.line())
    if not verbose and len(disagreements) > SHOWN:
        print(f"    ... and {len(disagreements) - SHOWN} more (--verbose prints every one)")
    print()


def print_tally(tally: Tally) -> None:
    for name in CLASSES:
        added = tally.kinds[("added", name)]
        amended = tally.kinds[("amended", name)]
        print(f"    {name:26s} {tally.classes[name]:6d}  (added {added}, amended {amended})")
        if name == "printed":
            print(f"      of which matched by notation only: {tally.notation}")
        if name == "not printed":
            for cause in CAUSES:
                print(f"      cause, {cause}: {tally.causes[cause]}")
    for reason, count in sorted(tally.unreadable.items()):
        print(f"      no amending act readable, {reason}: {count}")
    print(f"    agreement (printed + named in prose) / checked keys: {rate(tally.agreement)}")
    print(f"    printed but unmoved (key unchanged in the newer version): {tally.unmoved}")
    print(
        f"    whitespace-only keys, apart: {tally.spacing['keys']} "
        f"(of which printed {tally.spacing['printed']})"
    )
    print(f"    removed keys: {tally.removed} (printed or named {tally.removed_named})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("record", type=Path, help="a clone of the published changelog corpus")
    parser.add_argument("--act", action="append", help="CELEX; repeatable; default all six")
    parser.add_argument("--fetch", action="store_true", help="allow network for amending acts")
    parser.add_argument("--verbose", action="store_true", help="print every disagreement")
    args = parser.parse_args()

    root = default_cache_dir() / "cellar"
    cache = DiskResponseCache(root) if args.fetch else tables.OfflineDiskCache(root)
    http = CellarHttp(cache=cache)
    amending = Amending(CellarClient(http, observed_on=OBSERVED_ON))
    acts = args.act or list(PROFILES)
    unknown = [act for act in acts if act not in PROFILES]
    if unknown:
        print(f"no profile: {', '.join(unknown)}", file=sys.stderr)
        return 1
    print(f"read on {OBSERVED_ON} over the disk cache at {tables.shown_path(root)}")
    print(f"published record {revision(args.record)}\n")
    total = Tally()
    for act in acts:
        offline = tables.OfflineDiskCache(root)
        total.add(check_act(act, args.record, offline, amending, args.verbose))
    http.close()
    print("== total")
    print_tally(total)
    print(f"  network calls {http.network_calls}")
    return 0


def revision(record: Path) -> str:
    """The clone's own commit, so a reading is dated by the corpus it was taken over."""
    found = subprocess.run(
        ["git", "-C", str(record), "log", "-1", "--format=%h %cs"],
        capture_output=True,
        text=True,
        check=False,
    )
    return found.stdout.strip() or "(no git answer)"


if __name__ == "__main__":
    sys.exit(main())
