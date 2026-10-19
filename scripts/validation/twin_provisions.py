#!/usr/bin/env python
"""Which provisions of two acts are textual twins, and whether one amending act changed only one.

One-off validation code, kept so the threshold a twin map is built with, and the case for an
alert when twins drift apart, are a reproducible artifact rather than an assertion. "Twin" here
means textually similar and nothing more: no sentence of this script, or of its results, says a
provision is equivalent to another or ought to change with it. It answers, over the disk cache
and a fresh clone of the public record:

1. `pairs`: every same-kind unit pair of the Medical Devices Regulation (`32017R0745`) and the
   IVDR (`32017R0746`), article with article and annex with annex, scored by the word ratio, and
   the mutual-best pairs; timed. Run on each act's newest version and, where that differs, on the
   newest version date both acts have.
2. `floor`: the lowest candidate floor at or above 0.50 at which the mutual-best pairs at or
   above it agree on their normalised headings at least 95% of the time (0.90 if none does);
   then, for the pairs at that floor, the children aligned level by level, how the record's
   changed coordinates fall on them, and the excerpt each pair's page would carry.
3. `divergence`: the changes of one act's record whose unit has a twin, made by an amending act
   that also made an event of the other act which left the twin untouched (one-sided), and the
   ones where it touched the twin too (two-sided); and whether one-sided changes clear a bar of
   five from at least two amending acts.
4. `screen`: every pair of acts the cache holds, newest version each, screened by 8-word
   shingle overlap and then scored, counted against a rule of ten mutual-best article pairs.

**Method.** The word ratio is `difflib.SequenceMatcher(None, a_words, b_words,
autojunk=False).ratio()` over `comparison_text.split()`, the convention the diff engine's
date-only check uses; `real_quick_ratio()` and `quick_ratio()` are upper bounds, so a pair whose
bound is below the lowest floor in play (0.30) is skipped without changing any figure above it.
A pair is mutual-best when each side is the other's highest ratio; ties go to the lower canonical
location string. The character form compared against it is the engine's renumbering matcher: a
character `SequenceMatcher` on the first 2,000 characters of each comparison text. Headings are
compared case-folded with whitespace collapsed and trailing `.:;` stripped; a missing heading
equals nothing. Children are aligned the same way below a pair, level by level, kind with kind
(a paragraph with a paragraph), at the floor. A page's passages are the non-equal word opcodes,
each with up to six equal words either side and each side cut at 400 characters with a marked
cut; a pair's passages are withheld when their characters on either side exceed 30% of that
side's comparison text, counted over every passage rather than the twelve a page would show.
Changes and amending acts are read from the clone's payloads through `ChangelogEntry` and
`emendrix.site_.amending.amending_keys`, imported rather than repeated.

**What a figure does not mean.** Heading agreement is a proxy for the precision of a pairing:
two articles can share a heading and differ in substance, and a reworded heading can sit on a
twin. The twins are computed on the newest texts, while the record's changes were made to older
ones, so a change counted against a twin may predate the pairing it is counted under. A
one-sided change says the record holds no change to the twin from the same amending act; it does
not say the act should have made one, and the record may simply not hold that event. The screen
counts shared shingles only below a document-frequency cap, so a pair whose whole overlap is
boilerplate found in more than that many units is not screened in; the run says how many
shingles the cap set aside, and a unit of fewer than eight words has no shingle and is never
screened in at all.

It writes nothing, calls no model and spends nothing. Offline by default, with the tree-notice
age limit lifted through the environment; `pairs --fetch` and `floor --fetch` refresh the two
acts' notices and fetch their newest listed packages through the project's own client.

Usage, from the repository root::

    uv run python scripts/validation/twin_provisions.py pairs [--fetch]
    uv run python scripts/validation/twin_provisions.py pairs --a 32017R0745 --b 32017R0746 \\
        --version-a 20250110 --version-b 20250110
    uv run python scripts/validation/twin_provisions.py floor [--fetch] --record <clone>
    uv run python scripts/validation/twin_provisions.py divergence --record <clone> [--fetch]
    uv run python scripts/validation/twin_provisions.py screen [--floor 0.60]
"""

from __future__ import annotations

import argparse
import difflib
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from text_store_survey import (
    cache_root,
    cached_packages,
    make_adapter,
    print_header,
)

from emendrix.core import ActId, ProvisionNode, ProvisionTree, VersionId
from emendrix.diff.tree_diff import RENUMBER_PREFIX_LIMIT
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import FixtureMissing
from emendrix.output import ChangelogEntry
from emendrix.site_.amending import amending_keys

MDR = "32017R0745"
IVDR = "32017R0746"
LOWEST_FLOOR = 0.30
CANDIDATE_FLOORS = tuple(round(0.30 + 0.05 * step, 2) for step in range(13))
FLOOR_FROM = 0.50
AGREEMENT = 0.95
FALLBACK_FLOOR = 0.90
CONTEXT_WORDS = 6
PASSAGE_CHARS = 400
MAX_PASSAGES = 12
WITHHELD_SHARE = 0.30
CUT = "[…]"
SHINGLE_WORDS = 8
JACCARD = 0.5
SHINGLE_DF_CAP = 200
TWIN_RULE_PAIRS = 10
BAR_CHANGES = 5
BAR_INSTRUMENTS = 2


# --------------------------------------------------------------------------- reading


@dataclass(frozen=True)
class Item:
    """One provision node reduced to what pairing reads."""

    location: str
    kind: str
    heading: str | None
    text: str
    words: tuple[str, ...]
    node: ProvisionNode


def item_of(node: ProvisionNode) -> Item:
    text = str(node.comparison_text)
    return Item(
        location=node.location.canonical,
        kind=str(node.location.segments[-1].code),
        heading=node.heading,
        text=text,
        words=tuple(text.split()),
        node=node,
    )


def version_id(act: str, raw: str) -> str:
    return raw if raw.startswith("0") else f"0{act[1:]}-{raw}"


def newest(adapter: EuCorpusAdapter, act: str, fetch: bool) -> list[str]:
    """The act's consolidations, oldest first: listed by the notice with `fetch`, else cached."""
    if fetch:
        listed = adapter.discover_versions(ActId(corpus="eu", key=act))
        return sorted(str(one.version) for one in listed if str(one.version).startswith("0"))
    return [item.version for item in cached_packages(cache_root()).get(act, [])]


def tree_of(adapter: EuCorpusAdapter, act: str, version: str) -> ProvisionTree:
    fetched = adapter.fetch_version(ActId(corpus="eu", key=act), VersionId(version))
    if not isinstance(fetched, ProvisionTree):
        raise SystemExit(f"{act} {version}: {type(fetched).__name__}")
    return fetched


# --------------------------------------------------------------------------- pairing


@dataclass
class Scored:
    """Ratios of one side against the other, with how many pairs the bounds skipped."""

    ratios: dict[tuple[int, int], float] = field(default_factory=dict)
    candidates: int = 0
    skipped_real_quick: int = 0
    skipped_quick: int = 0


def score(left: Sequence[Item], right: Sequence[Item], floor: float) -> Scored:
    """Every same-kind pair's word ratio at or above `floor`; seq2 is set once per right item."""
    scored = Scored()
    matcher = difflib.SequenceMatcher(None, autojunk=False)
    for j, b in enumerate(right):
        matcher.set_seq2(list(b.words))
        for i, a in enumerate(left):
            if a.kind != b.kind:
                continue
            scored.candidates += 1
            matcher.set_seq1(list(a.words))
            if matcher.real_quick_ratio() < floor:
                scored.skipped_real_quick += 1
                continue
            if matcher.quick_ratio() < floor:
                scored.skipped_quick += 1
                continue
            ratio = matcher.ratio()
            if ratio >= floor:
                scored.ratios[(i, j)] = ratio
    return scored


def bests(
    scored: Scored, left: Sequence[Item], right: Sequence[Item]
) -> tuple[dict[int, tuple[int, float]], dict[int, tuple[int, float]]]:
    """Each side's best match by ratio, ties to the lower canonical location string."""
    best_left: dict[int, tuple[int, float]] = {}
    best_right: dict[int, tuple[int, float]] = {}
    for (i, j), ratio in scored.ratios.items():
        held = best_left.get(i)
        if held is None or (-ratio, right[j].location) < (-held[1], right[held[0]].location):
            best_left[i] = (j, ratio)
        held = best_right.get(j)
        if held is None or (-ratio, left[i].location) < (-held[1], left[held[0]].location):
            best_right[j] = (i, ratio)
    return best_left, best_right


def mutual(
    best_left: dict[int, tuple[int, float]], best_right: dict[int, tuple[int, float]]
) -> list[tuple[int, int, float]]:
    return sorted(
        (i, j, ratio) for i, (j, ratio) in best_left.items() if best_right.get(j, (-1, 0.0))[0] == i
    )


def norm_heading(heading: str | None) -> str:
    return " ".join((heading or "").casefold().split()).rstrip(".:;").strip()


def headings_equal(a: Item, b: Item) -> bool:
    left = norm_heading(a.heading)
    return bool(left) and left == norm_heading(b.heading)


@dataclass
class Run:
    """One pairing of two act versions."""

    a_act: str
    b_act: str
    a_version: str
    b_version: str
    a: list[Item]
    b: list[Item]
    scored: Scored
    best_a: dict[int, tuple[int, float]]
    best_b: dict[int, tuple[int, float]]
    pairs: list[tuple[int, int, float]]
    seconds: float

    def at(self, floor: float) -> list[tuple[int, int, float]]:
        return [pair for pair in self.pairs if pair[2] >= floor]


def run_pairs(
    adapter: EuCorpusAdapter, a_act: str, b_act: str, a_version: str, b_version: str
) -> Run:
    a_tree = tree_of(adapter, a_act, a_version)
    b_tree = tree_of(adapter, b_act, b_version)
    a = [item_of(node) for node in a_tree.roots]
    b = [item_of(node) for node in b_tree.roots]
    started = time.perf_counter()
    scored = score(a, b, LOWEST_FLOOR)
    best_a, best_b = bests(scored, a, b)
    pairs = mutual(best_a, best_b)
    seconds = time.perf_counter() - started
    return Run(a_act, b_act, a_version, b_version, a, b, scored, best_a, best_b, pairs, seconds)


def char_ratio(a: Item, b: Item) -> float:
    head, tail = a.text[:RENUMBER_PREFIX_LIMIT], b.text[:RENUMBER_PREFIX_LIMIT]
    return difflib.SequenceMatcher(None, head, tail, autojunk=False).ratio()


def char_best(item: Item, start: Item, others: Sequence[Item]) -> tuple[Item, float]:
    """The character form's best match for `item`, pruned by its own upper bounds."""
    best, best_ratio = start, char_ratio(item, start)
    head = item.text[:RENUMBER_PREFIX_LIMIT]
    for other in others:
        if other.kind != item.kind or other is start:
            continue
        matcher = difflib.SequenceMatcher(
            None, head, other.text[:RENUMBER_PREFIX_LIMIT], autojunk=False
        )
        if matcher.real_quick_ratio() < best_ratio or matcher.quick_ratio() < best_ratio:
            continue
        ratio = matcher.ratio()
        if (-ratio, other.location) < (-best_ratio, best.location):
            best, best_ratio = other, ratio
    return best, best_ratio


# --------------------------------------------------------------------------- the floor


def agreement_table(run: Run) -> list[tuple[float, int, int, float]]:
    rows = []
    for floor in CANDIDATE_FLOORS:
        kept = run.at(floor)
        agree = sum(1 for i, j, _ in kept if headings_equal(run.a[i], run.b[j]))
        rows.append((floor, len(kept), agree, agree / len(kept) if kept else 0.0))
    return rows


def floor_of(run: Run) -> tuple[float, float, int, bool]:
    """The rule: lowest floor >= 0.50 with heading agreement >= 0.95, else 0.90."""
    table = agreement_table(run)
    for floor, count, _, share in table:
        if floor >= FLOOR_FROM and count and share >= AGREEMENT:
            return floor, share, count, True
    for floor, count, _, share in table:
        if floor == FALLBACK_FLOOR:
            return floor, share, count, False
    raise AssertionError("the candidate floors include the fallback")


# --------------------------------------------------------------------------- children


def align(a: ProvisionNode, b: ProvisionNode, floor: float) -> list[tuple[str, str, float]]:
    """Descendants of a pair aligned level by level, kind with kind, mutual-best at `floor`."""
    left = [item_of(child) for child in a.children]
    right = [item_of(child) for child in b.children]
    if not left or not right:
        return []
    scored = score(left, right, floor)
    best_left, best_right = bests(scored, left, right)
    aligned: list[tuple[str, str, float]] = []
    for i, j, ratio in mutual(best_left, best_right):
        aligned.append((left[i].location, right[j].location, ratio))
        aligned.extend(align(left[i].node, right[j].node, floor))
    return aligned


# --------------------------------------------------------------------------- the record


def entries(record: Path, act: str) -> list[ChangelogEntry]:
    found = []
    for path in sorted((record / "eu" / act / "changes").glob("*.json")):
        found.append(ChangelogEntry.model_validate_json(path.read_bytes()))
    return found


def coordinates_on_children(
    run: Run, floor: float, record: Path, children: dict[str, list[tuple[str, str, float]]]
) -> None:
    """How each act's changed coordinates fall on the aligned children of its twinned units."""
    for act, side in ((run.a_act, 0), (run.b_act, 1)):
        twinned = {
            (run.a[i].location if side == 0 else run.b[j].location): run.a[i].location
            for i, j, _ in run.at(floor)
        }
        aligned = {pair[side] for rows in children.values() for pair in rows}
        counts: Counter[str] = Counter()
        for entry in entries(record, act):
            for emitted in entry.changes:
                change = emitted.change
                unit = change.location.top_level.canonical
                if unit not in twinned:
                    counts["changes whose unit has no twin at the floor"] += 1
                    continue
                counts["changes whose unit has a twin"] += 1
                coordinates = [c for c in change.changed_within if c.depth > 1]
                if not coordinates:
                    counts["  unit-level, no coordinate below the unit"] += 1
                for coordinate in coordinates:
                    segments = coordinate.segments
                    hit = any(
                        " ".join(str(s) for s in segments[:depth]) in aligned
                        for depth in range(len(segments), 1, -1)
                    )
                    key = "maps to an aligned child" if hit else "maps to the unit only"
                    counts[f"  coordinate {key}"] += 1
        print(f"{act}: changed coordinates of the record against the aligned children")
        for name in (
            "changes whose unit has no twin at the floor",
            "changes whose unit has a twin",
            "  unit-level, no coordinate below the unit",
            "  coordinate maps to an aligned child",
            "  coordinate maps to the unit only",
        ):
            print(f"  {name:50s} {counts[name]}")
        print()


# --------------------------------------------------------------------------- passages


@dataclass(frozen=True)
class Passage:
    a: str
    b: str
    cut: bool


def cut(text: str) -> tuple[str, bool]:
    if len(text) <= PASSAGE_CHARS:
        return text, False
    return text[:PASSAGE_CHARS] + CUT, True


def passages(a: Item, b: Item) -> tuple[list[Passage], int, int]:
    """Each non-equal word opcode with its context, and the differing characters alone."""
    matcher = difflib.SequenceMatcher(None, list(a.words), list(b.words), autojunk=False)
    found = []
    bare_a = bare_b = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        bare_a += len(" ".join(a.words[i1:i2]))
        bare_b += len(" ".join(b.words[j1:j2]))
        left, left_cut = cut(" ".join(a.words[max(0, i1 - CONTEXT_WORDS) : i2 + CONTEXT_WORDS]))
        right, right_cut = cut(" ".join(b.words[max(0, j1 - CONTEXT_WORDS) : j2 + CONTEXT_WORDS]))
        found.append(Passage(left, right, left_cut or right_cut))
    return found, bare_a, bare_b


def over_share(left: int, right: int, a: Item, b: Item) -> bool:
    return left > WITHHELD_SHARE * len(a.text) or right > WITHHELD_SHARE * len(b.text)


def page_figures(run: Run, floor: float) -> None:
    identical = withheld = pages = over_cap = withheld_shown = withheld_bare = 0
    largest: tuple[int, str] = (0, "")
    rows = []
    for i, j, ratio in run.at(floor):
        a, b = run.a[i], run.b[j]
        if a.text == b.text:
            identical += 1
            rows.append(f"  {a.location:10s} {b.location:10s} {ratio:.3f}  identical, no page")
            continue
        pages += 1
        found, bare_a, bare_b = passages(a, b)
        left = sum(len(p.a) for p in found)
        right = sum(len(p.b) for p in found)
        held = over_share(left, right, a, b)
        withheld += held
        over_cap += len(found) > MAX_PASSAGES
        shown = found[:MAX_PASSAGES]
        withheld_shown += over_share(
            sum(len(p.a) for p in shown), sum(len(p.b) for p in shown), a, b
        )
        withheld_bare += over_share(bare_a, bare_b, a, b)
        excerpt = 0 if held else sum(len(p.a) + len(p.b) for p in shown)
        if excerpt > largest[0]:
            largest = (excerpt, f"{a.location} / {b.location}")
        rows.append(
            f"  {a.location:10s} {b.location:10s} {ratio:.3f}  passages {len(found):4d}  "
            f"share {left / max(1, len(a.text)):.3f} / {right / max(1, len(b.text)):.3f}  "
            f"bare {bare_a / max(1, len(a.text)):.3f} / {bare_b / max(1, len(b.text)):.3f}  "
            + ("withheld" if held else f"excerpt {excerpt:6d} chars")
        )
    print(f"pages at the floor {floor:.2f} (passages: {CONTEXT_WORDS} context words, ")
    print(f"  {PASSAGE_CHARS}-char cut, at most {MAX_PASSAGES} shown, withheld above ")
    print(f"  {WITHHELD_SHARE:.0%} of either side's comparison text over every passage)")
    print(f"  pairs at the floor               {identical + pages}")
    print(f"  identical, no page               {identical}")
    print(f"  pages                            {pages}")
    print(f"    withheld (differ too widely)   {withheld}")
    print(f"    with passages shown            {pages - withheld}")
    print(f"    with more than {MAX_PASSAGES} passages     {over_cap}")
    print("  withheld under two other readings of the share, for comparison:")
    print(f"    the {MAX_PASSAGES} shown passages only        {withheld_shown}")
    print(f"    the differing words alone, no context  {withheld_bare}")
    print(f"  largest shown excerpt            {largest[0]} chars ({largest[1]})")
    print()
    for row in rows:
        print(row)
    print()


# --------------------------------------------------------------------------- subcommands


def default_runs(
    adapter: EuCorpusAdapter, a_act: str, b_act: str, fetch: bool
) -> tuple[tuple[str, str], tuple[str, str] | None]:
    """Newest each, and the newest date both acts have when that differs."""
    a_versions, b_versions = newest(adapter, a_act, fetch), newest(adapter, b_act, fetch)
    primary = (a_versions[-1], b_versions[-1])
    a_dates = {v.split("-")[1]: v for v in a_versions}
    b_dates = {v.split("-")[1]: v for v in b_versions}
    common = sorted(set(a_dates) & set(b_dates))
    if not common:
        return primary, None
    same = (a_dates[common[-1]], b_dates[common[-1]])
    return primary, (None if same == primary else same)


def print_run(run: Run) -> None:
    articles = sum(1 for i, _, _ in run.pairs if run.a[i].kind == "AR")
    print(f"== {run.a_act} {run.a_version} against {run.b_act} {run.b_version}")
    print(f"units                 {len(run.a)} against {len(run.b)}")
    print(f"same-kind pairs       {run.scored.candidates}")
    print(f"  skipped by real_quick_ratio < {LOWEST_FLOOR:.2f}  {run.scored.skipped_real_quick}")
    print(f"  skipped by quick_ratio < {LOWEST_FLOOR:.2f}       {run.scored.skipped_quick}")
    computed = run.scored.candidates - run.scored.skipped_real_quick - run.scored.skipped_quick
    print(f"  ratio() computed                   {computed}")
    print(f"  at or above {LOWEST_FLOOR:.2f}                   {len(run.scored.ratios)}")
    print(f"mutual-best pairs     {len(run.pairs)} ({articles} article, the rest annex)")
    print(f"word-ratio seconds    {run.seconds:.1f} (all pairs, this machine, one process)")
    started = time.perf_counter()
    disagree_a = disagree_b = 0
    lines = []
    for i, j, ratio in run.pairs:
        a, b = run.a[i], run.b[j]
        best_b, chars = char_best(a, b, run.b)
        best_a, _ = char_best(b, a, run.a)
        disagree_a += best_b is not b
        disagree_b += best_a is not a
        mark = "" if best_b is b and best_a is a else "  char-best differs: "
        if best_b is not b:
            mark += f"A->{best_b.location} "
        if best_a is not a:
            mark += f"B->{best_a.location}"
        lines.append(
            f"  {a.location:10s} {b.location:10s} word {ratio:.3f}  char {chars:.3f}  "
            f"headings_equal {headings_equal(a, b)!s:5s}  "
            f"{a.heading or '-'!s} | {b.heading or '-'!s}{mark.rstrip()}"
        )
    seconds = time.perf_counter() - started
    print(
        f"character form ({RENUMBER_PREFIX_LIMIT}-char prefix) chooses a different best match: "
        f"for {disagree_a} of {len(run.pairs)} A units, {disagree_b} of {len(run.pairs)} B units "
        f"({seconds:.1f}s)"
    )
    print()
    print("mutual-best pairs, A order: A, B, word ratio, char ratio, headings_equal, headings")
    for row in lines:
        print(row)
    print()
    paired_a = {i for i, _, _ in run.pairs}
    paired_b = {j for _, j, _ in run.pairs}
    for label, items, others, best, paired in (
        ("A", run.a, run.b, run.best_a, paired_a),
        ("B", run.b, run.a, run.best_b, paired_b),
    ):
        unpaired = [index for index in range(len(items)) if index not in paired]
        print(f"unpaired {label} units ({len(unpaired)}): unit, best candidate, ratio")
        for index in unpaired:
            found = best.get(index)
            if found is None:
                print(f"  {items[index].location:10s} none at or above {LOWEST_FLOOR:.2f}")
            else:
                print(
                    f"  {items[index].location:10s} {others[found[0]].location:10s} {found[1]:.3f}"
                )
        print()


def cmd_pairs(args: argparse.Namespace) -> int:
    print_header(fetch=args.fetch, record=None)
    adapter = make_adapter(fetch=args.fetch)
    if args.version_a and args.version_b:
        runs = [(version_id(args.a, args.version_a), version_id(args.b, args.version_b))]
    else:
        primary, same = default_runs(adapter, args.a, args.b, args.fetch)
        runs = [primary] + ([same] if same else [])
    for a_version, b_version in runs:
        print_run(run_pairs(adapter, args.a, args.b, a_version, b_version))
    adapter.close()
    return 0


def print_floor(run: Run) -> float:
    print(f"== {run.a_act} {run.a_version} against {run.b_act} {run.b_version}")
    print(f"{'f':>5s} {'pairs >= f':>10s} {'headings equal':>15s} {'agreement':>10s}")
    for floor, count, agree, share in agreement_table(run):
        print(f"{floor:5.2f} {count:10d} {agree:15d} {share:10.3f}")
    floor, share, count, reached = floor_of(run)
    print()
    if not reached:
        print(f"no candidate floor from {FLOOR_FROM:.2f} reaches {AGREEMENT}; the rule gives 0.90")
    return floor


def cmd_floor(args: argparse.Namespace) -> int:
    print_header(fetch=args.fetch, record=args.record)
    adapter = make_adapter(fetch=args.fetch)
    primary, same = default_runs(adapter, MDR, IVDR, args.fetch)
    run = run_pairs(adapter, MDR, IVDR, *primary)
    if same is not None:
        print("cross-check on the newest version date both acts have:")
        print_floor(run_pairs(adapter, MDR, IVDR, *same))
    adapter.close()
    floor = print_floor(run)
    _, share, count, _ = floor_of(run)
    print(
        f"FLOOR: {floor:.2f} (heading agreement {share:.3f} over {count} pairs, "
        f"measured {args.measured_on})"
    )
    print(f"  over {run.a_act} {run.a_version} and {run.b_act} {run.b_version}")
    print()
    kept = run.at(floor)
    children: dict[str, list[tuple[str, str, float]]] = {}
    for i, j, _ in kept:
        children[run.a[i].location] = align(run.a[i].node, run.b[j].node, floor)
    total = sum(len(rows) for rows in children.values())
    print(f"children aligned below the {len(kept)} pairs at the floor: {total}")
    for i, j, _ in kept:
        below_a = sum(1 for _ in run.a[i].node.walk()) - 1
        rows = children[run.a[i].location]
        print(f"  {run.a[i].location:10s} {run.b[j].location:10s} {len(rows):4d} of {below_a}")
    print()
    if args.record is not None:
        coordinates_on_children(run, floor, args.record, children)
    page_figures(run, floor)
    return 0


def cmd_divergence(args: argparse.Namespace) -> int:
    print_header(fetch=args.fetch, record=args.record)
    adapter = make_adapter(fetch=args.fetch)
    primary, _ = default_runs(adapter, MDR, IVDR, args.fetch)
    run = run_pairs(adapter, MDR, IVDR, *primary)
    adapter.close()
    floor = args.floor if args.floor is not None else floor_of(run)[0]
    kept = run.at(floor)
    print(f"pairs at the floor {floor:.2f} over {run.a_version} and {run.b_version}: {len(kept)}")
    twin_of = {
        MDR: {run.a[i].location: run.b[j].location for i, j, _ in kept},
        IVDR: {run.b[j].location: run.a[i].location for i, j, _ in kept},
    }
    record = {act: entries(args.record, act) for act in (MDR, IVDR)}
    one_sided: list[str] = []
    two_sided: list[str] = []
    counted: set[tuple[str, str, str]] = set()
    instruments: set[str] = set()
    no_event = Counter[str]()
    for a_act, b_act in ((MDR, IVDR), (IVDR, MDR)):
        by_instrument: dict[str, list[ChangelogEntry]] = defaultdict(list)
        for entry in record[b_act]:
            for key in amending_keys(entry):
                by_instrument[key].append(entry)
        for entry in record[a_act]:
            for emitted in entry.changes:
                change = emitted.change
                unit = change.location.top_level.canonical
                twin = twin_of[a_act].get(unit)
                if twin is None:
                    continue
                for act in change.amending_acts:
                    events = by_instrument.get(act.key, [])
                    if not events:
                        no_event[act.key] += 1
                        continue
                    touched = [
                        sorted({c.change.location.top_level.canonical for c in e.changes})
                        for e in events
                    ]
                    row = (
                        f"  {a_act} {entry.to_version} {change.location.canonical:8s} "
                        f"by {act.key}; twin {b_act} {twin}; {b_act} events of {act.key}: "
                        + "; ".join(
                            f"{e.to_version} touched {', '.join(units)}"
                            for e, units in zip(events, touched, strict=True)
                        )
                    )
                    if any(twin in units for units in touched):
                        two_sided.append(row)
                    else:
                        one_sided.append(row)
                        counted.add((a_act, str(entry.to_version), change.location.canonical))
                        instruments.add(act.key)
    print()
    print(f"one-sided twin changes ({len(one_sided)} rows, {len(counted)} changes):")
    for row in one_sided:
        print(row)
    print()
    print(f"two-sided: the same amending act changed both twins ({len(two_sided)} rows):")
    for row in two_sided:
        print(row)
    print()
    print("twinned changes whose amending act made no event of the other act in the record:")
    for key, count in sorted(no_event.items()):
        print(f"  {key}  {count}")
    print()
    met = len(counted) >= BAR_CHANGES and len(instruments) >= BAR_INSTRUMENTS
    verdict = "met" if met else "not met"
    print(
        f"BAR: {verdict} ({len(counted)} changes, {len(instruments)} instruments; the bar is "
        f"{BAR_CHANGES} changes from {BAR_INSTRUMENTS} instruments, measured {args.measured_on})"
    )
    return 0


def shingles(words: Sequence[str]) -> set[int]:
    return {
        hash(" ".join(words[k : k + SHINGLE_WORDS])) for k in range(len(words) - SHINGLE_WORDS + 1)
    }


def cmd_screen(args: argparse.Namespace) -> int:
    print_header(fetch=False, record=None)
    adapter = make_adapter(fetch=False)
    held = cached_packages(cache_root())
    acts: dict[str, tuple[str, list[Item]]] = {}
    for act, items in held.items():
        try:
            fetched = adapter.fetch_version(
                ActId(corpus="eu", key=act), VersionId(items[-1].version)
            )
        except FixtureMissing:
            print(f"{act} {items[-1].version}: not served offline")
            continue
        if not isinstance(fetched, ProvisionTree):
            print(f"{act} {items[-1].version}: {type(fetched).__name__}")
            continue
        acts[act] = (items[-1].version, [item_of(node) for node in fetched.roots])
    primary, _ = default_runs(adapter, MDR, IVDR, False)
    reference = run_pairs(adapter, MDR, IVDR, *primary)
    floor = args.floor if args.floor is not None else floor_of(reference)[0]
    adapter.close()
    started = time.perf_counter()
    units: list[tuple[str, Item, set[int]]] = []
    for act in sorted(acts):
        for item in acts[act][1]:
            units.append((act, item, shingles(item.words)))
    postings: dict[int, list[int]] = defaultdict(list)
    for index, (_, _, found) in enumerate(units):
        for shingle in found:
            postings[shingle].append(index)
    capped = 0
    shared: Counter[tuple[int, int]] = Counter()
    for members in postings.values():
        if len(members) > SHINGLE_DF_CAP:
            capped += 1
            continue
        for x, left in enumerate(members):
            for right in members[x + 1 :]:
                if (
                    units[left][0] != units[right][0]
                    and units[left][1].kind == units[right][1].kind
                ):
                    shared[(left, right)] += 1
    screened: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for (left, right), count in shared.items():
        size = len(units[left][2]) + len(units[right][2]) - count
        if size and count / size >= JACCARD:
            screened[(units[left][0], units[right][0])].append((left, right))
    screen_seconds = time.perf_counter() - started
    print(f"acts read            {len(acts)} (newest cached version each)")
    print(f"units                {len(units)}")
    print(f"distinct shingles    {len(postings)} ({SHINGLE_WORDS} words)")
    print(f"  set aside by the document-frequency cap of {SHINGLE_DF_CAP} units: {capped}")
    print(f"cross-act same-kind unit pairs sharing a shingle  {len(shared)}")
    print(
        f"  of them with Jaccard >= {JACCARD}                  {sum(map(len, screened.values()))}"
    )
    print(f"screen seconds       {screen_seconds:.1f}")
    print(f"floor                {floor:.2f}")
    print()
    started = time.perf_counter()
    matcher = difflib.SequenceMatcher(None, autojunk=False)
    results = []
    for (left_act, right_act), candidates in sorted(screened.items()):
        ratios: dict[tuple[int, int], float] = {}
        for left, right in candidates:
            a, b = units[left][1], units[right][1]
            matcher.set_seqs(list(a.words), list(b.words))
            if matcher.real_quick_ratio() < floor or matcher.quick_ratio() < floor:
                continue
            ratio = matcher.ratio()
            if ratio >= floor:
                ratios[(left, right)] = ratio
        pairs = mutual_of(ratios, units)
        articles = [p for p in pairs if units[p[0]][1].kind == "AR"]
        results.append((left_act, right_act, len(candidates), pairs, articles))
    print(f"word-ratio seconds over the screened pairs: {time.perf_counter() - started:.1f}")
    full = {(reference.a[i].location, reference.b[j].location) for i, j, _ in reference.at(floor)}
    found_here = {
        (units[x][1].location, units[y][1].location)
        for left_act, right_act, _, pairs, _ in results
        if (left_act, right_act) == (MDR, IVDR)
        for x, y, _ in pairs
    }
    print(
        f"calibration on {MDR} and {IVDR}: the screen finds {len(found_here & full)} of the "
        f"{len(full)} pairs the all-pairs run finds at the floor, and {len(found_here - full)} "
        "it does not"
    )
    print()
    print(
        f"{'act A':10s} {'act B':10s} {'screened':>8s} {'mutual >= floor':>15s} "
        f"{'articles':>8s}  verdict (>= {TWIN_RULE_PAIRS} article pairs enters the twins list)"
    )
    for left_act, right_act, count, pairs, articles in results:
        verdict = "enters" if len(articles) >= TWIN_RULE_PAIRS else "below the rule"
        print(
            f"{left_act:10s} {right_act:10s} {count:8d} {len(pairs):15d} {len(articles):8d}  "
            f"{verdict}"
        )
    print()
    print("mutual-best pairs at the floor, per act pair (unit A, unit B, ratio):")
    for left_act, right_act, _, pairs, _ in results:
        if not pairs:
            continue
        shown = ", ".join(
            f"{units[x][1].location}/{units[y][1].location} {r:.2f}" for x, y, r in pairs
        )
        print(f"  {left_act} {right_act}: {shown}")
    return 0


def mutual_of(
    ratios: dict[tuple[int, int], float], units: Sequence[tuple[str, Item, set[int]]]
) -> list[tuple[int, int, float]]:
    best_left: dict[int, tuple[int, float]] = {}
    best_right: dict[int, tuple[int, float]] = {}
    for (i, j), ratio in ratios.items():
        held = best_left.get(i)
        if held is None or (-ratio, units[j][1].location) < (-held[1], units[held[0]][1].location):
            best_left[i] = (j, ratio)
        held = best_right.get(j)
        if held is None or (-ratio, units[i][1].location) < (-held[1], units[held[0]][1].location):
            best_right[j] = (i, ratio)
    return sorted(
        (i, j, r) for i, (j, r) in best_left.items() if best_right.get(j, (-1, 0.0))[0] == i
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--measured-on", default="2026-10-19", help="the date a line states")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("pairs", help="every same-kind unit pair, scored and timed")
    one.add_argument("--a", default=MDR)
    one.add_argument("--b", default=IVDR)
    one.add_argument("--version-a")
    one.add_argument("--version-b")
    one.add_argument("--fetch", action="store_true")
    two = commands.add_parser("floor", help="the floor rule, children, coordinates and pages")
    two.add_argument("--record", type=Path)
    two.add_argument("--fetch", action="store_true")
    three = commands.add_parser("divergence", help="one-sided and two-sided twin changes")
    three.add_argument("--record", type=Path, required=True)
    three.add_argument("--floor", type=float)
    three.add_argument("--fetch", action="store_true")
    four = commands.add_parser("screen", help="every pair of cached acts, screened then scored")
    four.add_argument("--floor", type=float)
    args = parser.parse_args(None if argv is None else list(argv))
    handlers = {
        "pairs": cmd_pairs,
        "floor": cmd_floor,
        "divergence": cmd_divergence,
        "screen": cmd_screen,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
