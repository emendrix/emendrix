"""The tally a version is summed up by, and the tags it is made of.

A tag is an adjective and the tally is a set of them, printed only for the categories present.
What a row of zeros once guaranteed is guaranteed here instead: the total is always printed, the
sources-differ tag is there exactly when the count is not zero, and the tags that break it down
add back up to it. Every number is the committed document's own.
"""

from __future__ import annotations

import re
from pathlib import Path

from site_entries import (
    attributed_entry,
    disputed_entry,
    some_textless_entry,
    textless_entry,
    unattributed_entry,
    untouched_entry,
)

from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry
from emendrix.site_.build import write_site
from emendrix.site_.inputs import collect_site
from emendrix.site_.tags import tally

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"

_TAG = re.compile(r'<span class="tag tag--([a-z-]+)">(\d+)?[^<]*</span>')

_ENTRIES: tuple[ChangelogEntry, ...] = (
    attributed_entry(),
    disputed_entry(),
    some_textless_entry(),
    textless_entry(),
    unattributed_entry(),
    untouched_entry(),
)


def _tags(entry: ChangelogEntry, *, shapes: bool = True) -> dict[str, int]:
    """Each numbered tag's kind and count, for one entry's tally."""
    found = _TAG.findall("".join(tally(entry, shapes=shapes)))
    return {kind: int(number) for kind, number in found if number}


def test_a_tally_never_prints_a_zero_count_tag() -> None:
    for entry in _ENTRIES:
        rendered = "".join(tally(entry, shapes=True))
        assert not re.search(r'tag--[a-z-]+">0 ', rendered), entry.key


def test_the_differ_tag_is_there_exactly_when_something_is_disputed() -> None:
    for entry in _ENTRIES:
        tags = _tags(entry)
        if entry.counts.disputed:
            assert tags["differ"] == entry.counts.disputed, entry.key
        else:
            assert "differ" not in tags, entry.key
    assert any(entry.counts.disputed for entry in _ENTRIES)


def test_the_per_shape_tags_add_up_to_the_differ_tag() -> None:
    for entry in _ENTRIES:
        tags = _tags(entry)
        shapes = sum(count for kind, count in tags.items() if kind.startswith("differ-"))
        assert shapes == tags.get("differ", 0), entry.key
        assert not any(kind.startswith("differ-") for kind in _tags(entry, shapes=False))


def test_the_total_is_the_touched_count() -> None:
    for entry in _ENTRIES:
        (sentence,) = re.findall(
            r'<p class="tally">([^<]*)</p>', "".join(tally(entry, shapes=True))
        )
        if entry.counts.touched:
            assert sentence.startswith(f"{entry.counts.touched} "), sentence
        else:
            assert sentence == "No provisions differ between these two versions."


def test_the_help_link_is_printed_only_when_asked_for_and_climbs_from_its_page() -> None:
    entry = disputed_entry()
    assert "tags-help" not in "".join(tally(entry, shapes=False))
    rendered = "".join(tally(entry, shapes=True, root="../../../"))
    assert '<a href="../../../methodology/#glossary">What these mean →</a>' in rendered


def test_the_help_link_resolves_to_the_glossary_from_every_page_that_prints_it(
    tmp_path: Path,
) -> None:
    """The act page, the amending act's page and the version page each climb a different
    distance; every copy of the link must land on the methodology page's glossary."""
    site = collect_site(
        generated_on=disputed_entry().detected_on,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(attributed_entry(),),
    )
    root = tmp_path / "site"
    write_site(root, site)
    glossary = (root / "methodology" / "index.html").read_text(encoding="utf-8")
    assert 'id="glossary"' in glossary
    checked = 0
    for page in root.rglob("index.html"):
        for href in re.findall(r'href="([^"]*methodology/#glossary)"', page.read_text("utf-8")):
            target = (page.parent / href.split("#")[0] / "index.html").resolve()
            assert target == (root / "methodology" / "index.html").resolve(), page
            checked += 1
    assert checked >= 3


def test_every_change_kind_is_a_tag_in_sentence_case_with_its_own_look() -> None:
    """The stored value's own word, cased for reading: `Modified`, never `MODIFIED`."""
    from emendrix.core import ChangeType
    from emendrix.site_.tags import GLOSSARY_OF, kind_tag

    for kind in ChangeType:
        words = kind.value.capitalize()
        assert kind_tag(kind) == (
            f'<span class="tag tag--kind-{kind.value.lower()}">{words}</span>'
        ), kind
        assert f"kind-{kind.value.lower()}" in GLOSSARY_OF


def test_every_shape_where_sources_differ_is_a_tag_with_its_definition_beside_it() -> None:
    """The tag is an adjective and never the link; the link to what it means sits beside it."""
    from emendrix.core import ChangeType, SignalObservation, SignalSet, SignalStatus
    from emendrix.site_.dispute import dispute_shape
    from emendrix.site_.tags import SHAPE_TAGS, differ_tag

    seen = SignalObservation(status=SignalStatus.OBSERVED)
    absent = SignalObservation(status=SignalStatus.ABSENT)
    unavailable = SignalObservation(status=SignalStatus.UNAVAILABLE)
    kinds = (
        SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.MODIFIED,)),
        SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.INSERTED,)),
    )
    shapes = {}
    for diff, meta in ((seen, absent), (absent, seen), kinds):
        signals = SignalSet(
            structural_diff=diff, corpus_metadata=meta, instruction_parse=unavailable
        )
        shapes[dispute_shape(signals)] = differ_tag(signals, "../../")
    assert set(shapes) == set(SHAPE_TAGS)
    for shape, (kind, words) in SHAPE_TAGS.items():
        assert shapes[shape] == (
            f'<span class="tag tag--{kind}">{words}</span><a class="define" '
            'href="../../methodology/#sources-differ">What this means</a>'
        )
