"""The structured artifact: versioned, round-tripping, and losing nothing on the way out.

Other tools read this document, so the tests below are about the contract
rather than about any one act: the schema declares its version, a document survives a
serialise/parse round trip byte for byte, and the two flags a consumer most needs, per-change
signal provenance and the gate's verdict, are still there when it arrives.
"""

from __future__ import annotations

import json

from toy_entries import OBSERVED_ON, disputed_entry, explained_entry, toy_delta, toy_entry

from emendrix import DISCLAIMER
from emendrix.core import ChangeType
from emendrix.gate import GateOutcome
from emendrix.output import SCHEMA_VERSION, ChangelogEntry, diff_only_entry
from emendrix.output.json_out import DIFF_ONLY_NOTE, slug


def test_the_document_declares_its_schema_version_and_its_disclaimer() -> None:
    payload = json.loads(toy_entry().to_json())
    assert payload["schema_version"] == SCHEMA_VERSION == "1.0"
    assert payload["disclaimer"] == DISCLAIMER


def test_a_document_round_trips_byte_for_byte() -> None:
    """Committed artifacts are diffed in git, so serialisation may not wobble."""
    text = explained_entry().to_json()
    assert ChangelogEntry.model_validate_json(text).to_json() == text
    assert text.endswith("\n")


def test_the_json_and_the_markdown_count_the_same_things() -> None:
    entry = disputed_entry()
    payload = json.loads(entry.to_json())
    assert payload["counts"]["touched"] == entry.counts.touched
    assert payload["counts"]["disputed"] == 1
    assert payload["summary"]["disputed"] == 1


def test_per_change_signal_provenance_survives() -> None:
    """Which of the three signals saw a change is what makes `disputed` checkable."""
    disputed = [
        change
        for change in json.loads(disputed_entry().to_json())["changes"]
        if change["change"]["disputed"]
    ]
    assert len(disputed) == 1
    signals = disputed[0]["change"]["signals"]
    assert signals["corpus_metadata"]["status"] == "observed"
    assert signals["structural_diff"]["status"] == "absent"


def test_the_gate_flags_survive() -> None:
    changes = json.loads(explained_entry().to_json())["changes"]
    assert changes[0]["outcome"] == GateOutcome.PASSED.value
    assert changes[0]["sentences"][0]["fallback"] is False
    assert changes[1]["outcome"] == GateOutcome.FALLBACK.value
    assert changes[1]["sentences"][0]["fallback"] is True


def test_verbatim_texts_are_in_the_document_unnormalised() -> None:
    texts = [
        change["change"]["after"]
        for change in json.loads(toy_entry().to_json())["changes"]
        if change["change"]["after"]
    ]
    assert any("evening,  and the recycling" in text for text in texts), "two spaces, kept"


def test_the_counts_split_touched_units_into_substantive_and_date_only() -> None:
    """The header line's split. Computed from the changes, never asserted by a caller."""
    entry = toy_entry()
    assert entry.counts.touched == entry.counts.substantive + entry.counts.date_only
    assert entry.counts.date_only == 0, "the toy transition moves no dates"


def test_a_deferred_unit_counts_as_date_only() -> None:
    delta = toy_delta()
    deferred = delta.changes[0].model_copy(
        update={"change_type": ChangeType.DEFERRED, "applies_from": OBSERVED_ON}
    )
    entry = diff_only_entry(
        delta.model_copy(update={"changes": (deferred,)}), detected_on=OBSERVED_ON
    )
    assert (entry.counts.touched, entry.counts.date_only, entry.counts.substantive) == (1, 1, 0)


def test_diff_only_mode_says_so_rather_than_counting_absent_prose_as_a_defect() -> None:
    entry = toy_entry()
    assert entry.diff_only is True
    assert entry.counts.unexplained == 0, "no stage ran, so nothing is missing"
    assert entry.counts.quoted == 0
    assert all(change.unexplained == DIFF_ONLY_NOTE for change in entry.changes)


def test_the_repository_path_of_an_entry_is_derived_from_its_identity() -> None:
    entry = toy_entry()
    assert entry.act_dir == "toy/house-rules"
    assert entry.key == "v2"


def test_identifiers_that_are_not_path_safe_are_made_safe() -> None:
    """Version tags are opaque; nothing promises the next corpus keeps to a safe alphabet."""
    assert slug("2024R1689/20260727") == "2024R1689_20260727"
    assert slug("../../etc") == "etc"
    assert slug("///") == "unnamed"
