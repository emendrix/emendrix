"""A toy act with a register and a recorded entry change, for the substance pages.

Every key, cell and identifier is invented and visibly not a real number (`toy-1`, `toy-e1`):
the site never checks a check digit, it renders what the register and the payload carry, so the
pages need no corpus behind them. The shapes are the ones the inverted index has to get right:

- `toy-1` (CAS) and `toy-e1` (EC) are printed by one entry, `k1`, which a change amended: the
  EC page repeats the CAS page exactly and defers to it.
- `toy-2` (CAS) sits in `k2` alone, while `toy-e2` (EC) sits in `k2` and in `k3`: the EC page
  says more than the CAS page and stays its own canonical.
- `toy-9` (CAS) was in `k9`, which the change removed: no entry prints it now, and it keeps its
  page for its history.
- `toy-4` (CAS) sits in a row with no key, which is never compared.
- `toy-i1` (an Index No) is carried by `k1` and lands on `toy-1`'s page.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from site_entries import attributed_entry
from toy_table_entries import TABLE, UNIT

from emendrix.core import EntryChange, EntryDelta, Identifier, TableEntry
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, Register
from emendrix.site_.inputs import SiteInputs, collect_site

__all__ = [
    "BUILT",
    "SITE_URL",
    "entry_with_table",
    "register",
    "row",
    "substance_site",
]

BUILT = date(2026, 9, 1)
SITE_URL = "https://example.invalid/site"
REPORTS = Path(__file__).resolve().parents[2] / "reports" / "eval"


def _ids(*pairs: tuple[str, str]) -> tuple[Identifier, ...]:
    return tuple(Identifier(scheme=s, value=v) for s, v in sorted(pairs))


def row(
    key: str | None, *pairs: tuple[str, str], name: str = "", cell: str = "alpha"
) -> TableEntry:
    """One entry of the toy table, its rows invented."""
    return TableEntry(
        unit=UNIT,
        container=UNIT,
        table=1,
        key=key,
        rows=((key or "", name or f"name {key}", cell, "beta"),),
        identifiers=_ids(*pairs),
        name=name or f"name {key}",
    )


K1 = (("cas", "toy-1"), ("ec", "toy-e1"), ("index", "toy-i1"))


def register(act_key: str = "house-rules", version: str = "v2") -> Register:
    """The toy act's register: what its newest version prints."""
    return Register(
        corpus="toy",
        key=act_key,
        version=version,
        tables=(TABLE,),
        entries=(
            row("k1", *K1, name="Alpha compound; and its salts", cell="alpha after"),
            row("k2", ("cas", "toy-2"), ("ec", "toy-e2")),
            row("k3", ("ec", "toy-e2")),
            row(None, ("cas", "toy-4")),
        ),
    )


def entry_with_table() -> ChangelogEntry:
    """The toy event, its annex change carrying an amended `k1` and a removed `k9`."""
    entry = attributed_entry()
    changes = (
        EntryChange(
            kind="amended",
            container=UNIT,
            table=1,
            key="k1",
            before=row("k1", *K1, name="Alpha compound; and its salts", cell="alpha before"),
            after=row("k1", *K1, name="Alpha compound; and its salts", cell="alpha after"),
        ),
        EntryChange(
            kind="removed",
            container=UNIT,
            table=1,
            key="k9",
            before=row("k9", ("cas", "toy-9"), name="Gone compound"),
        ),
    )
    delta = EntryDelta(tables=(TABLE,), changes=changes)
    at = next(i for i, e in enumerate(entry.changes) if e.change.location.canonical == "AN I")
    emitted = entry.changes[at]
    tabled = emitted.model_copy(
        update={"change": emitted.change.model_copy(update={"table_entries": delta})}
    )
    return entry.model_copy(
        update={"changes": (*entry.changes[:at], tabled, *entry.changes[at + 1 :])}
    )


def substance_site(*, site_url: str = SITE_URL, accounts: bool = False) -> SiteInputs:
    """The toy act shown with its register and its one event."""
    return collect_site(
        generated_on=BUILT,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(entry_with_table(),),
        site_url=site_url,
        accounts=accounts,
        registers=(register(),),
    )
