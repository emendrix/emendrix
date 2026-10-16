"""The entry diff never reaches the model: a change with one builds the same prompt as without.

Byte identity of the user and system messages is the whole claim, and the cassette key is
derived from exactly those two strings, so proving the prompt unchanged proves no committed
cassette moves. The delta is attached to a toy change, because what is under test is the
prompt builder's indifference to the field, not any law.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import (
    Change,
    Delta,
    EntryChange,
    EntryDelta,
    EntryTable,
    ProvisionLocation,
    ProvisionTree,
    TableEntry,
)
from emendrix.diff import compute_delta
from emendrix.explain import build_context, build_prompt, cassette_key, header_block
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

CONTAINER = ProvisionLocation.parse("AR 2")


def toy_delta() -> Delta:
    adapter = ToyCorpusAdapter(observed_on=date(2026, 8, 6))
    before, after = adapter.fetch_version(HOUSE_RULES, V1), adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return compute_delta(before, after)


def _with_entries(change: Change) -> Change:
    after = TableEntry(
        unit=CONTAINER, container=CONTAINER, table=1, key="k1", rows=(("k1", "new words"),)
    )
    delta = EntryDelta(
        tables=(EntryTable(unit=CONTAINER, container=CONTAINER, table=1, key_label="No"),),
        changes=(EntryChange(kind="added", container=CONTAINER, table=1, key="k1", after=after),),
    )
    return change.model_copy(update={"table_entries": delta})


def test_the_prompt_is_byte_identical_with_and_without_the_entry_diff() -> None:
    plain = toy_delta().changes[0]
    assert plain.table_entries is None
    with_entries = _with_entries(plain)
    assert with_entries.table_entries is not None
    for change in (plain, with_entries):
        context = build_context(
            change, from_version=toy_delta().from_version, to_version=toy_delta().to_version
        )
        parts = build_prompt(change, context)
        reference = build_prompt(
            plain,
            build_context(
                plain, from_version=toy_delta().from_version, to_version=toy_delta().to_version
            ),
        )
        assert parts.system == reference.system
        assert parts.user == reference.user
        assert header_block(change) == header_block(plain)
        assert cassette_key("any-model", parts.system, parts.user) == cassette_key(
            "any-model", reference.system, reference.user
        )
    assert (
        "k1"
        not in build_prompt(
            with_entries,
            build_context(
                with_entries,
                from_version=toy_delta().from_version,
                to_version=toy_delta().to_version,
            ),
        ).user
    )
