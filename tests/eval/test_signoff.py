"""The sign-off: the one thing that may move `human_review`, and the digest that limits it.

Two properties matter here and they pull in opposite directions on purpose. A committed review
by a named person on a named date should reach a reader, because `pending` next to a rate nobody
checked is the state this project least wants to be in. And a review must never describe prose
nobody read, which is what the digest enforces: it covers the whole sample, both texts included,
so any change to what the model was shown or what it said takes the published claim back to
`pending` with nobody having to remember the rule.

The last test is the transcription check. A sign-off is typed by hand from a sheet somebody
ticked by hand, and the two are only worth anything while they agree, so the agreement is
asserted rather than trusted, for every sign-off in the tree rather than for one of them.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from emendrix.eval_.judge import Triple
from emendrix.eval_.signoff import (
    PENDING,
    ReviewedEntry,
    ReviewSignoff,
    latest_signoff,
    load_signoff,
    prompt_sha,
    review_status,
    sample_digest,
    signoff_paths,
)

ROOT = Path(__file__).resolve().parents[2]

COUNTS = {
    "reports/faithfulness-review-2026-08-08.md": (13, 7),
    "reports/faithfulness-review-2026-08-09.md": (15, 5),
    "reports/faithfulness-review-2026-08-10.md": (18, 2),
    "reports/faithfulness-review-2026-08-11.md": (18, 2),
    "reports/faithfulness-review-2026-08-12.md": (17, 3),
}
"""Every ticked sheet in the tree and the split a person put on it, pinned here so a transcription
that drifts from its source has somewhere to land. Not regenerable: each is an afternoon of
somebody reading two legal texts per entry, recoverable only from git."""

_HEADING = re.compile(r"^## (\d+)\. `([^`]+)` — `([^`]+)`$", re.M)
_TICKED_FAITHFUL = "- [x] Faithful"
_TICKED_NOT = re.compile(r"^- \[x\] Not faithful — reason: (.+)$", re.M)


def _triple(index: int = 1, **updates: object) -> Triple:
    base = Triple(
        case_id="32024R1689@20260727",
        unit=f"AR {index}",
        outcome="passed",
        change_type="modified",
        before=f"before {index}",
        after=f"after {index}",
        sentences=(f"sentence {index}",),
    )
    return base.model_copy(update=updates)


def _signoff(triples: tuple[Triple, ...], **updates: object) -> ReviewSignoff:
    base = ReviewSignoff(
        reviewed_on=date(2026, 8, 8),
        reviewer="A Reviewer",
        worksheet="reports/faithfulness-review-2026-08-08.md",
        sample_digest=sample_digest(triples),
        summary="reviewed 2/2 on 2026-08-08 by A Reviewer: 1 faithful, 1 not faithful",
        entries=tuple(
            ReviewedEntry(slug=item.slug, prompt_sha=prompt_sha(item), faithful=True)
            for item in triples
        ),
    )
    return base.model_copy(update=updates)


def test_the_digest_is_the_same_every_time_it_is_taken() -> None:
    triples = (_triple(1), _triple(2))
    assert sample_digest(triples) == sample_digest(triples)
    assert len(sample_digest(triples)) == 64


def test_every_field_the_reviewer_read_is_inside_the_digest() -> None:
    """A changed BEFORE text changes what "faithful" means as surely as a changed sentence.

    `context` and `header` are in the list because the worksheet quotes them: whatever the
    reviewer was shown is part of what the sign-off describes, and the digest is what stops a
    review being published about prose or evidence nobody read.
    """
    triples = (_triple(1), _triple(2))
    base = sample_digest(triples)
    for field, value in (
        ("case_id", "32017R0745@20200424"),
        ("unit", "AN III"),
        ("before", "something else entirely"),
        ("after", "something else entirely"),
        ("context", "an enclosing provision the reviewer was shown"),
        ("header", "CHANGE TYPE: MODIFIED (an obviously synthetic header)"),
        ("sentences", ("a different sentence",)),
    ):
        moved = (_triple(1, **{field: value}), _triple(2))
        assert sample_digest(moved) != base, field


def test_the_order_of_the_sample_is_part_of_its_identity() -> None:
    """The sheet numbers its entries, and a reviewer's note names a number."""
    assert sample_digest((_triple(1), _triple(2))) != sample_digest((_triple(2), _triple(1)))


def test_a_sample_the_signoff_does_not_describe_is_pending() -> None:
    triples = (_triple(1), _triple(2))
    signoff = _signoff(triples)
    assert review_status(signoff, (_triple(1), _triple(3))) == PENDING
    assert review_status(signoff, (_triple(1),)) == PENDING


def test_no_signoff_and_no_sample_are_both_pending() -> None:
    triples = (_triple(1), _triple(2))
    assert review_status(None, triples) == PENDING
    assert review_status(_signoff(()), ()) == PENDING


def test_a_matching_signoff_publishes_its_summary_and_nothing_else() -> None:
    """Verbatim: no prefix, no date appended, no "(reviewed)" decoration around it."""
    triples = (_triple(1), _triple(2))
    signoff = _signoff(triples)
    assert review_status(signoff, triples) == signoff.summary


def test_a_missing_signoff_is_none_and_a_broken_one_is_loud(tmp_path: Path) -> None:
    """A missing review is a normal state of this project; an unreadable one is a build fault."""
    assert load_signoff(tmp_path / "nothing.json") is None
    broken = tmp_path / "faithfulness-signoff-2026-08-08.json"
    broken.write_text('{"reviewer": "A Reviewer"}', encoding="utf-8")
    with pytest.raises(ValidationError):
        load_signoff(broken)


def test_the_newest_signoff_is_the_one_a_run_would_publish() -> None:
    """Sign-offs accumulate, one per sheet, and publication takes the last of them.

    An older review is kept because it is a label set a judge is scored against, not because it
    is still a candidate for the report: the sample it describes stopped being the current one
    the day it was read, and its digest says so.
    """
    found = signoff_paths()
    assert [path.name for path in found] == [
        "faithfulness-signoff-2026-08-08.json",
        "faithfulness-signoff-2026-08-09.json",
        "faithfulness-signoff-2026-08-10.json",
        "faithfulness-signoff-2026-08-11.json",
        "faithfulness-signoff-2026-08-12.json",
    ]
    newest = latest_signoff()
    assert newest is not None
    assert newest.worksheet == "reports/faithfulness-review-2026-08-12.md"
    assert newest == load_signoff(found[-1])


def test_a_directory_with_no_signoff_in_it_is_none_rather_than_an_error(tmp_path: Path) -> None:
    """A missing review is a normal state of this project, including before the first one."""
    assert signoff_paths(tmp_path) == ()
    assert latest_signoff(tmp_path) is None


@pytest.mark.parametrize("path", signoff_paths(), ids=lambda path: path.name)
def test_every_committed_signoff_says_what_its_ticked_sheet_says(path: Path) -> None:
    """The transcription, checked against its source. Neither file may drift from the other.

    The sheet is the artifact a person made and the sign-off is a machine-readable copy of it,
    so a disagreement between them is a transcription error in the copy, never a reason to edit
    the sheet. Every sign-off is checked, not only the newest: an older one is the label set a
    judge is scored against, so it has to keep saying what its sheet says for as long as it is
    in the tree.
    """
    signoff = load_signoff(path)
    assert signoff is not None
    assert signoff.worksheet in COUNTS, f"{path.name} reviews a sheet nothing here pins"

    text = (ROOT / signoff.worksheet).read_text(encoding="utf-8")
    bodies = _HEADING.split(text)[1:]
    ticked = [
        (f"{case} {unit}", _TICKED_FAITHFUL in body, _TICKED_NOT.search(body))
        for _, case, unit, body in zip(*[iter(bodies)] * 4, strict=True)
    ]
    assert len(ticked) == 20

    assert [entry.slug for entry in signoff.entries] == [slug for slug, _, _ in ticked]
    for entry, (slug, faithful, reason) in zip(signoff.entries, ticked, strict=True):
        assert faithful != bool(reason), f"{slug} is ticked in neither or in both columns"
        assert entry.faithful is faithful, slug
        assert entry.note == ("" if reason is None else reason.group(1).strip()), slug

    expected = COUNTS[signoff.worksheet]
    counts = (
        sum(1 for entry in signoff.entries if entry.faithful),
        sum(1 for entry in signoff.entries if not entry.faithful),
    )
    assert counts == expected, counts
    assert f"{expected[0]} faithful, {expected[1]} not faithful" in signoff.summary
