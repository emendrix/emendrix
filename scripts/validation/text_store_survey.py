#!/usr/bin/env python
"""How large a store of every provision of every cached version would be, and what it misses.

One-off validation code, kept so the figures a verbatim text store is sized against are a
reproducible artifact rather than an assertion. A store keeps, for each consolidated version of
each act, one line per provision node in pre-order: a header line, then for each node its
canonical location, its parent's, its heading, its verbatim `text`, its `comparison_text` and
the sha256 of the comparison text, each line a compact JSON object, the file gzip at level 9
with `mtime=0`. A node's `text` is its whole subtree, so every depth repeats the text below it.
This script answers, over every consolidated English Formex package the disk cache holds:

1. `size`: per act and in total, versions, nodes, units, raw and gzip bytes of that layout; the
   same for a layout holding units only; and for a pooled layout, where each act's distinct
   comparison texts (by digest) are written once into one pool file and each version keeps only
   a list of locations and digests. Also the parse time per package.
2. `tokens`: the length of every distinct comparison text, by depth (units, their children,
   grandchildren, deeper), in words, characters and a token proxy, against a 2,048-token cap.
3. `coverage`: per act on the watchlist or in a clone of the public record, the versions the
   record has diffed, the versions the adapter lists from the act's tree notice, and the
   packages the cache holds; and what a full build would still have to fetch.

**Method.** Packages are enumerated from the cache's sidecar files (status 200, a Formex 4 zip
in English at a consolidation address), never by listing an act's versions, so the population
is exactly what this machine holds. Each is read through the project's own adapter
(`EuCorpusAdapter.fetch_version`), the path a store build takes, so a version the adapter answers
with a state is counted as that state, and a version it served from the original OJ text is
counted apart. The serialiser is this script's own, written for this measurement and
independent of any store code; each line is `json.dumps` with compact separators and no ASCII
escaping, which is the byte form a pydantic `model_dump_json` of the same fields produces.

**What a figure does not mean.** The token figure is a proxy, `ceil(chars / 4)`: no tokenizer
for the embedder is installed, and four characters per token overstates the count for plain
English while understating it for numbers, CAS-like identifiers and tables read as prose. A
figure is over the cache as it stood on the day of the run, which is not every version an act
has: `coverage` says what is missing, and a projection over every listed version is a scaling,
not a measurement. The pooled figure keeps the first verbatim text met for a digest, so two
nodes whose verbatim texts differ only in whitespace count once. Distinct texts are counted per
act; a provision repeated word for word across two acts counts in both.

It writes nothing, calls no model and spends nothing. Offline by default: the cache is read
with network access refused, and the tree-notice age limit is lifted through the environment
(`EMENDRIX_NOTICE_MAX_AGE_S`) so a notice of any age is read as cached. `coverage --fetch`
refreshes stale notices through the project's own client, with its polite delay.

Usage, from the repository root::

    uv run python scripts/validation/text_store_survey.py size [--act CELEX] [--verbose]
    uv run python scripts/validation/text_store_survey.py tokens [--act CELEX]
    uv run python scripts/validation/text_store_survey.py coverage --record <changelogs clone>
    uv run python scripts/validation/text_store_survey.py coverage --record <clone> --fetch
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from emendrix.core import ActId, ProvisionNode, ProvisionTree, VersionId
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import DiskResponseCache, FixtureMissing, default_cache_dir
from emendrix.eu.http import NOTICE_MAX_AGE_ENV
from emendrix.eu.identifiers import Celex
from emendrix.eu.packages import FormexPackage
from emendrix.watch.config import load_watchlist

OBSERVED_ON = date(2026, 10, 19)
"""Passed in rather than read from a clock, exactly as the CLI boundary passes it."""

REPOSITORY = Path(__file__).resolve().parents[2]
WATCHLIST = REPOSITORY / "watchlist.toml"
OFFLINE_NOTICE_AGE_S = "31536000"
RECORD_URL = "https://github.com/emendrix/changelogs"
TOKEN_CAP = 2048
CHARS_PER_TOKEN = 4

CONSOLIDATED_URLS = (
    re.compile(r"/resource/consolidation/(\d{4}[A-Z]\d{4})%2F(\d{8})\.ENG\.fmx4$"),
    re.compile(r"/resource/celex/0(\d{4}[A-Z]\d{4})-(\d{8})\.ENG\.fmx4$"),
)


# --------------------------------------------------------------------------- the cache


@dataclass(frozen=True)
class Cached:
    """One consolidated English Formex package the disk cache holds."""

    act: str
    label: str
    key: str

    @property
    def version(self) -> str:
        return f"0{self.act[1:]}-{self.label}"


class OfflineDiskCache(DiskResponseCache):
    """The shared disk cache, refusing to fall through to the network."""

    @property
    def offline(self) -> bool:
        return True


def cache_root() -> Path:
    return default_cache_dir() / "cellar"


def cached_packages(root: Path) -> dict[str, list[Cached]]:
    """Every consolidated English Formex package in the cache, by act, oldest first."""
    found: dict[tuple[str, str], Cached] = {}
    for sidecar in sorted(root.glob("*/*.json")):
        entry = json.loads(sidecar.read_text())
        if entry.get("status_code") != 200 or entry.get("accept") != "application/zip":
            continue
        url = str(entry.get("url") or "")
        for pattern in CONSOLIDATED_URLS:
            matched = pattern.search(url)
            if matched is not None:
                item = Cached(act="3" + matched[1], label=matched[2], key=str(entry["key"]))
                found.setdefault((item.act, item.label), item)
    by_act: dict[str, list[Cached]] = defaultdict(list)
    for item in found.values():
        by_act[item.act].append(item)
    return {act: sorted(items, key=lambda one: one.label) for act, items in sorted(by_act.items())}


def original_cached(offline: EuCorpusAdapter, act: str) -> bool:
    """Whether the cache answers for the act's original OJ text, asked the way the adapter asks.

    The original sits at an OJ address rather than a CELEX one, so the sidecar URLs cannot say
    which act it belongs to; the tree notice can, and an offline request either hits or misses.
    """
    try:
        found = offline.client.fetch_formex(
            Celex.parse(act), VersionId(act), allow_original_fallback=False
        )
    except FixtureMissing:
        return False
    return isinstance(found, FormexPackage)


def make_adapter(fetch: bool) -> EuCorpusAdapter:
    """The project's adapter over the shared cache: offline unless `fetch`."""
    if not fetch:
        os.environ[NOTICE_MAX_AGE_ENV] = OFFLINE_NOTICE_AGE_S
        cache: DiskResponseCache = OfflineDiskCache(cache_root())
    else:
        os.environ.pop(NOTICE_MAX_AGE_ENV, None)
        cache = DiskResponseCache(cache_root())
    return EuCorpusAdapter.build(observed_on=OBSERVED_ON, cache=cache)


def watched() -> dict[str, str]:
    """The watchlist's acts by CELEX, with their names; empty if there is no watchlist."""
    if not WATCHLIST.is_file():
        return {}
    return {act.celex: act.name or "" for act in load_watchlist(WATCHLIST).acts}


def revision(clone: Path | None) -> str:
    """A clone's own commit, so a reading is dated by the record it was taken over."""
    if clone is None:
        return "no record read"
    try:
        found = subprocess.run(
            ["git", "-C", str(clone), "log", "-1", "--format=%h %ad", "--date=short"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "revision unknown"
    return found.stdout.strip()


def print_header(fetch: bool, record: Path | None) -> None:
    """The run's provenance: command, date, cache, record and whether it was offline."""
    root = cache_root()
    entries = sum(1 for _ in root.glob("*/*.json"))
    # The clone's own path is this machine's; the results name the record by its commit.
    shown_args = [
        arg if record is None else arg.replace(str(record), "<changelogs clone>")
        for arg in sys.argv[1:]
    ]
    argv = " ".join(["uv run python", "scripts/validation/" + Path(sys.argv[0]).name, *shown_args])
    print(f"command   {argv}")
    print(f"run on    {OBSERVED_ON.isoformat()}")
    shown = str(root).replace(str(Path.home()), "~", 1)
    print(f"cache     {shown}, {entries} entries")
    if record is None:
        print("record    none read")
    else:
        print(f"record    a fresh clone of {RECORD_URL} at {revision(record)}")
    if fetch:
        print("offline   no: notices older than 6 h refetched; an uncached package read is fetched")
    else:
        print(f"offline   yes: network refused, {NOTICE_MAX_AGE_ENV}={OFFLINE_NOTICE_AGE_S}")
    print()


# --------------------------------------------------------------------------- reading


@dataclass(frozen=True)
class Read:
    """One cached package as the adapter served it: a tree, or the reason there is none."""

    item: Cached
    tree: ProvisionTree | None
    state: str
    seconds: float


def read_all(adapter: EuCorpusAdapter, items: list[Cached]) -> Iterator[Read]:
    """Each package through `fetch_version`, timed; a state or a cache miss is counted."""
    for item in items:
        started = time.perf_counter()
        try:
            fetched = adapter.fetch_version(
                ActId(corpus="eu", key=item.act), VersionId(item.version)
            )
        except FixtureMissing:
            yield Read(item, None, "not served offline", time.perf_counter() - started)
            continue
        seconds = time.perf_counter() - started
        if isinstance(fetched, ProvisionTree):
            yield Read(item, fetched, "tree", seconds)
        else:
            yield Read(item, None, type(fetched).__name__, seconds)


def selected(acts: list[str] | None) -> dict[str, list[Cached]]:
    packages = cached_packages(cache_root())
    if acts:
        return {act: packages.get(act, []) for act in acts}
    return packages


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def line(record: dict[str, object]) -> bytes:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def nodes_with_parents(tree: ProvisionTree) -> Iterator[tuple[ProvisionNode, str | None]]:
    """Every node in pre-order with its parent's canonical location."""

    def walk(node: ProvisionNode, parent: str | None) -> Iterator[tuple[ProvisionNode, str | None]]:
        yield node, parent
        for child in node.children:
            yield from walk(child, node.location.canonical)

    for root in tree.roots:
        yield from walk(root, None)


def node_record(node: ProvisionNode, parent: str | None) -> dict[str, object]:
    return {
        "location": node.location.canonical,
        "parent": parent,
        "heading": node.heading,
        "text": str(node.text),
        "comparison_text": str(node.comparison_text),
        "digest": digest(str(node.comparison_text)),
    }


def header_record(tree: ProvisionTree, requested: str, nodes: int, units: int) -> dict[str, object]:
    return {
        "store_schema": "1.0",
        "corpus": tree.act.corpus,
        "key": tree.act.key,
        "version": requested,
        "served_version": str(tree.version),
        "language": tree.language,
        "nodes": nodes,
        "units": units,
    }


def gz(data: bytes) -> int:
    return len(gzip.compress(data, compresslevel=9, mtime=0))


# --------------------------------------------------------------------------- size


@dataclass
class Sizes:
    """One act's figures, summed over its versions."""

    versions: int = 0
    states: dict[str, int] = field(default_factory=dict)
    fallback: int = 0
    nodes: int = 0
    units: int = 0
    raw: int = 0
    gzip: int = 0
    unit_raw: int = 0
    unit_gzip: int = 0
    index_raw: int = 0
    index_gzip: int = 0
    pool: dict[str, bytes] = field(default_factory=dict)
    seconds: list[float] = field(default_factory=list)

    def pool_sizes(self) -> tuple[int, int]:
        data = b"".join(self.pool[key] for key in sorted(self.pool))
        return len(data), gz(data)


def measure_version(sizes: Sizes, read: Read, verbose: bool) -> None:
    """Add one version's three layouts to its act's figures."""
    tree = read.tree
    assert tree is not None
    pairs = list(nodes_with_parents(tree))
    units = len(tree.roots)
    head = line(header_record(tree, read.item.version, len(pairs), units))
    records = [node_record(node, parent) for node, parent in pairs]
    body = b"".join(line(record) for record in records)
    unit_head = line(header_record(tree, read.item.version, units, units))
    unit_body = b"".join(line(record) for record in records if record["parent"] is None)
    index_body = b"".join(
        line({key: record[key] for key in ("location", "parent", "heading", "digest")})
        for record in records
    )
    for record in records:
        key = str(record["digest"])
        if key not in sizes.pool:
            pooled = {k: record[k] for k in ("digest", "text", "comparison_text")}
            sizes.pool[key] = line(pooled)
    full, units_only, index = head + body, unit_head + unit_body, head + index_body
    sizes.versions += 1
    sizes.nodes += len(pairs)
    sizes.units += units
    sizes.raw += len(full)
    sizes.gzip += (full_gz := gz(full))
    sizes.unit_raw += len(units_only)
    sizes.unit_gzip += gz(units_only)
    sizes.index_raw += len(index)
    sizes.index_gzip += gz(index)
    if str(tree.version) != read.item.version:
        sizes.fallback += 1
    if verbose:
        print(
            f"  {read.item.version}  nodes {len(pairs):6d}  units {units:4d}  "
            f"raw {len(full):11,d}  gzip {full_gz:10,d}  parse {read.seconds:6.2f}s"
            + ("" if str(tree.version) == read.item.version else f"  served {tree.version}")
        )


def size(acts: list[str] | None, verbose: bool) -> int:
    print_header(fetch=False, record=None)
    names = watched()
    adapter = make_adapter(fetch=False)
    total = Sizes()
    pooled_raw = pooled_gzip = distinct = 0
    every_second: list[float] = []
    print(
        f"{'act':10s} {'w':1s} {'vers':>4s} {'nodes':>8s} {'units':>6s} "
        f"{'raw':>13s} {'gzip':>11s} {'units gz':>10s} {'distinct':>8s} "
        f"{'pool gz':>10s} {'index gz':>10s} {'pooled gz':>10s} {'parse s':>8s}"
    )
    for act, items in selected(acts).items():
        sizes = Sizes()
        if verbose:
            print(f"== {act} {names.get(act, '')}".rstrip())
        for read in read_all(adapter, items):
            sizes.seconds.append(read.seconds)
            if read.tree is None:
                sizes.states[read.state] = sizes.states.get(read.state, 0) + 1
                if verbose:
                    print(f"  {read.item.version}  {read.state}")
                continue
            measure_version(sizes, read, verbose)
        pool_raw, pool_gzip = sizes.pool_sizes()
        print(
            f"{act:10s} {'*' if act in names else ' '} {sizes.versions:4d} {sizes.nodes:8d} "
            f"{sizes.units:6d} {sizes.raw:13,d} {sizes.gzip:11,d} {sizes.unit_gzip:10,d} "
            f"{len(sizes.pool):8d} {pool_gzip:10,d} {sizes.index_gzip:10,d} "
            f"{pool_gzip + sizes.index_gzip:10,d} {sum(sizes.seconds):8.1f}"
            + (f"  states {sizes.states}" if sizes.states else "")
            + (f"  served from OJ {sizes.fallback}" if sizes.fallback else "")
        )
        for name in ("versions", "nodes", "units", "raw", "gzip", "unit_raw", "unit_gzip"):
            setattr(total, name, getattr(total, name) + getattr(sizes, name))
        total.index_raw += sizes.index_raw
        total.index_gzip += sizes.index_gzip
        total.fallback += sizes.fallback
        for state, count in sizes.states.items():
            total.states[state] = total.states.get(state, 0) + count
        pooled_raw += pool_raw
        pooled_gzip += pool_gzip
        distinct += len(sizes.pool)
        every_second.extend(sizes.seconds)
    adapter.close()
    print()
    print("totals (w: * = on the local watchlist)")
    print(f"  acts                         {len(selected(acts))}")
    print(f"  versions with a tree         {total.versions}")
    print(f"  versions answered by state   {sum(total.states.values())}  {total.states}")
    print(f"  versions served from the OJ  {total.fallback}")
    print(f"  nodes                        {total.nodes:,d}")
    print(f"  units                        {total.units:,d}")
    print("  every node, whole-subtree text (the store's layout):")
    print(f"    raw bytes                  {total.raw:,d}")
    print(f"    gzip bytes                 {total.gzip:,d}")
    if total.versions:
        print(f"    gzip bytes per version     {total.gzip // total.versions:,d} (mean)")
    print("  units only:")
    print(f"    raw bytes                  {total.unit_raw:,d}")
    print(f"    gzip bytes                 {total.unit_gzip:,d}")
    print("  pooled per act by comparison-text digest:")
    print(f"    distinct texts             {distinct:,d} of {total.nodes:,d} node lines")
    print(f"    pool raw / gzip            {pooled_raw:,d} / {pooled_gzip:,d}")
    print(f"    index raw / gzip           {total.index_raw:,d} / {total.index_gzip:,d}")
    print(f"    pool + index gzip          {pooled_gzip + total.index_gzip:,d}")
    if total.gzip:
        saving = 1 - (pooled_gzip + total.index_gzip) / total.gzip
        print(f"    saving against the layout  {saving:.3f} of the gzip bytes")
    if every_second:
        ordered = sorted(every_second)
        print(
            f"  parse seconds per package    p50 {percentile(ordered, 50):.2f}  "
            f"p90 {percentile(ordered, 90):.2f}  max {ordered[-1]:.2f}  "
            f"total {sum(ordered):.1f}"
        )
    return 0


# --------------------------------------------------------------------------- tokens


def percentile(ordered: list[float] | list[int], share: int) -> float:
    """Nearest-rank percentile of an already sorted list."""
    if not ordered:
        return 0.0
    rank = max(1, math.ceil(share / 100 * len(ordered)))
    return float(ordered[rank - 1])


def depth_label(depth: int) -> str:
    return {1: "units", 2: "children", 3: "grandchildren"}.get(depth, "deeper")


def tokens(acts: list[str] | None) -> int:
    print_header(fetch=False, record=None)
    print(
        f"token proxy: ceil(characters / {CHARS_PER_TOKEN}) of the comparison text, against a "
        f"{TOKEN_CAP}-token cap. A proxy, not a count: no tokenizer for the embedder is "
        "installed; four characters per token overstates plain English and understates numbers, "
        "identifiers and tables read as prose."
    )
    print("each distinct comparison text (by sha256) is counted once per act and depth bucket;")
    print("'leaf' counts the over-cap texts of nodes with no children, which no finer node covers.")
    print()
    adapter = make_adapter(fetch=False)
    # (act, depth bucket, digest) -> (chars, words, has children at every occurrence)
    seen: dict[tuple[str, str, str], tuple[int, int, bool]] = {}
    occurrences: dict[str, int] = defaultdict(int)
    over_occurrences: dict[str, int] = defaultdict(int)
    for act, items in selected(acts).items():
        for read in read_all(adapter, items):
            if read.tree is None:
                continue
            for node in read.tree.walk():
                text = str(node.comparison_text)
                bucket = depth_label(node.location.depth)
                key = (act, bucket, digest(text))
                proxy = math.ceil(len(text) / CHARS_PER_TOKEN)
                occurrences[bucket] += 1
                if proxy > TOKEN_CAP:
                    over_occurrences[bucket] += 1
                parent = bool(node.children)
                if key in seen:
                    chars, words, had = seen[key]
                    seen[key] = (chars, words, had and parent)
                else:
                    seen[key] = (len(text), len(text.split()), parent)
    adapter.close()
    print(
        f"{'depth':14s} {'distinct':>9s} {'measure':>8s} {'p50':>8s} {'p90':>8s} {'p99':>8s} "
        f"{'max':>9s} {'> cap':>7s} {'leaf':>6s} {'nodes':>9s} {'nodes>cap':>9s}"
    )
    for bucket in ("units", "children", "grandchildren", "deeper", "all"):
        rows = [v for k, v in seen.items() if bucket == "all" or k[1] == bucket]
        proxies = sorted(math.ceil(chars / CHARS_PER_TOKEN) for chars, _, _ in rows)
        over = sum(1 for chars, _, _ in rows if math.ceil(chars / CHARS_PER_TOKEN) > TOKEN_CAP)
        leaf = sum(
            1
            for chars, _, parent in rows
            if not parent and math.ceil(chars / CHARS_PER_TOKEN) > TOKEN_CAP
        )
        nodes = sum(occurrences.values()) if bucket == "all" else occurrences[bucket]
        nodes_over = sum(over_occurrences.values()) if bucket == "all" else over_occurrences[bucket]
        measures: dict[str, list[int]] = {
            "words": sorted(words for _, words, _ in rows),
            "chars": sorted(chars for chars, _, _ in rows),
            "tokens~": proxies,
        }
        for index, (name, values) in enumerate(measures.items()):
            last = index == len(measures) - 1
            print(
                f"{(bucket if index == 0 else ''):14s} {(len(rows) if index == 0 else ''):>9} "
                f"{name:>8s} {percentile(values, 50):8.0f} {percentile(values, 90):8.0f} "
                f"{percentile(values, 99):8.0f} {(values[-1] if values else 0):9d} "
                f"{(over if last else ''):>7} {(leaf if last else ''):>6} "
                f"{(nodes if last else ''):>9} {(nodes_over if last else ''):>9}"
            )
    return 0


# --------------------------------------------------------------------------- coverage


def record_versions(record: Path, act: str) -> set[str]:
    """Every version the record's index names on either side of an event."""
    index = record / "eu" / act / "index.json"
    if not index.is_file():
        return set()
    events = json.loads(index.read_text()).get("events", [])
    found: set[str] = set()
    for event in events:
        for side in ("from_version", "to_version"):
            if event.get(side):
                found.add(str(event[side]))
    return found


def listed_versions(adapter: EuCorpusAdapter, act: str) -> tuple[set[str], str]:
    """The consolidations the tree notice lists, or why it could not be read."""
    try:
        listed = adapter.discover_versions(ActId(corpus="eu", key=act))
    except FixtureMissing:
        return set(), "notice not cached"
    except Exception as error:  # a malformed notice is a counted answer here, never a crash
        return set(), f"notice unreadable ({type(error).__name__})"
    return {str(one.version) for one in listed if str(one.version).startswith("0")}, ""


def coverage(record: Path, fetch: bool) -> int:
    print_header(fetch=fetch, record=record)
    names = watched()
    held = cached_packages(cache_root())
    in_record = {path.name for path in (record / "eu").iterdir() if path.is_dir()}
    acts = sorted(set(names) | in_record)
    adapter = make_adapter(fetch=fetch)
    offline = make_adapter(fetch=False)  # after: the age limit is read when a client is built
    print(
        "w: * on the local watchlist, r: * in the record. 'listed' counts consolidations the "
        "tree notice lists; 'to fetch' is listed and not cached; 'diffed' and 'diffed, not "
        "cached' count consolidations the record names on either side of an event; 'oj' says "
        "whether the original OJ text the record diffs from is cached (y), not cached (n), "
        "or not diffed from (-)."
    )
    print()
    print(
        f"{'act':10s} w r {'diffed':>6s} {'listed':>6s} {'cached':>6s} "
        f"{'listed∩cached':>13s} {'to fetch':>8s} {'diffed, not cached':>18s} oj"
    )
    totals: dict[str, int] = defaultdict(int)
    missing_lines: list[str] = []
    for act in acts:
        named = record_versions(record, act)
        diffed = {version for version in named if version.startswith("0")}
        oj = "-" if act not in named else ("y" if original_cached(offline, act) else "n")
        listed, why = listed_versions(adapter, act)
        cached = {item.version for item in held.get(act, [])}
        to_fetch = sorted(listed - cached)
        diffed_missing = sorted(diffed - cached)
        print(
            f"{act:10s} {'*' if act in names else ' '} {'*' if act in in_record else ' '} "
            f"{len(diffed):6d} {len(listed):6d} {len(cached):6d} {len(listed & cached):13d} "
            f"{len(to_fetch):8d} {len(diffed_missing):18d} {oj:>2s}" + (f"  {why}" if why else "")
        )
        totals["acts"] += 1
        totals["diffed"] += len(diffed)
        totals["listed"] += len(listed)
        totals["cached"] += len(cached)
        totals["both"] += len(listed & cached)
        totals["to_fetch"] += len(to_fetch)
        totals["diffed_missing"] += len(diffed_missing)
        totals["no_notice"] += 1 if why else 0
        totals["oj_diffed"] += oj != "-"
        totals["oj_missing"] += oj == "n"
        if to_fetch or diffed_missing or oj == "n":
            missing_lines.append(f"{act} {names.get(act, '')}".rstrip())
            if to_fetch:
                missing_lines.append(f"  to fetch:            {', '.join(to_fetch)}")
            if diffed_missing:
                missing_lines.append(f"  diffed, not cached:  {', '.join(diffed_missing)}")
            if oj == "n":
                missing_lines.append(f"  original OJ text diffed from, not cached: {act}")
    print()
    print(f"acts                                 {totals['acts']}")
    print(f"  whose notice could not be read     {totals['no_notice']}")
    print(f"versions the record has diffed       {totals['diffed']}")
    print(f"consolidations the notices list      {totals['listed']}")
    print(f"consolidated packages cached         {totals['cached']}")
    print(f"  of them listed                     {totals['both']}")
    print(f"listed, not cached (a build fetches) {totals['to_fetch']}")
    print(f"diffed, not cached                   {totals['diffed_missing']}")
    print(f"original OJ texts diffed from        {totals['oj_diffed']}")
    print(f"  of them not cached                 {totals['oj_missing']}")
    if totals["listed"]:
        print(f"coverage of listed by cached         {totals['both'] / totals['listed']:.3f}")
    offline.close()
    calls = adapter.client.http.network_calls
    print(f"network calls                        {calls}")
    adapter.close()
    print()
    print("missing, per act")
    for missing in missing_lines:
        print(missing)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("size", help="bytes of the store's layout and two alternatives")
    one.add_argument("--act", action="append", help="CELEX; repeatable; default every act")
    one.add_argument("--verbose", action="store_true", help="one line per version")
    two = commands.add_parser("tokens", help="length distribution of distinct comparison texts")
    two.add_argument("--act", action="append", help="CELEX; repeatable; default every act")
    three = commands.add_parser("coverage", help="diffed, listed and cached versions per act")
    three.add_argument("--record", type=Path, required=True, help="a clone of the changelogs")
    three.add_argument("--fetch", action="store_true", help="refresh stale tree notices")
    args = parser.parse_args()
    if args.command == "size":
        return size(args.act, args.verbose)
    if args.command == "tokens":
        return tokens(args.act)
    return coverage(args.record, args.fetch)


if __name__ == "__main__":
    sys.exit(main())
