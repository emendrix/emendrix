#!/usr/bin/env python
"""Which tables in the cached Formex packages hold substance identifiers, and what their rows are.

One-off validation code, kept so the facts a table reader would be built on are a reproducible
artifact rather than an assertion. The parser reads a `TBL` as prose and never as rows: cells
join by a space and rows by a line break, so a stored annex text cannot be split back into the
rows the act prints. The markup still has them. This script reads the markup and answers, over
every consolidated English Formex package the disk cache holds:

1. which annex tables carry CAS numbers, EC numbers or CLP Index numbers, and in which columns;
2. which column numbers a table's rows, how unique that key is, and how many rows carry none;
3. how the keyed rows move between consecutive versions of one act;
4. how much a full list of one version's keyed rows, and one transition's row diff, would weigh.

**Method.** Packages are enumerated from the cache's sidecar files (status 200, a Formex 4 zip
in English), never by listing an act's versions, so the population is exactly what this
machine holds. Each package is opened with the package's own reader, its documents and units
are selected the way the parser selects them, and a table's container is named by the parser's
own placement function, so `AN VI SCT 3` here is the location the provision tree uses. A
table's grid is built from each cell's `COL` attribute, with `ROWSPAN` and `COLSPAN` tracked
per column rather than by position. A cell's text is `verbatim_text` of the `CELL` element.

**Identifiers.** A CAS number is `\\d{2,7}-\\d{2}-\\d` whose check digit is the sum of the
other digits weighted 1, 2, 3, ... from the right, modulo 10. An EC number is
`[2-9]\\d{2}-\\d{3}-\\d` whose check digit is the sum of its six digits weighted 1 to 6 from the
left, modulo 11; a sum giving 10 is not issued and is counted apart. A CLP Index number is
`\\d{3}-\\d{3}-\\d{2}-[\\dX]`; which rule, if any, its last character follows is measured here
over every value the cache holds rather than assumed. A value of the right shape with a wrong
check digit is counted and printed with its row, because it is a fact about the act.

**A key** is the column a table's rows are told apart by. It is chosen per table and version
from the cells alone: the column whose own values are most distinct relative to the number of
body rows, preferring an Index-shaped column, then a numbered one, then the leftmost. A row
whose key cell is a `ROWSPAN` copy continues the entry above it; a row whose key cell is empty
is counted as unkeyed; a key seen twice in one table is counted and never paired.

**What a figure does not mean.** A "substance table" is a table with at least three cells
holding a check-digit-valid CAS or EC number or an Index-shaped value: it is a statement about
markup, not about what the act regulates. A row with no identifier is not a row about no
substance (a group entry names a family, not a number). A row diff between two versions is a
naive keyed comparison of cell texts, not the change the amending act made. Figures are read
over the cache as it stood on the day of the run, which the results file names.

It writes nothing, calls no model and spends nothing. Offline by default: `--fetch` lets
`survey` list the six table-bearing acts' versions and fetch missing packages through the
project's own client, with its polite delay.

Usage, from the repository root::

    uv run python scripts/validation/substance_tables.py survey
    uv run python scripts/validation/substance_tables.py survey --act 32008R1272 --verbose
    uv run python scripts/validation/substance_tables.py survey --fetch
    uv run python scripts/validation/substance_tables.py transitions --act 32008R1272
    uv run python scripts/validation/substance_tables.py transitions --act 32008R1272 \\
        --record <changelogs clone>
    uv run python scripts/validation/substance_tables.py excerpt 32008R1272 \\
        02008R1272-20260701 "AN VI" --rows 40

`excerpt` prints one table as a well-formed XML fragment: the table's ancestors reduced to their
tags, attributes and the headings a location is read from, then the table with its header rows
and its first `--rows` body rows, every other row dropped. Same input, same bytes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import Element, tostring

from emendrix.core import (
    ActId,
    LocationSegment,
    ProvisionLocation,
    VersionId,
    normalize_for_comparison,
)
from emendrix.eu.cache import DiskResponseCache, FixtureMissing, default_cache_dir
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex.documents import act_documents, documents_of, unit_elements
from emendrix.eu.formex.locations import INLINE, annex_segment
from emendrix.eu.formex.model import CoverageCounter

# The walk's own placement, imported rather than copied, so a container here is the location
# the provision tree gives the same element.
from emendrix.eu.formex.parse import _placed, _Siblings
from emendrix.eu.formex.text import SKIPPED_SUBTREES, verbatim_text
from emendrix.eu.http import CellarHttp
from emendrix.eu.identifiers import Celex
from emendrix.eu.packages import FormexPackage

OBSERVED_ON = date(2026, 10, 16)
"""Passed in rather than read from a clock, exactly as the CLI boundary passes it."""

SIX_ACTS = {
    "32006R1907": "REACH",
    "32008R1272": "CLP",
    "32009R1223": "Cosmetics",
    "32012R0528": "Biocides",
    "32012R0649": "PIC",
    "32019R1021": "POPs",
}
"""The acts the record publishes that were expected to carry substance tables."""

CONSOLIDATED_URLS = (
    re.compile(r"/resource/consolidation/(\d{4}[A-Z]\d{4})%2F(\d{8})\.ENG\.fmx4$"),
    re.compile(r"/resource/celex/0(\d{4}[A-Z]\d{4})-(\d{8})\.ENG\.fmx4$"),
)
ORIGINAL_URL = re.compile(r"/resource/celex/3(\d{4}[A-Z]\d{4})\.ENG\.fmx4$")

HYPHENS = str.maketrans({chr(code): "-" for code in (0x2010, 0x2011, 0x2012, 0x2013, 0x2212)})
CAS = re.compile(r"(?<![\d-])(\d{2,7})-(\d{2})-(\d)(?![\d-])")
EC = re.compile(r"(?<![\d-])([2-9]\d{2})-(\d{3})-(\d)(?![\d-])")
INDEX = re.compile(r"(?<![\d-])(\d{3})-(\d{3})-(\d{2})-([\dX])(?![\d-])")
INDEX_LEAD = re.compile(r"^(\d{3}-\d{3}-\d{2}-[\dX])(?![\d-])")
NUMBER_LEAD = re.compile(r"^(\d+[a-z]?)(?:\.|\s|$)")
EMPTY_MARKS = frozenset({"", "-", "/", chr(0x2013), chr(0x2014)})
"""What a cell holds when it holds nothing: empty, a hyphen, a slash, an en or em dash."""
SUBSTANCE_THRESHOLD = 3
FORM_RANK = {"index": 0, "number": 1, "cas": 2, "ec": 2, "text": 3}


# --------------------------------------------------------------------------- the cache


@dataclass(frozen=True)
class Cached:
    """One consolidated (or original) English Formex package the disk cache holds."""

    act: str
    label: str
    key: str
    url: str

    @property
    def version(self) -> str:
        code = self.act[1:]
        return self.act if self.label == "original" else f"0{code}-{self.label}"

    @property
    def order(self) -> tuple[int, str]:
        return (0, "") if self.label == "original" else (1, self.label)


class OfflineDiskCache(DiskResponseCache):
    """The shared disk cache, refusing to fall through to the network."""

    @property
    def offline(self) -> bool:
        return True


def cached_packages(root: Path) -> dict[str, list[Cached]]:
    """Every English Formex package in the cache, by act, oldest first; read from sidecars."""
    found: dict[tuple[str, str], Cached] = {}
    for sidecar in sorted(root.glob("*/*.json")):
        entry = json.loads(sidecar.read_text())
        if entry.get("status_code") != 200 or entry.get("accept") != "application/zip":
            continue
        url = str(entry.get("url") or "")
        label = None
        act = None
        for pattern in CONSOLIDATED_URLS:
            matched = pattern.search(url)
            if matched is not None:
                act, label = "3" + matched[1], matched[2]
        original = ORIGINAL_URL.search(url)
        if original is not None:
            act, label = "3" + original[1], "original"
        if act is None or label is None:
            continue
        item = Cached(act=act, label=label, key=str(entry["key"]), url=url)
        previous = found.get((act, label))
        if previous is None or item.url < previous.url:
            found[(act, label)] = item
    by_act: dict[str, list[Cached]] = defaultdict(list)
    for item in found.values():
        by_act[item.act].append(item)
    return {act: sorted(items, key=lambda one: one.order) for act, items in sorted(by_act.items())}


def load(cache: DiskResponseCache, item: Cached) -> FormexPackage | None:
    """The package behind one cache entry, or `None` if the cache does not answer for it."""
    response = cache.get(item.key)
    if response is None:
        return None
    return FormexPackage.from_zip(
        response.body,
        act=ActId(corpus="eu", key=item.act),
        requested_version=VersionId(item.version),
        served_version=VersionId(item.version),
        language="ENG",
        source_url=response.url,
        fetched_at=response.fetched_at,
    )


def fetch_missing(root: Path, acts: Iterable[str]) -> None:
    """List each act's versions through the project client and fetch packages not cached yet."""
    http = CellarHttp(cache=DiskResponseCache(root))
    client = CellarClient(http, observed_on=OBSERVED_ON)
    held = cached_packages(root)
    for act in acts:
        celex = Celex.parse(act)
        have = {item.version for item in held.get(act, [])}
        for record in client.tree_notice(celex).consolidated:
            if record.version in have:
                continue
            fetched = client.fetch_formex(celex, record.version, allow_original_fallback=False)
            state = "fetched" if isinstance(fetched, FormexPackage) else fetched.state
            print(f"fetch {act} {record.version}: {state}", file=sys.stderr)
    print(f"fetch: {http.network_calls} network calls", file=sys.stderr)
    http.close()


# --------------------------------------------------------------------------- tables


@dataclass(frozen=True)
class Row:
    """One `ROW` as a grid line. `marks[i]`: '' declared, R rowspan copy, C colspan, - none."""

    ordinal: int
    header: bool
    cells: tuple[str, ...]
    marks: tuple[str, ...]
    block: str = ""


@dataclass
class Table:
    """One `TBL` under an annex unit, with its grid and what reading the grid ran into."""

    unit: str
    container: str
    ordinal: int
    via: str
    element: Element
    declared_cols: int | None
    rows: list[Row]
    rowspans: int = 0
    colspans: int = 0
    missing_col: int = 0
    collisions: int = 0
    nested: int = 0
    stray_rows: int = 0
    header_cells_in_body: int = 0
    blocks: int = 0

    @property
    def identity(self) -> tuple[str, str, int]:
        return (self.unit, self.container, self.ordinal)

    @property
    def name(self) -> str:
        return f"{self.container} #{self.ordinal}" + (f" (in {self.via})" if self.via else "")

    @property
    def width(self) -> int:
        return max((len(row.cells) for row in self.rows), default=0)

    @property
    def headers(self) -> list[Row]:
        return [row for row in self.rows if row.header]


def _int(raw: str | None) -> int | None:
    if raw is None or not raw.strip().isdigit():
        return None
    return int(raw.strip())


def read_table(tbl: Element, unit: str, container: str, ordinal: int, via: str) -> Table:
    """The grid of one table, columns placed by `COL`, spans copied down and across."""
    table = Table(unit, container, ordinal, via, tbl, _int(tbl.get("COLS")), [])
    elements = [pair for corpus in tbl.findall("CORPUS") for pair in _rows(corpus, "")]
    table.blocks = sum(1 for corpus in tbl.findall("CORPUS") for _ in corpus.iter("BLK"))
    nested = [inner for inner in tbl.iter("TBL") if inner is not tbl]
    table.nested = len(nested)
    inner_rows = sum(1 for inner in nested for _ in inner.iter("ROW"))
    table.stray_rows = sum(1 for _ in tbl.iter("ROW")) - inner_rows - len(elements)
    pending: dict[int, tuple[int, str]] = {}
    raw: list[tuple[int, bool, dict[int, tuple[str, str]], str]] = []
    for index, (row, block) in enumerate(elements, 1):
        cells: dict[int, tuple[str, str]] = {}
        for col, (left, text) in sorted(pending.items()):
            cells[col] = (text, "R")
            if left == 1:
                del pending[col]
            else:
                pending[col] = (left - 1, text)
        header = row.get("TYPE") == "HEADER"
        free = 1
        for cell in row.findall("CELL"):
            declared = _int(cell.get("COL"))
            if declared is None:
                table.missing_col += 1
                while free in cells:
                    free += 1
                declared = free
            col = declared
            if col in cells:
                table.collisions += 1
            if cell.get("TYPE") == "HEADER" and not header:
                table.header_cells_in_body += 1
            across = max(1, _int(cell.get("COLSPAN")) or 1)
            down = max(1, _int(cell.get("ROWSPAN")) or 1)
            text = verbatim_text(cell)
            cells[col] = (text, "")
            for extra in range(1, across):
                cells[col + extra] = ("", "C")
            table.colspans += across > 1
            if down > 1:
                table.rowspans += 1
                for extra in range(across):
                    pending[col + extra] = (down - 1, text if extra == 0 else "")
            free = col + across
        raw.append((index, header, cells, block))
    width = max([table.declared_cols or 0] + [max(cells) for _, _, cells, _ in raw if cells])
    for index, header, cells, block in raw:
        line = [cells.get(col, ("", "-")) for col in range(1, width + 1)]
        texts = tuple(text for text, _ in line)
        table.rows.append(Row(index, header, texts, tuple(mark for _, mark in line), block))
    return table


def _rows(element: Element, block: str) -> Iterator[tuple[Element, str]]:
    """A corpus's rows in document order, each with the `BLK` headings it sits under."""
    for child in element:
        if child.tag == "ROW":
            yield child, block
        elif child.tag == "BLK":
            heading = child.find("TI.BLK")
            title = "" if heading is None else norm(verbatim_text(heading))
            yield from _rows(child, f"{block} / {title}" if block else title)


def _outer_tables(element: Element) -> Iterator[Element]:
    """Tables under `element` that are not themselves inside a table."""
    for child in element:
        if child.tag == "TBL":
            yield child
        else:
            yield from _outer_tables(child)


def _walk(
    element: Element,
    unit: str,
    location: ProvisionLocation,
    counter: CoverageCounter,
    siblings: _Siblings,
    list_type: str | None,
    ordinals: Counter[str],
    found: list[Table],
) -> None:
    """The parser's walk over one annex, stopping at every table to read it."""
    for child in element:
        tag = child.tag
        if tag in SKIPPED_SUBTREES:
            continue
        if tag == "TBL":
            ordinals[location.canonical] += 1
            ordinal = ordinals[location.canonical]
            found.append(read_table(child, unit, location.canonical, ordinal, ""))
            continue
        if tag in INLINE:
            for tbl in _outer_tables(child):
                ordinals[location.canonical] += 1
                ordinal = ordinals[location.canonical]
                found.append(read_table(tbl, unit, location.canonical, ordinal, tag))
            continue
        placed = _placed(child, location, True, counter, siblings, list_type)
        if placed is None:
            nested = child.get("TYPE") if tag == "LIST" else list_type
            _walk(child, unit, location, counter, siblings, nested, ordinals, found)
        else:
            _walk(child, unit, placed, counter, _Siblings(), None, ordinals, found)


def tables_of(package: FormexPackage) -> tuple[list[Table], Counter[str], tuple[Element, ...]]:
    """Every table under a numbered annex unit, the tables found elsewhere, and the documents."""
    counter = CoverageCounter()
    elsewhere: Counter[str] = Counter()
    found: list[Table] = []
    documents = documents_of(act_documents(package, counter))
    for document in documents:
        for unit, is_annex in unit_elements(document):
            if not is_annex:
                elsewhere["in an article"] += sum(1 for _ in _outer_tables(unit))
                continue
            segment = annex_segment(unit)
            if segment is None:
                elsewhere["in an unnumbered annex"] += sum(1 for _ in _outer_tables(unit))
                continue
            location = ProvisionLocation(
                segments=(LocationSegment(code=segment[0], value=segment[1]),)
            )
            _walk(unit, location.canonical, location, counter, _Siblings(), None, Counter(), found)
    elsewhere["unreadable members"] = counter.documents_unreadable
    return found, elsewhere, documents


# --------------------------------------------------------------------------- identifiers


def cas_valid(number: str) -> bool:
    digits = number.replace("-", "")
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(digit) * weight for weight, digit in enumerate(reversed(body), 1))
    return total % 10 == check


def ec_check(number: str) -> int:
    """The EC check value, 0 to 10; 10 is a value no EC number is issued with."""
    digits = number.replace("-", "")[:6]
    return sum(int(digit) * weight for weight, digit in enumerate(digits, 1)) % 11


def ec_valid(number: str) -> bool:
    return ec_check(number) == int(number[-1])


@dataclass
class Found:
    """What one cell's text holds, identifier by identifier."""

    cas: list[str] = field(default_factory=list)
    cas_bad: list[str] = field(default_factory=list)
    ec: list[str] = field(default_factory=list)
    ec_bad: list[str] = field(default_factory=list)
    ec_ten: list[str] = field(default_factory=list)
    index: list[str] = field(default_factory=list)
    unusual_hyphen: int = 0


def scan(text: str) -> Found:
    found = Found()
    plain = text.translate(HYPHENS)
    if plain != text:
        found.unusual_hyphen = sum(
            1 for pattern in (CAS, EC, INDEX) for one in pattern.finditer(plain)
        ) - sum(1 for pattern in (CAS, EC, INDEX) for one in pattern.finditer(text))
    for matched in CAS.finditer(plain):
        (found.cas if cas_valid(matched[0]) else found.cas_bad).append(matched[0])
    for matched in EC.finditer(plain):
        value = matched[0]
        if ec_valid(value):
            found.ec.append(value)
        elif ec_check(value) == 10:
            found.ec_ten.append(value)
        else:
            found.ec_bad.append(value)
    found.index.extend(matched[0] for matched in INDEX.finditer(plain))
    return found


def _weights(kind: str) -> list[int]:
    start = int(kind[-1])
    return (
        list(range(start, start + 8))
        if kind.startswith("asc")
        else list(range(start + 7, start - 1, -1))
    )


def index_rules() -> dict[str, object]:
    """Candidate check-digit rules for a CLP Index number, named; X stands for 10."""
    rules: dict[str, object] = {}
    for kind in ("asc1", "asc2", "asc3", "desc1", "desc2", "desc3"):
        for modulus in (10, 11):
            for complement in (False, True):
                name = f"weights {kind} mod {modulus}{' complement' if complement else ''}"
                rules[name] = (_weights(kind), modulus, complement)
    rules["luhn"] = "luhn"
    rules["digit sum mod 10"] = "sum"
    return rules


def index_rule_holds(rule: object, value: str) -> bool:
    digits = [int(one) for one in value.replace("-", "")[:8]]
    last = value[-1]
    check = 10 if last == "X" else int(last)
    if rule == "sum":
        return sum(digits) % 10 == check
    if rule == "luhn":
        total = 0
        for position, digit in enumerate(reversed(digits)):
            doubled = digit * 2 if position % 2 == 0 else digit
            total += doubled - 9 if doubled > 9 else doubled
        return (10 - total % 10) % 10 == check
    assert isinstance(rule, tuple)
    weights, modulus, complement = rule
    total = sum(weight * digit for weight, digit in zip(weights, digits, strict=True))
    computed = (modulus - total % modulus) % modulus if complement else total % modulus
    return bool(computed == check)


# --------------------------------------------------------------------------- columns and keys


def norm(text: str) -> str:
    return str(normalize_for_comparison(text))


def is_empty(text: str) -> bool:
    return norm(text) in EMPTY_MARKS


@dataclass
class Column:
    """Per-column counts over a table's body rows, declared cells only."""

    cells: int = 0
    cas_cells: int = 0
    ec_cells: int = 0
    index_cells: int = 0
    multi_cas: int = 0
    dash_cells: int = 0
    cas_bad: int = 0
    ec_bad: int = 0
    ec_ten: int = 0
    unusual_hyphen: int = 0


@dataclass
class Analysis:
    """One table read as entries: columns, the key, and the entries it yields."""

    table: Table
    body: list[Row]
    columns: list[Column]
    repeated_headers: int
    blank_rows: int
    key: int | None = None
    form: str = ""
    scores: list[tuple[int, str, float, float]] = field(default_factory=list)
    entries: dict[str, list[Row]] = field(default_factory=dict)
    duplicates: list[str] = field(default_factory=list)
    unkeyed: list[Row] = field(default_factory=list)
    bad: list[tuple[int, int, str, str]] = field(default_factory=list)

    @property
    def substance(self) -> bool:
        return any(
            max(column.cas_cells, column.ec_cells, column.index_cells) >= SUBSTANCE_THRESHOLD
            for column in self.columns
        )

    def identifiers(self, key: str) -> list[str]:
        values: set[str] = set()
        for row in self.entries[key]:
            for text, mark in zip(row.cells, row.marks, strict=True):
                if mark == "":
                    found = scan(text)
                    values.update(f"cas:{one}" for one in found.cas)
                    values.update(f"ec:{one}" for one in found.ec)
        return sorted(values)


def form_of(values: list[str]) -> str:
    if not values:
        return "text"
    shares = {
        "index": sum(1 for one in values if INDEX_LEAD.match(one)),
        "number": sum(1 for one in values if NUMBER_LEAD.match(one)),
        "cas": sum(1 for one in values if CAS.fullmatch(one)),
        "ec": sum(1 for one in values if EC.fullmatch(one)),
    }
    for form in ("index", "number", "cas", "ec"):
        if shares[form] * 2 > len(values):
            return form
    return "text"


def key_of(text: str, form: str) -> str | None:
    value = norm(text)
    if value in EMPTY_MARKS:
        return None
    if form == "index":
        matched = INDEX_LEAD.match(value)
        return matched[1] if matched else value
    if form == "number":
        matched = NUMBER_LEAD.match(value)
        return matched[1] if matched else value
    return value


def analyse(table: Table) -> Analysis:
    """Column counts, the chosen key, and the rows grouped into keyed entries."""
    header_lines = {tuple(norm(cell) for cell in row.cells) for row in table.headers}
    body: list[Row] = []
    repeated = blank = 0
    for row in table.rows:
        if row.header:
            continue
        line = tuple(norm(cell) for cell in row.cells)
        if line in header_lines:
            repeated += 1
        elif all(is_empty(cell) for cell in row.cells):
            blank += 1
        else:
            body.append(row)
    analysis = Analysis(table, body, [Column() for _ in range(table.width)], repeated, blank)
    for row in body:
        for col, (text, mark) in enumerate(zip(row.cells, row.marks, strict=True)):
            if mark != "":
                continue
            column = analysis.columns[col]
            column.cells += 1
            column.dash_cells += norm(text) in EMPTY_MARKS - {""}
            found = scan(text)
            column.cas_cells += bool(found.cas)
            column.multi_cas += len(found.cas) > 1
            column.ec_cells += bool(found.ec)
            column.index_cells += bool(found.index)
            column.cas_bad += len(found.cas_bad)
            column.ec_bad += len(found.ec_bad)
            column.ec_ten += len(found.ec_ten)
            column.unusual_hyphen += found.unusual_hyphen
            for kind, values in (
                ("CAS", found.cas_bad),
                ("EC", found.ec_bad),
                ("EC=10", found.ec_ten),
            ):
                analysis.bad.extend((row.ordinal, col + 1, kind, value) for value in values)
    choose_key(analysis)
    return analysis


def choose_key(analysis: Analysis) -> None:
    """The key column: distinct and covering, then by form, then leftmost.

    A column qualifies when its own values are at least 95% distinct and its own cells plus the
    rowspan copies of them cover at least 80% of body rows. Among qualifying columns an
    Index-shaped one wins, then a numbered one, then a CAS- or EC-shaped one, then text; within
    a form the larger product of the two shares, then the leftmost. With none qualifying, the
    largest product is taken, and a table where every product is zero has no key.
    """
    rows = len(analysis.body)
    if not rows:
        return
    ranked: list[tuple[bool, int, float, int, str]] = []
    for col in range(analysis.table.width):
        own = [
            norm(row.cells[col])
            for row in analysis.body
            if row.marks[col] == "" and not is_empty(row.cells[col])
        ]
        copies = sum(1 for row in analysis.body if row.marks[col] == "R")
        form = form_of(own)
        distinct = len({key_of(value, form) for value in own}) / len(own) if own else 0.0
        covered = (len(own) + copies) / rows
        analysis.scores.append((col + 1, form, round(distinct, 3), round(covered, 3)))
        qualifies = distinct >= 0.95 and covered >= 0.8
        ranked.append((not qualifies, FORM_RANK[form], -distinct * covered, col, form))
    qualifying = [one for one in ranked if not one[0]]
    chosen = min(qualifying) if qualifying else min(ranked, key=lambda one: (one[2], one[3]))
    _, _, product, col, form = chosen
    if product == 0:
        return
    analysis.key, analysis.form = col, form
    group(analysis)


def group(analysis: Analysis) -> None:
    """Rows into entries by the key column; a rowspan copy of the key continues an entry."""
    assert analysis.key is not None
    col = analysis.key
    seen: Counter[str] = Counter()
    current: str | None = None
    entries: dict[str, list[Row]] = {}
    for row in analysis.body:
        if row.marks[col] == "R" and current is not None:
            entries[current].append(row)
            continue
        key = key_of(row.cells[col], analysis.form) if row.marks[col] == "" else None
        if key is None:
            analysis.unkeyed.append(row)
            current = None
            continue
        seen[key] += 1
        if seen[key] > 1:
            current = None
            continue
        entries[key] = [row]
        current = key
    analysis.duplicates = sorted(key for key, count in seen.items() if count > 1)
    analysis.entries = {key: rows for key, rows in entries.items() if seen[key] == 1}


# --------------------------------------------------------------------------- reading a version


@dataclass
class Version:
    """One cached version, read: its analysed tables and the tables found outside annexes."""

    item: Cached
    analyses: list[Analysis]
    elsewhere: Counter[str]

    @property
    def substance(self) -> list[Analysis]:
        return [one for one in self.analyses if one.substance]


def read_version(cache: DiskResponseCache, item: Cached) -> Version | None:
    package = load(cache, item)
    if package is None:
        return None
    tables, elsewhere, _ = tables_of(package)
    return Version(item, [analyse(table) for table in tables], elsewhere)


def shown_path(path: Path) -> str:
    """A path for a results file: the home directory written as `~`."""
    home = str(Path.home())
    text = str(path)
    return "~" + text[len(home) :] if text.startswith(home) else text


def show(text: str, limit: int = 0) -> str:
    """A cell on one line for printing: line breaks shown as `\\n`, optionally clipped."""
    shown = text.replace("\n", "\\n")
    return shown if not limit or len(shown) <= limit else shown[: limit - 1] + "…"


def header_text(table: Table) -> str:
    if not table.headers:
        return "(no HEADER row)"
    return " || ".join(" | ".join(show(cell) for cell in row.cells) for row in table.headers)


# --------------------------------------------------------------------------- survey


def survey(root: Path, acts: list[str] | None, verbose: bool) -> int:
    cache = OfflineDiskCache(root)
    packages = cached_packages(root)
    keys = acts or list(packages)
    print(f"read on {OBSERVED_ON} over the disk cache at {shown_path(root)}")
    print(f"acts with an English Formex package: {len(packages)}, read here: {len(keys)}")
    print(f"packages read here: {sum(len(packages.get(key, [])) for key in keys)}\n")
    overview: list[str] = []
    for act in keys:
        items = packages.get(act, [])
        if not items:
            print(f"== {act}: no package cached\n")
            continue
        overview.append(survey_act(cache, act, items, verbose))
    print("== overview (newest version per act)")
    print("act         name       versions  annex tables  substance tables  valid CAS cells")
    for line in overview:
        print(line)
    return 0


def survey_act(cache: DiskResponseCache, act: str, items: list[Cached], verbose: bool) -> str:
    name = SIX_ACTS.get(act, "")
    print(f"== {act} {name}".rstrip())
    print(f"versions cached {len(items)}: {items[0].label} to {items[-1].label}")
    bad: dict[tuple[str, int, str, str], tuple[str, int, int]] = {}
    seen_versions: Counter[tuple[str, int, str, str]] = Counter()
    indexes: set[str] = set()
    hyphens = 0
    identities: dict[tuple[str, str, int], list[str]] = defaultdict(list)
    newest: Version | None = None
    for item in items:
        version = read_version(cache, item)
        if version is None:
            print(f"  {item.label}: not readable from the cache")
            continue
        newest = version
        markup = Counter[str]()
        for one in version.analyses:
            table = one.table
            markup["rowspan"] += table.rowspans
            markup["colspan"] += table.colspans
            markup["no COL"] += table.missing_col
            markup["collision"] += table.collisions
            markup["nested TBL"] += table.nested
            markup["stray ROW"] += table.stray_rows
            markup["header rows"] += len(table.headers)
            markup["tables without header"] += not table.headers
            markup["CELL TYPE=HEADER in body"] += table.header_cells_in_body
            markup["BLK"] += table.blocks
        rows = sum(len(one.body) for one in version.substance)
        elsewhere = ", ".join(f"{k} {v}" for k, v in sorted(version.elsewhere.items()) if v)
        print(
            f"  {item.label:9s} annex tables {len(version.analyses):4d}  substance "
            f"{len(version.substance):3d} ({rows} body rows)  "
            + "  ".join(f"{k} {v}" for k, v in sorted(markup.items()) if v)
            + (f"  | elsewhere: {elsewhere}" if elsewhere else "")
        )
        for one in version.substance:
            identities[one.table.identity].append(item.label)
            for ordinal, col, kind, value in one.bad:
                where = (one.table.container, one.table.ordinal, kind, value)
                seen_versions[where] += 1
                bad.setdefault(where, (item.label, ordinal, col))
            for column in one.columns:
                hyphens += column.unusual_hyphen
            if act == "32008R1272" and one.table.unit == "AN VI":
                for row in one.body:
                    for text, mark in zip(row.cells, row.marks, strict=True):
                        if mark == "":
                            indexes.update(scan(text).index)
    if newest is None:
        return f"{act}  (nothing readable)"
    print(f"\n  substance-table identities across versions: {len(identities)}")
    for identity, labels in sorted(identities.items()):
        print(
            f"    {identity[1]} #{identity[2]}: {len(labels)} versions, {labels[0]}..{labels[-1]}"
        )
    print(f"\n  newest version {newest.item.version}: substance tables in full")
    for one in newest.substance:
        print_table(one, verbose)
    others = [one for one in newest.analyses if not one.substance]
    print(f"\n  newest version: {len(others)} other annex tables")
    if verbose:
        for one in others:
            table = one.table
            print(
                f"    {table.name}: {table.width} cols, {len(one.body)} body rows; "
                f"{show(header_text(table), 120)}"
            )
    print_bad(bad, seen_versions, verbose)
    if hyphens:
        print(f"  identifiers written with a non-ASCII hyphen (all versions): {hyphens}")
    if indexes:
        print_index_rules(indexes)
    print()
    valid_cas = sum(column.cas_cells for one in newest.substance for column in one.columns)
    tables = len(newest.analyses)
    return (
        f"{act}  {name:9s}  {len(items):8d}  {tables:12d}  {len(newest.substance):16d}  "
        f"{valid_cas:15d}"
    )


def print_bad(
    bad: dict[tuple[str, int, str, str], tuple[str, int, int]],
    seen: Counter[tuple[str, int, str, str]],
    verbose: bool,
) -> None:
    """Identifier-shaped values whose check digit fails, each once, where it first appeared."""
    kinds = Counter(kind for _, _, kind, _ in bad)
    print(
        f"\n  identifier-shaped values failing their check digit, distinct per table: "
        f"{sum(kinds.values())} ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))})"
    )
    ordered = sorted(bad.items(), key=lambda pair: (pair[1], pair[0]))
    ten = [where for where, _ in ordered if where[2] == "EC=10"]
    if ten:
        last = Counter(where[3][-1] for where in ten)
        print(
            f"    EC numbers whose weighted sum is 10 mod 11: {len(ten)}, last digit "
            f"{dict(sorted(last.items()))}"
        )
    shown = [pair for pair in ordered if pair[0][2] != "EC=10" or verbose]
    for (container, tbl, kind, value), (label, at_row, at_col) in shown[: None if verbose else 20]:
        print(
            f"    {kind:5s} {value:14s} {container} #{tbl} row {at_row} col {at_col}, "
            f"first {label}, in {seen[(container, tbl, kind, value)]} versions"
        )


def print_table(one: Analysis, verbose: bool) -> None:
    table = one.table
    print(f"\n  -- {table.unit} | {table.name}")
    print(
        f"     columns {table.width} (COLS={table.declared_cols}), rows {len(table.rows)} "
        f"(header {len(table.headers)}, body {len(one.body)}, repeated header "
        f"{one.repeated_headers}, blank {one.blank_rows}), ROWSPAN {table.rowspans}, "
        f"COLSPAN {table.colspans}, no COL {table.missing_col}, nested TBL {table.nested}, "
        f"BLK {table.blocks}, stray ROW {table.stray_rows}"
    )
    print(f"     header: {header_text(table)}")
    for col, column in enumerate(one.columns, 1):
        print(
            f"     col {col:2d}: cells {column.cells:5d}  CAS {column.cas_cells:5d} "
            f"(multi {column.multi_cas}, bad {column.cas_bad})  EC {column.ec_cells:5d} "
            f"(bad {column.ec_bad}, =10 {column.ec_ten})  Index {column.index_cells:5d}  "
            f"dash {column.dash_cells}"
        )
    print("     key scores (col, form, distinct/rows, covered/rows): " + str(one.scores))
    if one.key is None:
        print("     key: none chosen (no column holds a value)")
        return
    sizes = Counter(len(rows) for rows in one.entries.values())
    no_id = [key for key in one.entries if not one.identifiers(key)]
    named = name_column(table)
    print(
        f"     name col {'-' if named is None else named + 1}; "
        f"key: col {one.key + 1} ({one.form}); entries {len(one.entries)}, unkeyed rows "
        f"{len(one.unkeyed)}, duplicate keys {len(one.duplicates)}, rows per entry "
        f"{dict(sorted(sizes.items()))}, entries with no CAS/EC {len(no_id)}"
    )
    if one.duplicates:
        print(f"     duplicate keys: {' ; '.join(show(key, 60) for key in one.duplicates[:20])}")
    if no_id:
        listed = no_id if verbose else no_id[:40]
        more = f" ... and {len(no_id) - len(listed)} more" if len(listed) < len(no_id) else ""
        print(f"     entries with no CAS/EC: {' ; '.join(show(key, 60) for key in listed)}{more}")
    if verbose:
        for row in one.unkeyed:
            print(f"     unkeyed row {row.ordinal}: {show(' | '.join(row.cells), 160)}")


def print_index_rules(values: set[str]) -> None:
    print(f"\n  CLP Index check character: {len(values)} distinct Index numbers in AN VI")
    results = []
    for name, rule in index_rules().items():
        hits = sum(1 for value in values if index_rule_holds(rule, value))
        results.append((hits, name))
    for hits, name in sorted(results, key=lambda one: (-one[0], one[1]))[:6]:
        print(f"    {name:34s} {hits}/{len(values)} ({hits / len(values):.4f})")
    whole = [name for hits, name in results if hits == len(values)]
    print(f"    rules holding for every value: {', '.join(whole) or 'none'}")
    last = Counter(value[-1] for value in values)
    print(f"    last character distribution: {dict(sorted(last.items()))}")


# --------------------------------------------------------------------------- transitions


@dataclass
class Moved:
    """A keyed row diff between two versions of one table identity, or of one unit."""

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    amended: list[str] = field(default_factory=list)
    spacing: list[str] = field(default_factory=list)
    same: int = 0
    unkeyed: tuple[int, int] = (0, 0)
    duplicates: tuple[int, int] = (0, 0)

    @property
    def moved(self) -> int:
        return len(self.added) + len(self.removed) + len(self.amended) + len(self.spacing)


def cells_of(rows: list[Row]) -> tuple[tuple[str, ...], ...]:
    return tuple(row.cells for row in rows)


def diff(before: Analysis | None, after: Analysis | None) -> Moved:
    moved = Moved()
    left = before.entries if before is not None else {}
    right = after.entries if after is not None else {}
    moved.added = sorted(set(right) - set(left))
    moved.removed = sorted(set(left) - set(right))
    for key in sorted(set(left) & set(right)):
        old, new = cells_of(left[key]), cells_of(right[key])
        if old == new:
            moved.same += 1
        elif [[norm(cell) for cell in row] for row in old] == [
            [norm(cell) for cell in row] for row in new
        ]:
            moved.spacing.append(key)
        else:
            moved.amended.append(key)
    moved.unkeyed = (
        len(before.unkeyed) if before else 0,
        len(after.unkeyed) if after else 0,
    )
    moved.duplicates = (
        len(before.duplicates) if before else 0,
        len(after.duplicates) if after else 0,
    )
    return moved


NAME_WORDS = ("name", "substance", "chemical", "designation")
"""Header words that mark the column an entry's name is read from, in the order tried."""


def name_column(table: Table) -> int | None:
    """The first column whose header names a substance, chemical or designation, if any."""
    for word in NAME_WORDS:
        for col in range(table.width):
            if any(word in norm(row.cells[col]).lower() for row in table.headers):
                return col
    return None


def entry_json(one: Analysis, key: str, cells: bool) -> dict[str, object]:
    """One entry in the register's hypothetical shape; a multi-row entry's cells join by line."""
    rows = one.entries[key]
    entry: dict[str, object] = {
        "unit": one.table.unit,
        "container": one.table.container,
        "table": one.table.ordinal,
        "key": key,
        "identifiers": [
            {"scheme": value.split(":", 1)[0], "value": value.split(":", 1)[1]}
            for value in one.identifiers(key)
        ],
    }
    named = name_column(one.table)
    entry["name"] = None if named is None else rows[0].cells[named]
    if cells:
        width = one.table.width
        entry["cells"] = [
            "\n".join(row.cells[col] for row in rows if row.marks[col] == "")
            for col in range(width)
        ]
    return entry


def size(document: object) -> tuple[int, int]:
    """Bytes as UTF-8, written with `indent=2` and compact."""
    pretty = json.dumps(document, indent=2, ensure_ascii=False).encode()
    compact = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode()
    return len(pretty), len(compact)


def transitions(root: Path, act: str, record: Path | None, verbose: bool) -> int:
    cache = OfflineDiskCache(root)
    items = cached_packages(root).get(act, [])
    print(f"read on {OBSERVED_ON} over the disk cache at {shown_path(root)}")
    print(f"== {act} {SIX_ACTS.get(act, '')}: {len(items)} cached versions".rstrip())
    previous: Version | None = None
    totals: Counter[str] = Counter()
    largest: tuple[int, str] = (0, "")
    pairs: dict[tuple[str, str], dict[str, Moved]] = {}
    for item in items:
        current = read_version(cache, item)
        if current is None:
            print(f"  {item.label}: not readable from the cache")
            continue
        if not current.analyses and current.elsewhere["unreadable members"]:
            print(f"  {item.label}: skipped, a member is not well-formed and no table was read")
            continue
        if previous is not None:
            by_unit = compare(previous, current, totals, verbose)
            pairs[(previous.item.version, current.item.version)] = by_unit
            for unit in by_unit:
                weight = unit_diff_size(previous, current, unit)
                if weight > largest[0]:
                    largest = (weight, f"{previous.item.label}->{current.item.label} {unit}")
        previous = current
    print("\n  stability of keys present in both versions, over every transition:")
    both = totals["same"] + totals["amended"] + totals["spacing"]
    for name in ("same", "spacing", "amended"):
        share = totals[name] / both if both else 0.0
        print(f"    {name:8s} {totals[name]:7d} ({share:.4f})")
    print(f"    added    {totals['added']:7d}\n    removed  {totals['removed']:7d}")
    print(f"    tables keyed by a different column than the version before: {totals['flips']}")
    if previous is not None:
        print_sizes(previous, largest)
    if record is not None:
        cross_check(record, act, cache, items, pairs)
    return 0


def compare(
    before: Version, after: Version, totals: Counter[str], verbose: bool
) -> dict[str, Moved]:
    """Per table identity and per unit, the keyed row diff between two versions."""
    left = {one.table.identity: one for one in before.substance if one.key is not None}
    right = {one.table.identity: one for one in after.substance if one.key is not None}
    units: dict[str, Moved] = {}
    lines: list[str] = []
    for identity in sorted(set(left) | set(right)):
        old, new = left.get(identity), right.get(identity)
        if old is not None and new is not None and old.key != new.key:
            totals["flips"] += 1
        moved = diff(old, new)
        unit = units.setdefault(identity[0], Moved())
        unit.added += moved.added
        unit.removed += moved.removed
        unit.amended += moved.amended
        unit.spacing += moved.spacing
        unit.same += moved.same
        for name in ("added", "removed", "amended", "spacing"):
            totals[name] += len(getattr(moved, name))
        totals["same"] += moved.same
        state = "" if old and new else (" (table new)" if new else " (table gone)")
        if moved.moved or verbose or state:
            lines.append(
                f"    {identity[1]} #{identity[2]}{state}: +{len(moved.added)} "
                f"-{len(moved.removed)} ~{len(moved.amended)} ws {len(moved.spacing)} "
                f"={moved.same} unkeyed {moved.unkeyed[0]}->{moved.unkeyed[1]} "
                f"dup {moved.duplicates[0]}->{moved.duplicates[1]}"
            )
            if verbose and moved.moved:
                for name in ("added", "removed", "amended", "spacing"):
                    keys = getattr(moved, name)
                    if keys:
                        lines.append(f"      {name}: {', '.join(keys[:40])}")
    total = sum(one.moved for one in units.values())
    print(f"  {before.item.label} -> {after.item.label}: {total} rows moved")
    for line in lines:
        print(line)
    return units


def unit_diff_size(before: Version, after: Version, unit: str) -> int:
    """Bytes (indent=2) of one unit's entry changes with cells, before and after in full."""
    left = {
        one.table.identity: one
        for one in before.substance
        if one.key is not None and one.table.unit == unit
    }
    right = {
        one.table.identity: one
        for one in after.substance
        if one.key is not None and one.table.unit == unit
    }
    changes: list[dict[str, object]] = []
    for identity in sorted(set(left) | set(right)):
        old, new = left.get(identity), right.get(identity)
        moved = diff(old, new)
        for kind, keys in (
            ("added", moved.added),
            ("removed", moved.removed),
            ("amended", moved.amended + moved.spacing),
        ):
            for key in keys:
                changes.append(
                    {
                        "kind": kind,
                        "key": key,
                        "before": entry_json(old, key, True)
                        if old and key in old.entries
                        else None,
                        "after": entry_json(new, key, True) if new and key in new.entries else None,
                    }
                )
    return size(changes)[0] if changes else 0


def print_sizes(newest: Version, largest: tuple[int, str]) -> None:
    keyed = [one for one in newest.substance if one.key is not None]
    with_cells = [entry_json(one, key, True) for one in keyed for key in one.entries]
    without = [entry_json(one, key, False) for one in keyed for key in one.entries]
    print(f"\n  register of {newest.item.version}: {len(with_cells)} entries")
    pretty, compact = size({"entries": with_cells})
    print(f"    with cells     {pretty:10d} bytes indent=2, {compact:10d} compact")
    pretty, compact = size({"entries": without})
    print(f"    without cells  {pretty:10d} bytes indent=2, {compact:10d} compact")
    print(
        f"  largest single-transition unit entry diff with cells: {largest[0]} bytes, {largest[1]}"
    )


# --------------------------------------------------------------------------- the record


def cross_check(
    record: Path,
    act: str,
    cache: DiskResponseCache,
    items: list[Cached],
    pairs: dict[tuple[str, str], dict[str, Moved]],
) -> None:
    """Every published change of the act: does a substance table sit in its unit, what moved."""
    head = subprocess.run(
        ["git", "-C", str(record), "log", "-1", "--format=%h %cs"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    print(f"\n  published record {head or '(no git answer)'}")
    held = {item.version for item in items}
    tally: Counter[str] = Counter()
    for path in sorted((record / "eu" / act / "changes").glob("*.json")):
        payload = json.loads(path.read_text())
        old, new = str(payload["from_version"]), str(payload["to_version"])
        units = sorted({str(one["change"]["provision"]["location"]) for one in payload["changes"]})
        by_unit = pairs.get((old, new))
        for unit in units:
            tally["changes"] += 1
            if by_unit is None:
                missing = [one for one in (old, new) if one not in held]
                reason = f"not cached: {', '.join(missing)}" if missing else "not consecutive here"
                tally["pair unread"] += 1
                if unit.startswith("AN"):
                    print(f"    {old} -> {new} {unit}: {reason}")
                continue
            moved = by_unit.get(unit)
            if moved is None:
                continue
            tally["with a substance table"] += 1
            tally["rows moved" if moved.moved else "no row moved"] += 1
            print(
                f"    {old} -> {new} {unit}: +{len(moved.added)} -{len(moved.removed)} "
                f"~{len(moved.amended)} ws {len(moved.spacing)} ={moved.same}"
            )
    print(
        f"  published changes {tally['changes']}: in a unit holding a substance table "
        f"{tally['with a substance table']} (rows moved {tally['rows moved']}, none "
        f"{tally['no row moved']}); version pair unread here {tally['pair unread']}"
    )


# --------------------------------------------------------------------------- excerpt


def excerpt(root: Path, act: str, version: str, unit: str, table: int | None, rows: int) -> int:
    cache = OfflineDiskCache(root)
    items = {item.version: item for item in cached_packages(root).get(act, [])}
    item = items.get(version)
    if item is None:
        print(f"{act} {version}: not cached", file=sys.stderr)
        return 1
    package = load(cache, item)
    if package is None:
        print(f"{act} {version}: not readable from the cache", file=sys.stderr)
        return 1
    found, _, documents = tables_of(package)
    in_unit = [one for one in found if one.unit == unit]
    if table is None:
        chosen = next((one for one in in_unit if analyse(one).substance), None)
    else:
        chosen = in_unit[table - 1] if 0 < table <= len(in_unit) else None
    if chosen is None:
        print(f"{unit}: no such table ({len(in_unit)} tables in the unit)", file=sys.stderr)
        return 1
    print('<?xml version="1.0" encoding="UTF-8"?>')
    print(
        f"<!-- {act} {version} {unit}, {chosen.name}; "
        f"header rows and the first {rows} body rows -->"
    )
    print(tostring(fragment(documents, chosen.element, rows), encoding="unicode"))
    return 0


HEADINGS = frozenset({"TITLE", "NO.GR.SEQ"})
"""Children of an ancestor the excerpt keeps: the parser reads a location from them."""


def fragment(documents: tuple[Element, ...], target: Element, rows: int) -> Element:
    """The ancestors of `target` reduced to tags, attributes and headings, then the table."""
    chain: list[Element] = []
    for document in documents:
        parents = {child: parent for parent in document.iter() for child in parent}
        if target in parents or target is document:
            node: Element | None = target
            while node is not None:
                chain.insert(0, node)
                node = parents.get(node)
            break
    top: Element | None = None
    current: Element | None = None
    for ancestor in chain[:-1]:
        reduced = Element(ancestor.tag, dict(ancestor.attrib))
        for child in ancestor:
            if child.tag in HEADINGS:
                reduced.append(deepcopy(child))
                reduced[-1].tail = None
        if current is None:
            top = reduced
        else:
            current.append(reduced)
        current = reduced
    table = trim(target, rows)
    if current is None:
        return table
    current.append(table)
    assert top is not None
    return top


def trim(tbl: Element, rows: int) -> Element:
    """The table with its header rows and its first `rows` body rows; every other row dropped."""
    copy = deepcopy(tbl)
    kept = 0
    for corpus in copy.findall("CORPUS"):
        for row in list(corpus.findall("ROW")):
            if row.get("TYPE") == "HEADER":
                continue
            kept += 1
            if kept > rows:
                corpus.remove(row)
    copy.tail = None
    return copy


# --------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("survey", help="every annex table of every cached version")
    one.add_argument("--act", action="append", help="CELEX; repeatable; default every act")
    one.add_argument("--verbose", action="store_true")
    one.add_argument("--fetch", action="store_true", help="fill gaps for the six acts first")
    two = commands.add_parser("transitions", help="keyed row diffs between cached versions")
    two.add_argument("--act", required=True)
    two.add_argument("--record", type=Path, help="a clone of the published changelogs")
    two.add_argument("--verbose", action="store_true")
    three = commands.add_parser("excerpt", help="one table as a well-formed XML fragment")
    three.add_argument("act")
    three.add_argument("version")
    three.add_argument("unit")
    three.add_argument("--table", type=int, help="1-based among the unit's tables")
    three.add_argument("--rows", type=int, default=20)
    args = parser.parse_args()

    root = default_cache_dir() / "cellar"
    try:
        if args.command == "survey":
            if args.fetch:
                fetch_missing(root, args.act or sorted(SIX_ACTS))
            return survey(root, args.act, args.verbose)
        if args.command == "transitions":
            return transitions(root, args.act, args.record, args.verbose)
        return excerpt(root, args.act, args.version, args.unit, args.table, args.rows)
    except FixtureMissing as error:
        print(f"not cached: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
