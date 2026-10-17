"""How a substance page names itself: its title, its description, its name and where it appears.

Composed here once and read by the page, its head and the search file, so a result a reader
clicks and the page it lands on describe one identifier one way. The words follow one rule
throughout: a page says where a number **appears**, in which entries of which acts, and never
what the law makes of the substance. Absence has one form, that no entry in the record prints
the number, because many entries name a group of substances and print no number at all.

Dates come from the corpus, the in-force date of the version a change was recorded in, and
never from the build. Nothing here escapes: a `<title>` is escaped by `chrome.page`, and every
other caller escapes what it prints.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.amending import AmendingAct, amenders, by_words
from emendrix.site_.clocks import event_date
from emendrix.site_.entry_table import SCHEMES
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import count
from emendrix.site_.substance_inputs import Holding, Moved, Substance
from emendrix.site_.titles import SUFFIX

__all__ = [
    "NAME_CAP",
    "changed_by",
    "cut_name",
    "entry_words",
    "first_version",
    "page_name",
    "place",
    "scheme_word",
    "standing_note",
    "substance_description",
    "substance_title",
]

NAME_CAP: Final = 40
"""How many characters of a name a title carries before it is cut on a word boundary."""


def scheme_word(scheme: str) -> str:
    """`CAS`, `EC`, `Index No`: what an identifier's scheme is called before its value."""
    return SCHEMES.get(scheme, scheme.upper())


def cut_name(name: str, cap: int = NAME_CAP) -> str:
    """A name cut at its first `;`, then at `cap` characters on a word boundary with a `…`.

    A cut at the `;` that leaves a parenthesis open, `2-Aminophenol (o-Aminophenol; CI 76520)`,
    goes back to before that parenthesis, so a title never prints half a bracket.
    """
    name = " ".join(name.split(";", 1)[0].split())
    while name.count("(") > name.count(")"):
        name = name[: name.rindex("(")].rstrip(" ,")
    if len(name) <= cap:
        return name
    head = name[:cap].rsplit(" ", 1)[0] if " " in name[:cap] else name[:cap]
    return f"{head.rstrip(' ,')}…"


def page_name(substance: Substance) -> str | None:
    """The shortest distinct name a current entry prints, else the newest history entry's."""
    names = [h.entry.name for h in substance.holdings if h.entry.name]
    if names:
        return cut_name(min(names, key=len))
    for moved in substance.history:
        if moved.side.name:
            return cut_name(moved.side.name)
    return None


def place(act: ActSite, unit: str) -> str:
    """`CLP Annex VI`: an act by its short label and the unit by its human name."""
    return f"{act.label} {unit}"


def _places(substance: Substance) -> list[tuple[ActSite, str]]:
    sources = [(h.act, h.entry.unit.human) for h in substance.holdings] or [
        (m.act, m.side.unit.human) for m in substance.history
    ]
    found: dict[tuple[str, str, str], tuple[ActSite, str]] = {}
    for act, unit in sources:
        found.setdefault((act.act.corpus, act.act.key, unit), (act, unit))
    return list(found.values())


def _where(substance: Substance) -> str:
    """`CLP Annex VI entry`; `A, B and C entries`; `entries in 4 acts`."""
    places = [place(act, unit) for act, unit in _places(substance)]
    if len(places) == 1:
        return f"{places[0]} entry"
    if len(places) <= 3:
        return f"{', '.join(places[:-1])} and {places[-1]} entries"
    acts = {act.act for act, _ in _places(substance)}
    return f"entries in {count(len(acts), 'act')}"


def entry_words(holding: Holding | Moved) -> str:
    """`CLP Annex VI section 3, table 2, Index No 605-001-00-5`, or the entry's name where the
    name is its key. The table's own container and, past the first, its ordinal: one key can be
    printed by two tables of one annex, and the two entries must not read as one."""
    if isinstance(holding, Holding):
        entry, table, act = holding.entry, holding.table, holding.act
    else:
        entry, table, act = holding.side, holding.table, holding.act
    label = table.key_label if table is not None else None
    if entry.key is None:
        key = "a row with no key"
    elif label:
        key = f"{label} {entry.key}"
    else:
        key = f"the entry for {cut_name(entry.name or entry.key, 60)}"
    table_no = f", table {entry.table}" if entry.table > 1 else ""
    return f"{place(act, entry.container.human)}{table_no}, {key}"


def changed_by(site: SiteInputs, moved: Moved) -> str:
    """`by X, the act that change names`, or '' where the change names no amending act.

    "Names" and never "made": a change records the amending acts its consolidation was read
    against, and that list can be shorter than the consolidation's own.
    """
    acts: tuple[AmendingAct, ...] = amenders(site.amending, moved.event)
    if not acts:
        return ""
    noun = "the act that change names" if len(acts) == 1 else "the acts that change names"
    return f"{by_words(acts)}, {noun}"


def first_version(act: ActSite) -> str | None:
    """The first version the record holds for an act, with its clock, or None with no event."""
    if not act.entries:
        return None
    return event_date(act.entries[-1]).human


def _since(substance: Substance) -> str:
    acts = [h.act for h in substance.holdings]
    first = first_version(acts[0]) if acts else None
    if first is None:
        return "No change to this entry is recorded."
    return f"No change to this entry since the first version the record holds, {first}."


def substance_title(substance: Substance) -> str:
    """`CAS 50-00-0 (formaldehyde): CLP Annex VI entry and every change`, then the suffix."""
    name = page_name(substance)
    named = f" ({name})" if name else ""
    head = f"{scheme_word(substance.scheme)} {substance.value}{named}"
    return f"{head}: {_where(substance)} and every change{SUFFIX}"


def _partner(substance: Substance) -> str:
    other = "ec" if substance.scheme == "cas" else "cas"
    found = next((one for one in substance.identifiers if one.scheme == other), None)
    return f", {scheme_word(found.scheme)} {found.value}" if found else ""


def substance_description(site: SiteInputs, substance: Substance) -> str:
    """Where the number appears and when an entry printing it last changed, in that order."""
    number = f"{scheme_word(substance.scheme)} {substance.value}"
    held = substance.holdings
    if held:
        firsts = [entry_words(holding) for holding in held[:2]]
        more = [f"and {len(held) - 2} more"] if len(held) > 2 else []
        listed = "; ".join([*firsts, *more])
        noun = "entry" if len(held) == 1 else "entries"
        lead = (
            f"{number}{_partner(substance)} appears in {len(held)} {noun} in the newest "
            f"versions emendrix holds: {listed}."
        )
    else:
        lead = f"No entry in the newest versions emendrix holds prints {number}."
    if not substance.history:
        return f"{lead} {_since(substance)}"
    newest = substance.history[0]
    by = changed_by(site, newest)
    return (
        f"{lead} Last changed in the version {newest.dated.words}{', ' + by if by else ''}: "
        "the row before and after, and its whole history."
    )


def standing_note(substance: Substance) -> str:
    """The note every substance page carries under its identifiers, its number filled in."""
    number = f"{scheme_word(substance.scheme)} {substance.value}"
    return (
        f"Where {number} appears: every table entry that prints it among its identifiers, in "
        "the newest version of each act this record holds, and every recorded change to those "
        "entries. Many entries name a group of substances and print no number, so absence here "
        "is not absence from the law. Not legal advice."
    )
