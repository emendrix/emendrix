"""The evidence digest: what an explanation was written about, and what its absence means.

The one correction in this pipeline that costs money is a re-explanation, because everything
else is a pure function of stored inputs and an explanation is the output of a paid,
non-repeatable call about a particular pair of verbatim texts. These tests hold the two halves
of making that answerable: the digest moves when the evidence moves and not when anything else
does, and a document that carries none says its provenance is unknown rather than being handed
one it cannot have earned.
"""

from __future__ import annotations

import json

from toy_entries import OBSERVED_ON, disputed_delta, toy_delta

from emendrix.core import ProvisionText
from emendrix.explain import RunStats
from emendrix.gate import GateOutcome
from emendrix.graph.report import EmittedChange, EmittedDelta, RunReport
from emendrix.output import (
    DIGEST_PREFIX,
    ChangelogEntry,
    EvidenceState,
    checked,
    digest_of,
    entries_for,
    evidence_for,
    recorded_digests,
)
from emendrix.output.provenance import digest_of_texts, keys_of, merged

MODEL = "test:pinned"
"""Any non-empty model id: `RunStats` only has to exist for the run to have explained."""


def _emitted(changes: tuple[EmittedChange, ...], *, explained: bool = True) -> EmittedDelta:
    delta = toy_delta()
    return EmittedDelta(
        act=delta.act,
        from_version=delta.from_version,
        to_version=delta.to_version,
        summary=delta.summary,
        changes=changes,
        explain=RunStats(model_id=MODEL, changes=len(changes)) if explained else None,
    )


def _changes() -> tuple[EmittedChange, ...]:
    return tuple(
        EmittedChange(change=change, outcome=GateOutcome.PASSED) for change in toy_delta().changes
    )


# ----------------------------------------------------------------- the digest itself


def test_a_digest_is_stable_across_two_runs() -> None:
    """Same evidence, same value: the whole comparison rests on it."""
    change = toy_delta().changes[0]
    assert digest_of(change) == digest_of(change)
    assert digest_of(change).startswith(DIGEST_PREFIX)


def test_a_digest_moves_when_either_verbatim_text_moves_by_one_byte() -> None:
    """The question it answers is whether the evidence moved, so one byte has to be enough."""
    change = next(item for item in toy_delta().changes if item.before and item.after)
    original = digest_of(change)
    for side in ("before", "after"):
        nudged = change.model_copy(update={side: ProvisionText(str(getattr(change, side)) + " ")})
        assert digest_of(nudged) != original, side


def test_a_digest_moves_when_the_location_moves() -> None:
    """A sentence about Article 4 is not a sentence about Article 5 with the same text."""
    assert digest_of_texts("AR 4", "a", "b") != digest_of_texts("AR 5", "a", "b")


def test_an_absent_side_is_not_an_empty_one() -> None:
    """Verbatim means verbatim: an empty provision text is a text, and a deletion is not one."""
    assert digest_of_texts("AR 4", None, "b") != digest_of_texts("AR 4", "", "b")
    assert digest_of_texts("AR 4", "a", None) != digest_of_texts("AR 4", "a", "")


def test_the_fields_cannot_run_together() -> None:
    """`("ab", "c")` and `("a", "bc")` are different evidence and digest differently."""
    assert digest_of_texts("AR 4", "ab", "c") != digest_of_texts("AR 4", "a", "bc")


def test_a_textless_change_digests_stably_and_unlike_every_other_change() -> None:
    """A unit another signal named and the diff never saw still gets a value of its own.

    It contributes no text to the prompt and no call was made about it, but "no evidence"
    is a fact about it, and it has to be tellable from "no digest recorded".
    """
    delta = disputed_delta()
    textless = next(change for change in delta.changes if change.textless)
    with_text = next(change for change in delta.changes if not change.textless)
    assert digest_of(textless) == digest_of(textless)
    assert digest_of(textless) != digest_of(with_text)
    assert digest_of(textless) == digest_of_texts(textless.location.canonical, None, None)


def test_two_changes_at_one_location_keep_separate_records() -> None:
    """Position is not identity after a repair, so the key is location plus occurrence."""
    change = toy_delta().changes[0]
    assert keys_of((change, change)) == (
        (change.location.canonical, 0),
        (change.location.canonical, 1),
    )
    assert len(evidence_for((change, change))) == 2


# ------------------------------------------------------------ the payload contract


def test_a_run_that_explained_records_what_it_showed() -> None:
    """The one place a digest is written: the run holding the changes it handed over."""
    changes = _changes()
    entry = entries_for(RunReport(observed_on=OBSERVED_ON, deltas=(_emitted(changes),)))[0]
    assert entry.schema_version == "1.2"
    assert len(entry.evidence) == len(changes)
    recorded = recorded_digests(entry.evidence)
    for key, item in zip(keys_of(item.change for item in changes), changes, strict=True):
        assert recorded[key] == digest_of(item.change)


def test_a_run_with_no_model_stage_records_nothing() -> None:
    """Nothing was shown to anybody, so there is no provenance to state."""
    entry = entries_for(
        RunReport(observed_on=OBSERVED_ON, deltas=(_emitted(_changes(), explained=False),))
    )[0]
    assert entry.evidence == ()


def test_the_constructor_never_derives_a_digest_of_its_own() -> None:
    """The safeguard that keeps a repair from inventing one: `of` is told, never asks.

    A repair puts a committed entry back together through this constructor, and an entry whose
    digests it derived from its own stored texts would assert that a call nobody witnessed was
    shown them.
    """
    assert ChangelogEntry.of(_emitted(_changes()), detected_on=OBSERVED_ON).evidence == ()


def test_an_entry_with_no_digest_reports_provenance_unknown_and_nothing_raises() -> None:
    """The honest reading of every change published before 2026-09-05, counted not crashed on."""
    entry = ChangelogEntry.of(_emitted(_changes()), detected_on=OBSERVED_ON)
    answers = checked(
        (item.change for item in entry.changes),
        recorded=recorded_digests(entry.evidence),
        derived={},
    )
    assert len(answers) == len(entry.changes)
    assert {answer.state for answer in answers} == {EvidenceState.UNRECORDED}


def test_a_change_whose_evidence_moved_reads_differs_and_carries_its_size() -> None:
    changes = _changes()
    entry = entries_for(RunReport(observed_on=OBSERVED_ON, deltas=(_emitted(changes),)))[0]
    first = entry.changes[0].change
    keys = keys_of(item.change for item in entry.changes)
    moved = first.model_copy(update={"after": ProvisionText(str(first.after) + "!")})
    answers = checked(
        (item.change for item in entry.changes),
        recorded=recorded_digests(entry.evidence),
        derived={keys[0]: digest_of(moved)},
    )
    assert answers[0].state is EvidenceState.DIFFERS
    assert answers[0].chars == len(first.before or "") + len(first.after or "")
    assert answers[1].state is EvidenceState.UNDERIVABLE, "nothing was derived for the rest"


def test_a_change_whose_evidence_stood_still_reads_matches() -> None:
    changes = _changes()
    entry = entries_for(RunReport(observed_on=OBSERVED_ON, deltas=(_emitted(changes),)))[0]
    keys = keys_of(item.change for item in entry.changes)
    derived = {key: digest_of(item.change) for key, item in zip(keys, entry.changes, strict=True)}
    answers = checked(
        (item.change for item in entry.changes),
        recorded=recorded_digests(entry.evidence),
        derived=derived,
    )
    assert {answer.state for answer in answers} == {EvidenceState.MATCHES}


def test_merging_replaces_one_record_and_leaves_every_other_alone() -> None:
    """What a pass that re-asked about one change may write, and no more than that."""
    changes = _changes()
    carried = evidence_for(item.change for item in changes)
    written = (carried[0].model_copy(update={"digest": DIGEST_PREFIX + "0" * 64}),)
    after = recorded_digests(merged(carried, written))
    assert after[carried[0].key] == DIGEST_PREFIX + "0" * 64
    assert after[carried[1].key] == carried[1].digest
    assert len(after) == len(carried)


# ------------------------------------------------------------------ every schema reads


def test_all_three_schema_versions_read_back() -> None:
    """446 documents say `1.0` and the site is built from them; `1.2` round-trips."""
    entry = entries_for(RunReport(observed_on=OBSERVED_ON, deltas=(_emitted(_changes()),)))[0]
    text = entry.to_json()
    assert ChangelogEntry.model_validate_json(text).to_json() == text

    payload = json.loads(text)
    for version in ("1.0", "1.1"):
        older = {**payload, "schema_version": version}
        del older["evidence"]
        read = ChangelogEntry.model_validate(older)
        assert read.schema_version == version
        assert read.evidence == (), "an older document states no provenance, and gains none"
