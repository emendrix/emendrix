"""Entry deltas for the site suite, built from invented keys and invented cell text.

The site renders whatever rows a delta carries, so these deltas need no corpus behind them:
keys read `k1`, cells read `alpha`, identifiers are visibly not real numbers. Nothing here is
typed legal content. The one table has two header rows with both kinds of span, because the
merge rule is what a header renders through.
"""

from __future__ import annotations

from emendrix.core import (
    EntryChange,
    EntryDelta,
    EntryGaps,
    EntryTable,
    Identifier,
    KeyRef,
    ProvisionLocation,
    TableEntry,
)

__all__ = [
    "TABLE",
    "UNIT",
    "added",
    "amended",
    "delta",
    "entry",
    "removed",
    "unpaired",
]

UNIT = ProvisionLocation.parse("AN I")

TABLE = EntryTable(
    unit=UNIT,
    container=UNIT,
    table=1,
    key_label="Entry",
    header=(("Entry", "Name", "Limits", None), (None, None, "low", "high")),
)
"""`Entry` and `Name` run down both header rows; `Limits` runs across two columns."""


def entry(key: str, *rows: tuple[str | None, ...], name: str | None = None) -> TableEntry:
    return TableEntry(
        unit=UNIT,
        container=UNIT,
        table=1,
        key=key,
        rows=rows or ((key, f"name {key}", "alpha", "beta"),),
        identifiers=(Identifier(scheme="cas", value=f"{key}-cas"),),
        name=name,
    )


def added(key: str, *rows: tuple[str | None, ...]) -> EntryChange:
    return EntryChange(kind="added", container=UNIT, table=1, key=key, after=entry(key, *rows))


def removed(key: str, *rows: tuple[str | None, ...]) -> EntryChange:
    return EntryChange(kind="removed", container=UNIT, table=1, key=key, before=entry(key, *rows))


def amended(
    key: str,
    before: tuple[str | None, ...],
    after: tuple[str | None, ...],
    *,
    typography: bool = False,
) -> EntryChange:
    return EntryChange(
        kind="amended",
        container=UNIT,
        table=1,
        key=key,
        typography_only=typography,
        before=entry(key, before),
        after=entry(key, after),
    )


def unpaired(key: str) -> KeyRef:
    return KeyRef(container=UNIT, table=1, key=key)


def delta(
    *changes: EntryChange,
    table: EntryTable = TABLE,
    whitespace_only: int = 0,
    gaps_before: EntryGaps | None = None,
    gaps_after: EntryGaps | None = None,
    unpaired_keys: tuple[KeyRef, ...] = (),
) -> EntryDelta:
    return EntryDelta(
        tables=(table,),
        changes=changes,
        whitespace_only=whitespace_only,
        gaps_before=gaps_before or EntryGaps(),
        gaps_after=gaps_after or EntryGaps(),
        unpaired=unpaired_keys,
    )
