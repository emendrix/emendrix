"""The record reader's committed fixture is what this package's own writers produce.

`emendrix-record` reads a changelogs repository and a site catalogue it never wrote, so its
tests, and those of every member reading through it, run over a copy committed beside them.
This test is what keeps that copy honest: it writes toy entries through `OutputRepo.write`, the
writer every hosted payload went through, and builds the catalogue with `api_files`, the
function the site build writes it with, then asserts the committed copy is byte for byte the
result.

`api_files` is handed a `SiteInputs` made with `model_construct`, holding only the acts, the
site URL and a poller record. A validated one needs an evaluation run, and the catalogue reads
neither that nor anything else on the model, so the bytes are the ones a full build would write
for these acts. The poller record gives each act one waiting consolidation, one of them with no
version known and no English text offered, so a reader meets both shapes the catalogue carries.

One payload is rewritten afterwards with `json`, its changes' `dispute_reason` keys removed,
and the index rebuilt over it the way `emendrix index rebuild` rebuilds it. That is the shape
of every payload written before the field was stored, and a reader must read it.

To regenerate, from the repository root, with the path the failure message names::

    uv run pytest -n0 tests/output/test_record_fixture.py
    rm -rf packages/emendrix-record/tests/fixtures
    cp -R <the path> packages/emendrix-record/tests/fixtures

Then read the diff, because that is the review.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from index_entries import (
    SECOND_EVENT_ON,
    at_version,
    repaired,
    with_units,
    without_dispute_reason,
)
from toy_entries import disputed_entry, explained_entry

from emendrix.core import ActId
from emendrix.output import INDEX_FILE, ChangelogEntry, OutputRepo, index_files
from emendrix.output.json_out import payload_for
from emendrix.site_.api_files import CATALOGUE, api_files
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.polled import PolledState, Waiting

FIXTURES = (
    Path(__file__).resolve().parents[2] / "packages" / "emendrix-record" / "tests" / "fixtures"
)
"""The committed copy the members' tests read."""

SITE_URL = "https://example.org"
"""Any absolute base will do; a reader only ever repeats what the catalogue says."""

GARDEN = ActId(corpus="toy", key="garden-rules", display_name="Garden Rules of Flat 3B")


def house_entries() -> tuple[ChangelogEntry, ...]:
    """Two events of one act: explained prose, then a disputed, repaired, unit-naming event."""
    later = at_version(disputed_entry(), "v3", SECOND_EVENT_ON)
    later = with_units(later, metadata_only=("AR 9",), instruction_only=("AR 7",))
    return (
        explained_entry(),
        repaired(later, "signals", SECOND_EVENT_ON + timedelta(days=1)),
    )


def garden_entry() -> ChangelogEntry:
    """A disputed event of a second act, whose payload is later stripped of `dispute_reason`."""
    return disputed_entry().model_copy(update={"act": GARDEN})


POLLED = PolledState(
    checked_through=SECOND_EVENT_ON + timedelta(days=3),
    waiting=2,
    waiting_since=SECOND_EVENT_ON + timedelta(days=1),
    by_act={
        str(GARDEN): (
            Waiting(
                version=None,
                state="english_unavailable",
                first_seen=SECOND_EVENT_ON + timedelta(days=1),
            ),
        ),
        "toy:house-rules": (
            Waiting(
                version="v4",
                state="consolidation_pending",
                first_seen=SECOND_EVENT_ON + timedelta(days=2),
            ),
        ),
    },
)
"""What the poller is taken to have recorded when the fixture's catalogue was built."""


def _site(entries: tuple[ChangelogEntry, ...]) -> SiteInputs:
    acts: dict[str, list[ChangelogEntry]] = {}
    for entry in entries:
        acts.setdefault(entry.act.key, []).append(entry)
    return SiteInputs.model_construct(
        site_url=SITE_URL,
        polled=POLLED,
        acts=tuple(
            ActSite(
                act=group[0].act,
                label=group[0].title,
                aliases=(key.replace("-", " "),),
                domain="Housing",
                entries=tuple(sorted(group, key=lambda entry: entry.key, reverse=True)),
            )
            for key, group in sorted(acts.items())
        ),
    )


def build_fixture(out: Path, scratch: Path) -> None:
    """Write the fixture tree into `out`, using `scratch` for the git repository."""
    repo = OutputRepo.open(scratch / "changelogs")
    for entry in (*house_entries(), garden_entry()):
        repo.write(entry)
    garden = repo.path / payload_for(GARDEN, "v2")
    garden.write_text(without_dispute_reason(garden_entry()), encoding="utf-8")
    for relative, text in index_files(repo.path).items():
        (repo.path / relative).write_text(text, encoding="utf-8")

    published = [repo.path / INDEX_FILE, *sorted(repo.path.glob(f"*/*/{INDEX_FILE}"))]
    published += sorted(repo.path.glob("*/*/changes/*.json"))
    for source in published:
        target = out / "changelogs" / source.relative_to(repo.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    entries = tuple(
        ChangelogEntry.model_validate_json(path.read_bytes())
        for path in sorted(repo.path.glob("*/*/changes/*.json"))
    )
    (out / "catalogue.json").write_text(api_files(_site(entries))[CATALOGUE], encoding="utf-8")


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_the_committed_fixture_is_what_the_writers_produce(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    out = tmp_path_factory.mktemp("record-fixture")
    build_fixture(out, tmp_path_factory.mktemp("record-scratch"))
    built, committed = _tree(out), _tree(FIXTURES)
    assert built == committed, (
        f"packages/emendrix-record/tests/fixtures differs from what the writers produce now, "
        f"built in {out}; to accept it run `rm -rf packages/emendrix-record/tests/fixtures && "
        f"cp -R {out} packages/emendrix-record/tests/fixtures` and read the diff"
    )


def test_one_fixture_payload_stores_no_dispute_reason_and_another_does() -> None:
    stripped = (FIXTURES / "changelogs" / payload_for(GARDEN, "v2")).read_text(encoding="utf-8")
    assert '"disputed": true' in stripped
    assert '"dispute_reason"' not in stripped
    house = FIXTURES / "changelogs" / "toy" / "house-rules" / "changes" / "v3.json"
    assert '"dispute_reason": "' in house.read_text(encoding="utf-8")
