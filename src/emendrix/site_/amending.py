"""Which instrument made an event, and what the site is allowed to call it.

The pipeline's unit is a version transition and its attribution is per change: every
`Change.amending_acts` entry is an act a signal named as amending that provision. This module
turns that into the reader's object, the instrument, and into the words a page may print for
it. Nothing here decides anything about the law: an act appears because a committed document
names it, and the name it is shown under is a label, a mechanical rendering of its identifier,
or the identifier itself.

Four names, in the order a heading prefers them:

1. **The declared label.** `[[amending_acts]]` in the watchlist, `Digital Omnibus on AI`. A
   label of the same rank as an act's own `name`, never identity, never matched on.
2. **The official number**, `Regulation (EU) 2026/1744`, rendered from the CELEX at the CLI
   boundary by the convention of the act's year and handed in as a plain string. The CELEX
   stays beside it on every surface, because the number is a reading of the identifier and the
   identifier is the fact.
3. **The recorded official title**, verbatim, where a committed document carries one. Two
   places in the emitted schema may: `change.amending_acts[*].display_name`, which the metadata
   path leaves unset, and `corroboration.signals[*].claims[*].amending_act.display_name`, which
   the instruction parse fills. Both are read, first non-empty wins, and neither is edited.
4. **The key**, when nothing else is known. A key is always shown; a bare one is honest.

Why this module holds the markup as well as the words: an act's name is a fact with a link, a
code and an optional title beside it, and writing that group in one place is what keeps the
event page and the act page's card from naming one instrument two ways. `site_/inputs.py`
imports `AmendingAct` and `collect_amending` from here rather than the other way round, so the
dependency runs one way and this module never needs to know what `SiteInputs` is; the read
helpers take the resolved mapping instead. That split is also what keeps `inputs.py` under the
size cap, the harvest being the larger half of the work.

No corpus vocabulary: keys and numbers arrive as strings, and this module never parses one.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping

from pydantic import BaseModel, ConfigDict, Field

from emendrix.output import ChangelogEntry
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.urls import amendment_href

__all__ = [
    "AmendingAct",
    "amenders",
    "amending_keys",
    "amending_lines",
    "amending_links",
    "by_words",
    "collect_amending",
    "mentioned_keys",
    "resolve",
]


class AmendingAct(BaseModel):
    """One instrument that amended a watched act, as the site names it. Labels, never identity."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1, description="The act's key in its corpus; the identity.")
    number: str = Field(
        default="",
        description="The official number rendered from the key at the CLI boundary, or ''.",
    )
    title: str = Field(
        default="", description="The official title a committed document recorded, or ''."
    )
    label: str = Field(default="", description="The watchlist's short name for it, or ''.")
    eurlex_url: str = Field(default="", description="Resolved at the CLI boundary; '' = none.")

    @property
    def short(self) -> str:
        """What a heading calls it: the declared label, else the official number, else the key."""
        return self.label or self.number or self.key


def _mentions(entries: Iterable[ChangelogEntry]) -> Iterator[tuple[str, str]]:
    """Every mention of an amending act in these entries, as `(key, title)`, in document order.

    `title` is `""` where the mention carries none, which is the normal state of the per-change
    mentions: the metadata path mints the id from an annotation that has no title in it. A
    diff-only entry has no corroboration report at all and a claim need not name an act, so
    both are guarded rather than assumed.
    """
    for entry in entries:
        for emitted in entry.changes:
            for act in emitted.change.amending_acts:
                yield act.key, act.display_name or ""
        report = entry.corroboration
        if report is None:
            continue
        for units in report.signals:
            for claim in units.claims:
                if claim.amending_act is not None:
                    named = claim.amending_act
                    yield named.key, named.display_name or ""


def mentioned_keys(entries: Iterable[ChangelogEntry]) -> tuple[str, ...]:
    """Every amending act any of these entries names, first mention first, each once."""
    seen: dict[str, None] = {}
    for key, _ in _mentions(entries):
        seen.setdefault(key, None)
    return tuple(seen)


def collect_amending(
    entries: Iterable[ChangelogEntry],
    *,
    labels: Mapping[str, str] | None = None,
    numbers: Mapping[str, str] | None = None,
    urls: Mapping[str, str] | None = None,
) -> dict[str, AmendingAct]:
    """Every amending act the committed documents name, resolved and keyed, sorted by key.

    Sorted because the mapping rides in `SiteInputs` and two builds of one repository state
    have to produce identical bytes; display order is `amending_keys`' business and is the
    order the document itself mentions them in.
    """
    titles: dict[str, str] = {}
    for key, title in _mentions(entries):
        if title and not titles.get(key):
            titles[key] = title
        titles.setdefault(key, "")
    declared = labels or {}
    rendered = numbers or {}
    addresses = urls or {}
    return {
        key: AmendingAct(
            key=key,
            number=rendered.get(key, ""),
            title=titles[key],
            label=declared.get(key, ""),
            eurlex_url=addresses.get(key, ""),
        )
        for key in sorted(titles)
    }


def amending_keys(entry: ChangelogEntry) -> tuple[str, ...]:
    """Every amending act the entry's changes name, first mention first, each once.

    The changes only, not the corroboration claims: what a page says made an event is what the
    merged changes carry, and a claim the merge did not attach to any change is a record of
    what a signal said rather than a statement about this event.
    """
    seen: dict[str, None] = {}
    for emitted in entry.changes:
        for act in emitted.change.amending_acts:
            seen.setdefault(act.key, None)
    return tuple(seen)


def resolve(known: Mapping[str, AmendingAct], key: str) -> AmendingAct:
    """One key through the collected mapping, or a bare `AmendingAct` carrying only the key.

    A name the site cannot improve on is still a name, and dropping the mention would be the
    one thing worse than showing an identifier. One function rather than a fallback repeated
    at each call site, so a page that resolves a key and a page that lists one cannot disagree
    about what an unknown key is called.
    """
    return known.get(key) or AmendingAct(key=key)


def amenders(known: Mapping[str, AmendingAct], entry: ChangelogEntry) -> tuple[AmendingAct, ...]:
    """`amending_keys` resolved through the collected mapping, in the entry's own order."""
    return tuple(resolve(known, key) for key in amending_keys(entry))


def by_words(acts: tuple[AmendingAct, ...]) -> str:
    """`by Digital Omnibus on AI`, `by A and B`, `by A and 2 others`; `''` for none.

    The clause a title, a card and a roster row carry, so it names at most two instruments and
    counts the rest: one consolidation can fold several, and one committed event names seven.
    A title has room for a name, not for a list. Unescaped, like every other string the site
    composes: the caller escapes it or hands it to a `<title>`, which `chrome` escapes.
    """
    names = [act.short for act in acts]
    if not names:
        return ""
    if len(names) == 1:
        return f"by {names[0]}"
    if len(names) == 2:
        return f"by {names[0]} and {names[1]}"
    return f"by {names[0]} and {len(names) - 1} others"


def _one_line(act: AmendingAct) -> Html:
    """One instrument, named: the number linked where there is an address, then the code.

    The label rides between them where the watchlist declares one, so a reader who knows the
    instrument by its short name and a reader who knows it by its number both find it, and the
    identifier closes the group either way.
    """
    name = escape(act.number) if act.number else escape(act.key)
    code = Html(f" <code>{escape(act.key)}</code>") if act.number else Html("")
    named = Html(f'<a href="{escape(act.eurlex_url)}">{name}</a>') if act.eurlex_url else Html(name)
    label = Html(f' <span class="ttl">{escape(act.label)}</span>') if act.label else Html("")
    return Html(f"{named}{label}{code}")


def amending_lines(acts: tuple[AmendingAct, ...], *, full: bool) -> list[Html]:
    """The instrument line, and on a full page the official titles under it.

    Empty for an event that names none: what a page says then is `attribution.py`'s sentence,
    and a line saying nothing above it would be a second answer to one question.

    `full` is false on the act page's timeline card, where thirty events would print thirty
    official titles and the reader is scanning dates. On the event's own page the titles are
    printed verbatim, because the words a reader searched for are in them and this is the one
    surface with room. They carry `.official`, the class the act page already prints its own
    act's official title under: one kind of fact, one treatment.
    """
    if not acts:
        return []
    lines = [
        Html(f'<p class="amending">Amended by {join([_one_line(act) for act in acts], " · ")}</p>')
    ]
    if full:
        lines.extend(
            Html(f'<p class="official">{escape(act.title)}</p>') for act in acts if act.title
        )
    return lines


def amending_links(acts: tuple[AmendingAct, ...], root: str) -> list[Html]:
    """The instrument line with each name linking the instrument's own page under `root`.

    A provision page's form of `amending_lines`. A step there is one row of one coordinate's
    history and the question it answers is which instrument moved it, so the name goes to that
    instrument's page, where the rest of its work is; the official address is on the event page
    one link away and is not printed again per step. The name and the identifier are the pair
    `_one_line` prints, in that order, so no surface names one instrument two ways.

    `root` is the prefix that climbs from the page to the site root, computed by the caller,
    which is the convention every cross-page link on the site follows.
    """
    if not acts:
        return []
    named = [
        Html(
            f'<a href="{escape(root + amendment_href(act.key))}">{escape(act.short)}</a>'
            + (f" <code>{escape(act.key)}</code>" if act.short != act.key else "")
        )
        for act in acts
    ]
    return [Html(f'<p class="amending">Amended by {join(named, " · ")}</p>')]
