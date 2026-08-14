"""The order of `CHANGELOG.md`: a property of the versions, never of the order they were run in.

The poller emits forward and a backfill emits backwards into the same file, weeks apart, so
"newest first" has to mean the newest *version* rather than the newest *emission*. These tests
are the difference between the two: every one of them passes an entry the file already has a
newer entry than, which is exactly the case a prepend gets wrong.

Built on the toy corpus, like the rest of the output suite: `v1 … v4` sort the way consolidated
version tags do, and no law is involved in checking that a list is in order.
"""

from __future__ import annotations

from toy_entries import OBSERVED_ON, toy_delta

from emendrix.core import VersionId
from emendrix.output import ChangelogEntry, changelog_text, diff_only_entry, split_entries


def entry(from_version: str, to_version: str) -> ChangelogEntry:
    """One transition of the house rules, keyed by the version it produced."""
    delta = toy_delta()
    return diff_only_entry(
        delta.model_copy(
            update={
                "from_version": VersionId(from_version),
                "to_version": VersionId(to_version),
            }
        ),
        detected_on=OBSERVED_ON,
    )


def file_of(*entries: ChangelogEntry) -> str:
    """The changelog those entries make, written in the order given."""
    text: str | None = None
    for item in entries:
        text = changelog_text(text, item)
    assert text is not None
    return text


def keys_of(text: str) -> list[str]:
    return [key for key, _ in split_entries(text)]


def test_a_backfilled_entry_lands_under_the_newer_one_the_file_already_has() -> None:
    assert keys_of(file_of(entry("v3", "v4"), entry("v1", "v2"))) == ["v4", "v2"]


def test_emission_order_does_not_decide_the_file_order() -> None:
    scrambled = file_of(entry("v2", "v3"), entry("v3", "v4"), entry("v1", "v2"))
    assert keys_of(scrambled) == ["v4", "v3", "v2"]


def test_a_backfill_after_a_poll_produces_the_file_a_poll_after_a_backfill_would() -> None:
    """The property the sorted insertion exists for: emission order stops mattering."""
    assert file_of(entry("v3", "v4"), entry("v1", "v2")) == file_of(
        entry("v1", "v2"), entry("v3", "v4")
    )


def test_re_emitting_an_entry_replaces_it_where_it_lies() -> None:
    """The idempotency the markers buy must survive the ordering change."""
    text = file_of(entry("v3", "v4"), entry("v1", "v2"))
    again = changelog_text(text, entry("v1", "v2"))
    assert keys_of(again) == ["v4", "v2"]
    assert again == text
