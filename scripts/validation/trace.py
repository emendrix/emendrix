#!/usr/bin/env python
"""Three-way validation trace for one act and one consolidated-version pair.

One-off validation code, kept so the numbers it measured stay reproducible. It
is deliberately *not* production code: stdlib + httpx, no package structure, no
type-checking, no tests. `src/emendrix/` reimplements all of it properly.

It computes, for one amended act and one pair of consolidated versions:

  signal 1  structural Formex diff of the two consolidated texts
  signal 2  CELLAR modification annotations from the amended act's branch notice,
            restricted to amendments whose START_OF_VALIDITY falls in the window
  signal 3  a naive parse of the amending acts' own instruction prose

and reports set agreement (P/R/F1 of signal 1 against signal 2) at
top-level-provision granularity.

Usage::

    python scripts/validation/trace.py versions 32006R1907
    python scripts/validation/trace.py trace 32017R0745 20170505 20200424

Everything fetched is cached under `scripts/validation/.cache/` (gitignored);
re-runs are offline. Verified against live endpoints on 2026-08-05.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
import xml.etree.ElementTree as ET  # types only; parsing goes through `defusedxml`
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from defusedxml.ElementTree import fromstring

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
RESULTS = HERE / "results"
BASE = "http://publications.europa.eu"
HEADERS = {"User-Agent": "emendrix-validation/0.1 (portfolio project; polite, cached)"}
POLITE_DELAY_S = 3.0
ORIGINAL = "original"  # version tag meaning "the act as published in the OJ"

# Instruction verbs used by EU drafting; the naive signal-3 parser keys off these.
VERBS = re.compile(
    r"\b(replaced|inserted|deleted|added|amended|repealed|substituted)\b", re.IGNORECASE
)
ART_REF = re.compile(r"\bArticle\s+(\d+\s*[a-z]?)\b")
ANN_REF = re.compile(r"\bAnnex\s+([IVXL]+)\b")


# --------------------------------------------------------------------------- io


def fetch(url: str, accept: str, name: str) -> bytes:
    """GET `url` with content negotiation, caching the body under .cache/<name>."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if path.exists():
        return path.read_bytes()
    import httpx  # imported late: this script is the only thing that needs it

    time.sleep(POLITE_DELAY_S)
    headers = {**HEADERS, "Accept": accept, "Accept-Language": "eng"}
    with httpx.Client(follow_redirects=True, timeout=300.0) as client:
        response = client.get(url, headers=headers)
    if response.status_code != 200:
        raise LookupError(f"{response.status_code} for {url}")
    path.write_bytes(response.content)
    return response.content


def act_code(celex: str) -> str:
    """32017R0745 -> 2017R0745 (the 'consolidation' URI form of an act)."""
    return celex[1:]


def consolidated_celex(celex: str, version: str) -> str:
    """(32017R0745, 20200424) -> 02017R0745-20200424."""
    return f"0{celex[1:]}-{version}"


def try_candidates(candidates: list[tuple[str, str]]) -> list[ET.Element]:
    errors = []
    for url, name in candidates:
        try:
            blob = fetch(url, "application/zip", name)
        except LookupError as exc:
            errors.append(str(exc))
            continue
        return documents(blob)
    raise LookupError(" ; ".join(errors))


def fetch_consolidated(celex: str, version: str) -> list[ET.Element]:
    """Fetch a consolidated version's Formex 4 zip; return its document roots.

    Two addressing schemes are live and neither covers everything (2026-08-05):
    consolidations built from ~2018 on answer on
    `/resource/consolidation/<act-code>%2F<date>`, older ones only on
    `/resource/celex/<consolidated-celex>`.
    """
    cons = consolidated_celex(celex, version)
    return try_candidates(
        [
            (
                f"{BASE}/resource/consolidation/{act_code(celex)}%2F{version}.ENG.fmx4",
                f"{cons}.cons.fmx4.zip",
            ),
            (f"{BASE}/resource/celex/{cons}.ENG.fmx4", f"{cons}.celex.fmx4.zip"),
        ]
    )


def act_resource_paths(celex: str) -> list[str]:
    """Resource paths an act's own Formex may answer on, best guess first.

    32024R1689 -> ['celex/32024R1689', 'oj/L_202401689']. Acts published in the
    reformed OJ (from 2023-10) only answer on the OJ identifier.
    """
    year, number = celex[1:5], celex[6:].lstrip("0")
    return [f"celex/{celex}", f"oj/L_{year}{int(number):05d}"]


def fetch_act(resource_paths: list[str]) -> list[ET.Element]:
    """Fetch an act's own Formex 4 by any of its resource paths.

    Acts published in the reformed OJ (from 2023-10) do **not** answer on
    `/resource/celex/<celex>.ENG.fmx4`; only the OJ identifier resolves, e.g.
    `/resource/oj/L_202401860.ENG.fmx4`. Verified 2026-08-05.
    """
    return try_candidates(
        [
            (f"{BASE}/resource/{path}.ENG.fmx4", f"{path.replace('/', '_')}.ENG.fmx4.zip")
            for path in resource_paths
        ]
    )


def documents(blob: bytes) -> list[ET.Element]:
    """Unpack a Formex zip into [the act, *its annex documents].

    A Formex package is a bag of documents: a table of contents, a `.doc.xml`
    wrapper, scanned `.tif` pages, and, in an act as published in the OJ, one
    `ANNEX` document per annex. Regulation 1272/2008 ships 98 members, the largest
    of which is an annex, so 'largest XML' is the wrong rule for finding the act:
    it is the document whose root is `ACT`/`CONS.ACT` and which carries
    `ENACTING.TERMS`. A *consolidated* act instead carries its annexes inline as
    `CONS.ANNEX` elements, so the two shapes must both be handled. Verified
    2026-08-05 on 32024R1689 (7 separate ANNEX documents) and 02024R1689-20260727.
    """
    act: ET.Element | None = None
    annexes: list[ET.Element] = []
    fallback: ET.Element | None = None
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = [
            info.filename
            for info in sorted(archive.infolist(), key=lambda i: -i.file_size)
            if info.filename.endswith(".xml") and not info.filename.endswith(".doc.xml")
        ]
        for name in names:
            root = fromstring(archive.read(name))
            if root.tag == "ANNEX":
                annexes.append(root)
            elif (
                act is None
                and root.tag in {"ACT", "CONS.ACT", "CONS.DOC"}
                and root.find(".//ENACTING.TERMS") is not None
            ):
                act = root
            elif fallback is None:
                fallback = root
    act = act if act is not None else fallback
    if act is None:
        raise LookupError("no Formex document in archive")
    return [act, *annexes]


# ------------------------------------------------------------------- signal 1


def article_key(identifier: str) -> str:
    """Formex ARTICLE IDENTIFIER '004A' -> canonical unit key 'AR 4a'."""
    match = re.fullmatch(r"0*(\d+)([A-Za-z]*)", identifier.strip())
    if match is None:
        return f"AR {identifier.strip()}"
    return f"AR {int(match.group(1))}{match.group(2).lower()}"


def flatten(element: ET.Element) -> str:
    """Descendant text, with a separator inserted at every element boundary.

    `"".join(el.itertext())` is markup-sensitive, and Formex generations differ in
    whether adjacent inline elements carry surrounding whitespace: on the REACH
    2008->2009 pair that difference alone fabricated 110 false 'modified' articles
    (measured 2026-08-05). Joining on a separator and then squashing removes it.
    Production code must keep the verbatim text separately; this form is for
    comparison only.

    `BIB.INSTANCE` is skipped: standalone `ANNEX` documents carry a publication
    metadata block (OJ page numbers, document date) that is not provision text and
    differs between the OJ act and its consolidation.
    """
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        if node.tag == "BIB.INSTANCE":
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(element)
    return " ".join(parts)


def annex_key(annex: ET.Element) -> str | None:
    """`CONS.ANNEX` -> 'AN VI'. None for the 'LIST OF ANNEXES' table of contents.

    The number lives in `TITLE/TI`; the whole `TITLE` also contains the `STI`
    subtitle, which in the 2008 Formex generation runs into the number without a
    separator ('ANNEX IGENERAL PROVISIONS ...').
    """
    title = annex.find("TITLE/TI")
    if title is None:
        return None
    match = re.search(r"\bANNEX\s+([IVXL]+|\d+[A-Za-z]?)\b", squash(flatten(title)).upper())
    return f"AN {match.group(1)}" if match else None


def units(roots: list[ET.Element]) -> dict[str, str]:
    """Map canonical top-level unit key -> comparable text of that unit."""
    out: dict[str, str] = {}
    for root in roots:
        for article in root.iter("ARTICLE"):
            identifier = article.get("IDENTIFIER")
            if identifier and article not in quoted_articles(root):
                out[article_key(identifier)] = flatten(article)
        for annex in [*root.iter("CONS.ANNEX"), *([root] if root.tag == "ANNEX" else [])]:
            key = annex_key(annex)
            if key:
                out[key] = flatten(annex)
    return out


def squash(text: str) -> str:
    """Whitespace-only normalisation, used for comparison and never for storage."""
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Diff:
    inserted: set[str]
    deleted: set[str]
    modified: set[str]
    unchanged: set[str]

    @property
    def touched(self) -> set[str]:
        return self.inserted | self.deleted | self.modified


def structural_diff(before: dict[str, str], after: dict[str, str]) -> Diff:
    keys_before, keys_after = set(before), set(after)
    common = keys_before & keys_after
    return Diff(
        inserted=keys_after - keys_before,
        deleted=keys_before - keys_after,
        modified={k for k in common if squash(before[k]) != squash(after[k])},
        unchanged={k for k in common if squash(before[k]) == squash(after[k])},
    )


# ------------------------------------------------------------------- signal 2

BRACE = re.compile(r"\{(\w+)\|[^}]*\}")


def normalise_location(raw: str) -> str:
    """'{AR|.../fd_370/AR} 52 {PA|...} 4' -> 'AR 52 PA 4'.

    The raw CELLAR value is a `{code|authority-uri}` template. Legacy notices mix
    expanded and bare codes in the same string, so this only strips the braces.
    """
    return squash(BRACE.sub(r"\1", raw))


def location_unit(location: str) -> str | None:
    """Top-level unit of a normalised location string, or None if unkeyable."""
    match = re.match(r"(AR|AN)\s+(\S+)", location)
    if match is None:
        return None
    kind, number = match.groups()
    if kind == "AR":
        # 'AR 3.20' is Article 3 point 20; the unit is Article 3.
        number = number.split(".")[0]
        return f"AR {number.lower()}"
    return f"AN {number.upper()}"


@dataclass(frozen=True)
class Annotation:
    amending_act: str
    role: str
    location: str
    unit: str | None
    start_of_validity: str


def iso(date_text: str) -> str:
    """CELLAR emits both '2008-10-12' and '2007/11/23'. Normalise to ISO."""
    return date_text.strip().replace("/", "-")


def annotations(branch_root: ET.Element) -> tuple[list[Annotation], dict[str, list[str]]]:
    """Modification annotations, plus act CELEX -> its resolvable resource paths."""
    work = branch_root.find("WORK")
    if work is None:
        return [], {}
    out: list[Annotation] = []
    paths: dict[str, list[str]] = {}
    for link in work.findall("RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL"):
        uris = [e.text or "" for e in link.findall("SAMEAS/URI/VALUE")]
        celex = next(
            (u.rsplit("/", 1)[-1] for u in uris if "/celex/" in u),
            uris[0].rsplit("/", 1)[-1] if uris else "?",
        )
        paths[celex] = [
            u.split("/resource/", 1)[1] for u in uris if "/resource/" in u and "/eli/" not in u
        ]
        for annotation in link.findall("ANNOTATION"):
            role = (annotation.findtext("ROLE2") or "").split("/")[-1].rstrip("}") or "?"
            location = normalise_location(
                annotation.findtext("REFERENCE_TO_MODIFIED_LOCATION") or ""
            )
            start = annotation.find("START_OF_VALIDITY")
            start_text = ""
            if start is not None:
                start_text = start.findtext("VALUE") or (start.text or "")
            out.append(Annotation(celex, role, location, location_unit(location), iso(start_text)))
    return out, paths


# ------------------------------------------------------------------- signal 3


def act_number_forms(celex: str) -> list[str]:
    """32017R0745 -> ['2017/745', '745/2017'] (EU numbering flipped in 2015)."""
    year, number = celex[1:5], celex[6:].lstrip("0")
    return [f"{year}/{number}", f"{number}/{year}"]


def quoted_articles(scope: ET.Element) -> set[ET.Element]:
    """ARTICLE elements nested inside another ARTICLE, i.e. quoted replacement text.

    This is where an inserted article's identifier lives: the instruction prose says
    'the following Article is inserted' without the number.
    """
    return {
        inner
        for outer in scope.iter("ARTICLE")
        for inner in outer.iter("ARTICLE")
        if inner is not outer
    }


def instruction_scope(amending_root: ET.Element, amended_celex: str) -> list[ET.Element]:
    """The amending act's own articles that target `amended_celex`, else all of them.

    An amending act often amends several regulations in parallel articles
    ('Article 1 - Amendments to Regulation (EU) 2017/745'). Scanning the whole act
    would attribute another regulation's instructions to this one.
    """
    terms = amending_root.find("ENACTING.TERMS")
    if terms is None:
        return [amending_root]
    # Articles are direct children in small acts and nested under TITLE/CHAPTER
    # (`GR.SEQ`) groupings in large ones, so `iter` rather than `findall`; articles
    # nested inside another article are quoted replacement text, not own articles.
    articles = [a for a in terms.iter("ARTICLE") if a not in quoted_articles(terms)]
    forms = act_number_forms(amended_celex)
    targeted = []
    for article in articles:
        head = squash(flatten(article))[:400]
        if VERBS.search(head) and any(form in head for form in forms):
            targeted.append(article)
    return targeted or articles or [terms]


def instruction_units(amending_root: ET.Element, amended_celex: str) -> set[str]:
    """Naive parse of an amending act's own instruction prose.

    Deliberately naive: this is the measured cross-check, not ground truth.
    An amending instruction is an enumerated item whose *lead-in clause* (the text
    before the first colon, i.e. before the quoted replacement text) contains an
    instruction verb; the provision reference is taken from that clause only.
    Insertions carry no number in the prose ('the following article is inserted:'),
    so quoted `ARTICLE` elements, an ARTICLE nested inside another ARTICLE, are
    harvested too. That is the only way inserted identifiers are recoverable.
    """
    found: set[str] = set()
    for scope in instruction_scope(amending_root, amended_celex):
        for element in scope.iter():
            if element.tag not in {"P", "NP", "ALINEA"}:
                continue
            head = squash(flatten(element)).split(":")[0]
            if not head or not VERBS.search(head):
                continue
            for number in ART_REF.findall(head):
                found.add(f"AR {number.replace(' ', '').lower()}")
            for number in ANN_REF.findall(head):
                found.add(f"AN {number.upper()}")
        for quoted in quoted_articles(scope):
            identifier = quoted.get("IDENTIFIER")
            if identifier:
                found.add(article_key(identifier))
    return found


# ---------------------------------------------------------------------- report


def prf(predicted: set[str], reference: set[str]) -> tuple[float, float, float]:
    hits = len(predicted & reference)
    precision = hits / len(predicted) if predicted else 0.0
    recall = hits / len(reference) if reference else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def order(keys: set[str]) -> list[str]:
    def sort_key(key: str) -> tuple[str, int, str]:
        kind, _, rest = key.partition(" ")
        digits = re.match(r"\d+", rest)
        return (kind, int(digits.group()) if digits else 0, rest)

    return sorted(keys, key=sort_key)


def render(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def command_versions(celex: str) -> str:
    """Inventory of consolidated versions and their ENG manifestations."""
    blob = fetch(
        f"{BASE}/resource/celex/{celex}",
        "application/xml;notice=tree",
        f"{celex}.tree.xml",
    )
    text = blob.decode("utf-8", "replace")
    formats: dict[str, set[str]] = {}
    schemes: dict[str, set[str]] = {}
    pattern_cons = rf"/consolidation/{act_code(celex)}%2F(\d{{8}})\.ENG\.(\w+)"
    pattern_celex = rf"/celex/0{celex[1:]}-(\d{{8}})\.ENG\.(\w+)"
    for pattern, scheme in ((pattern_cons, "consolidation"), (pattern_celex, "celex")):
        for version, fmt in re.findall(pattern, text):
            formats.setdefault(version, set()).add(fmt)
            schemes.setdefault(version, set()).add(scheme)
    lines = [
        f"# consolidated versions of {celex} (from notice=tree, fetched 2026-08-05)",
        "",
        f"{len(formats)} versions; ENG manifestations per version",
        "",
    ]
    missing = []
    for version in sorted(formats):
        has_fmx4 = "fmx4" in formats[version]
        if not has_fmx4:
            missing.append(version)
        lines.append(
            f"{version}  fmx4={'yes' if has_fmx4 else 'NO '} "
            f"formats={','.join(sorted(formats[version]))} "
            f"via={','.join(sorted(schemes[version]))}"
        )
    lines += [
        "",
        f"versions without an English Formex manifestation: {len(missing)}",
        f"  {', '.join(missing) if missing else '(none)'}",
    ]
    return render(lines)


def command_annotations(celex: str) -> str:
    """Full inventory of an act's CELLAR modification annotations.

    Corroboration needs the complete *observed* role and location vocabulary: authority
    tables fd_370 (locations) and fd_375 (roles) publish no English labels, so the
    only honest source is what the corpus actually emits.
    """
    branch = fromstring(
        fetch(
            f"{BASE}/resource/celex/{celex}",
            "application/xml;notice=branch",
            f"{celex}.branch.xml",
        )
    )
    items, _ = annotations(branch)
    by_act: dict[str, list[Annotation]] = {}
    for item in items:
        by_act.setdefault(item.amending_act, []).append(item)
    lines = [
        f"# modification annotations of {celex} (notice=branch, fetched 2026-08-05)",
        "",
        f"{len(by_act)} amending acts - {len(items)} annotations",
        f"roles observed: {dict(sorted(Counter(i.role for i in items).items()))}",
        "location codes observed: "
        f"{dict(sorted(Counter(c for i in items for c in codes(i.location)).items()))}",
        f"annotations with no keyable top-level unit: {sum(1 for i in items if not i.unit)}",
        "",
        "## per amending act (sorted by earliest START_OF_VALIDITY)",
    ]
    for act, group in sorted(
        by_act.items(), key=lambda kv: min(i.start_of_validity for i in kv[1])
    ):
        dates = dict(sorted(Counter(i.start_of_validity for i in group).items()))
        lines.append(
            f"{act}  n={len(group)}  roles={dict(sorted(Counter(i.role for i in group).items()))}"
            f"  start_of_validity={dates}"
        )
    return render(lines)


def apply_substitution(text: str, old: str, new: str) -> str:
    """Apply a blanket word substitution of the kind EU acts order in one sentence.

    E.g. Regulation 1272/2008 Art. 57(11): "the word 'preparation' or 'preparations'
    ... shall be replaced by 'mixture' or 'mixtures' respectively throughout the
    text." CELLAR annotates such an instruction once; it changes dozens of articles.
    """

    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        out = new + ("s" if word.lower().endswith("s") else "")
        if word.isupper():
            return out.upper()
        return out.capitalize() if word[:1].isupper() else out

    return re.sub(rf"\b{re.escape(old)}s?\b", repl, text, flags=re.IGNORECASE)


def substitution_block(
    before: dict[str, str],
    after: dict[str, str],
    unexplained: set[str],
    substitution: str,
) -> list[str]:
    old, _, new = substitution.partition(":")
    explained = {
        key
        for key in unexplained
        if key in before
        and key in after
        and squash(apply_substitution(before[key], old, new)) == squash(after[key])
    }
    return [
        f"### blanket substitution check: '{old}' -> '{new}'",
        f"  diff-only units explained entirely by this substitution: "
        f"{len(explained)}/{len(unexplained)}",
        f"  explained: {' | '.join(order(explained)) or '-'}",
        f"  still unexplained: {' | '.join(order(unexplained - explained)) or '-'}",
        "",
    ]


def command_trace(
    celex: str, version_a: str, version_b: str, substitution: str | None = None
) -> str:
    # `original` = the act as published in the OJ, for acts whose first consolidated
    # version is not available in English (verified reality: 02024R1689-20240712 has
    # eleven languages, none of them English).
    if version_a == ORIGINAL:
        before_docs = fetch_act(act_resource_paths(celex))
    else:
        before_docs = fetch_consolidated(celex, version_a)
    after_docs = fetch_consolidated(celex, version_b)
    before, after = units(before_docs), units(after_docs)
    diff = structural_diff(before, after)

    branch = fromstring(
        fetch(
            f"{BASE}/resource/celex/{celex}",
            "application/xml;notice=branch",
            f"{celex}.branch.xml",
        )
    )
    all_annotations, act_paths = annotations(branch)
    start = "" if version_a == ORIGINAL else version_date(version_a)
    end = version_date(version_b)
    window = [a for a in all_annotations if start < a.start_of_validity <= end]
    acts = sorted({a.amending_act for a in window})

    metadata_units = {a.unit for a in window if a.unit}
    unkeyable = [a for a in window if not a.unit]

    prose_units: set[str] = set()
    prose_notes: list[str] = []
    for act in acts:
        try:
            docs = fetch_act(act_paths.get(act) or act_resource_paths(act))
            prose_units |= instruction_units(docs[0], celex)
        except LookupError as exc:
            prose_notes.append(f"  {act}: no English Formex ({exc})")

    lines = [
        f"# {celex}  {version_a} -> {version_b}",
        "# emendrix validation trace, generated 2026-08-05",
        "",
        f"amending acts in window: {', '.join(acts) if acts else '(none)'}",
        f"units in v({version_a}): {len(before)}   units in v({version_b}): {len(after)}",
        "",
        "## signal 1 - structural Formex diff",
        f"inserted {len(diff.inserted)} - modified {len(diff.modified)} - "
        f"deleted {len(diff.deleted)} - unchanged {len(diff.unchanged)} "
        f"-> {len(diff.touched)} touched",
        f"  inserted: {' | '.join(order(diff.inserted)) or '-'}",
        f"  deleted : {' | '.join(order(diff.deleted)) or '-'}",
        f"  modified: {' | '.join(order(diff.modified)) or '-'}",
        "",
        "## signal 2 - CELLAR modification annotations",
        f"{len(window)} annotations -> {len(metadata_units)} touched units",
        f"  roles: {dict(sorted(Counter(a.role for a in window).items()))}",
        f"  units: {' | '.join(order(metadata_units)) or '-'}",
        f"  location codes seen: "
        f"{dict(sorted(Counter(c for a in window for c in codes(a.location)).items()))}",
        f"  annotations with no keyable top-level unit: {len(unkeyable)}"
        + (f"  {[a.location for a in unkeyable]}" if unkeyable else ""),
        "",
        "## signal 3 - naive instruction-prose parse of the amending acts",
        f"{len(prose_units)} units named",
        *prose_notes,
        "",
        "## agreement (granularity: top-level provision)",
    ]
    lines += agreement_block("diff vs metadata", diff.touched, metadata_units)
    if substitution:
        lines += substitution_block(before, after, diff.touched - metadata_units, substitution)
    lines += agreement_block(
        "diff vs metadata, articles only",
        {u for u in diff.touched if u.startswith("AR")},
        {u for u in metadata_units if u.startswith("AR")},
    )
    lines += agreement_block(
        "prose vs metadata, same window",
        prose_units & keyspace(before, after),
        metadata_units,
    )
    lines += [
        "# note: instruction prose carries no date, so a naive parse names every provision",
        "# the amending act touches, not the subset that entered into force in this window.",
        "# The block below is the fair measure of the prose parser.",
    ]
    all_units_of_acts = {a.unit for a in all_annotations if a.amending_act in set(acts) and a.unit}
    lines += agreement_block(
        "prose vs metadata, whole amending acts",
        prose_units & keyspace(before, after),
        all_units_of_acts,
    )
    return render(lines)


def codes(location: str) -> list[str]:
    """Location-code tokens of a normalised location string.

    Roman numerals are dropped: they are annex *numbers* ('AN XVII'), not codes,
    and no observed fd_370 code is a valid roman numeral.
    """
    return [
        token
        for token in re.findall(r"\b[A-Z]{2,8}\b", location)
        if not re.fullmatch(r"[IVXLCDM]+", token)
    ]


def keyspace(before: dict[str, str], after: dict[str, str]) -> set[str]:
    """Units that actually exist in either version; bounds the prose signal."""
    return set(before) | set(after)


def agreement_block(label: str, predicted: set[str], reference: set[str]) -> list[str]:
    precision, recall, f1 = prf(predicted, reference)
    scores = (
        "P n/a - R n/a - F1 n/a (both sets empty)"
        if not predicted and not reference
        else f"P {precision:.3f} - R {recall:.3f} - F1 {f1:.3f}"
    )
    return [
        f"### {label}",
        f"  predicted {len(predicted)} - reference {len(reference)} - {scores}",
        f"  only in predicted: {' | '.join(order(predicted - reference)) or '-'}",
        f"  only in reference: {' | '.join(order(reference - predicted)) or '-'}",
        "",
    ]


def version_date(version: str) -> str:
    """Consolidated-version tag '20200424' -> ISO date '2020-04-24'."""
    return f"{version[:4]}-{version[4:6]}-{version[6:8]}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    versions = sub.add_parser("versions", help="list consolidated versions + manifestations")
    versions.add_argument("celex")
    annots = sub.add_parser("annotations", help="inventory of CELLAR modification annotations")
    annots.add_argument("celex")
    trace = sub.add_parser("trace", help="three-way trace of one version pair")
    trace.add_argument("celex")
    trace.add_argument("version_a")
    trace.add_argument("version_b")
    trace.add_argument(
        "--substitution",
        metavar="OLD:NEW",
        help="check how many diff-only units a blanket word substitution explains",
    )
    parser.add_argument("--write", action="store_true", help="also write results/<name>.txt")
    args = parser.parse_args(argv)

    if args.command == "versions":
        report = command_versions(args.celex)
        name = f"{args.celex}-versions.txt"
    elif args.command == "annotations":
        report = command_annotations(args.celex)
        name = f"{args.celex}-annotations.txt"
    else:
        report = command_trace(args.celex, args.version_a, args.version_b, args.substitution)
        name = f"{args.celex}-{args.version_a}-{args.version_b}.txt"
    sys.stdout.write(report)
    if args.write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / name).write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
