"""What the site is built from: committed artifacts on disk, and nothing else.

```
<output-repo>/<corpus>/<act>/changes/<version>.json   the amendment events
reports/eval/<date>-<sha>.json                        the measured numbers
watchlist.toml                                        which acts are watched, and their labels
```

The same provenance story as the changelog itself: if a number is on a page it was read out
of the committed report, and if a sentence of legal text is on a page it was read out of a
changelog document a diff produced from two published versions. Missing inputs are stated,
not raised: no changelog repository, an empty one, a watched act that has never been amended,
each is a page that says so.

Ordering is total and explicit, because two builds of one repository state have to produce one
tree: `glob` order is not sorted on every filesystem, acts sort by label then by key, and
every newest-first list of events sorts by `sort_date`, the consolidated version's own date
where the corpus resolved one, else `event_dated`. Why the two clocks may never share a sort
key is `clocks`' own story.

No absolute path reaches a page. Where the output repository lives is the operator's home
directory and a public site is the last place it belongs, so `configured` records only whether
there was one; the report is named by its file name and the committed convention, which is the
same string in a container and in a checkout.

`eurlex_url` is a plain string resolved at the CLI boundary. This module renders whatever
corpus the loop ran on and holds no corpus knowledge; which URL, if any, an act has is the
composition root's business, and an amending act's number and address arrive the same way into
`amending`, whose model and harvest live in `site_.amending` so that the dependency between the
two modules runs one way and this one stays inside the size cap.

No clock: `generated_on` arrives from the CLI boundary like every other date in this project.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId
from emendrix.eval_.report import DEFAULT_REPORT_DIR
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry
from emendrix.output.json_out import slug
from emendrix.site_.amending import AmendingAct, collect_amending
from emendrix.site_.attribution import unattributed
from emendrix.site_.clocks import EventDate, VersionDates, event_date, sort_date
from emendrix.watch.config import Watchlist

__all__ = [
    "ActSite",
    "PageChrome",
    "SiteInputs",
    "collect_site",
    "read_entries",
]


class ActSite(BaseModel):
    """One act as the site shows it: its label, its grouping, and every committed event."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    label: str = Field(min_length=1)
    long_name: str = Field(default="", description="The watchlist's long form, or ''.")
    domain: str = Field(default="", description="Index grouping; empty lands under 'Other'.")
    aliases: tuple[str, ...] = ()
    eurlex_url: str = Field(default="", description="Resolved at the CLI boundary; '' = none.")
    entries: tuple[ChangelogEntry, ...] = Field(
        default=(), description="Newest first by `sort_date`."
    )

    @property
    def slug(self) -> str:
        """The act's path segment: its own key, made filesystem-safe."""
        return slug(self.act.key)

    @property
    def headline(self) -> str:
        """What the page's H1 says: the long form when the watchlist gives one, else the label."""
        return self.long_name or self.label

    @property
    def newest_amendment(self) -> ChangelogEntry | None:
        """The newest event an amending act is named for; None when there is no such event.

        Newest by `sort_date`, the order `entries` arrives in. An event no amending act is
        named for is never the answer: this backs every "newest amendment" line the site
        prints, and one of those answered by such an event would dress it as an amendment. So
        `None` has two readings, told apart by `entries`, and each caller says which in words:
        nothing was ever seen, or everything seen names no amending act.
        """
        for entry in self.entries:
            if not unattributed(entry):
                return entry
        return None

    @property
    def dated(self) -> EventDate | None:
        """That event's date with its clock, or None. The clock is that entry's own, a true
        statement about it even when another entry carries a later detection date."""
        entry = self.newest_amendment
        return None if entry is None else event_date(entry)


class PageChrome(BaseModel):
    """The site-wide facts every page's shell renders, whatever the page is about.

    Gathered into one frozen model because `chrome.page` had reached ten keyword arguments,
    and its own docstring named an eleventh as the signal to gather rather than grow. It lives
    here rather than in `chrome` because `seo` reads this module and `chrome` reads `seo`, so
    this is the one place both can import it from without a cycle.

    `operator`, `operator_url` and `contact` are deployment facts like `site_url`: they arrive
    on the command line and nothing about them is committed, so a build that names nobody is
    the normal state and every page that reads them says nothing rather than something blank.
    """

    model_config = ConfigDict(frozen=True)

    generated_on: date = Field(description="Passed in at the CLI boundary; never clock-read.")
    repo_url: str = Field(default="", description="Public home of the source, or ''.")
    changelogs_url: str = Field(default="", description="Public home of the changelog data, or ''.")
    site_url: str = Field(default="", description="Absolute base for feeds, or '' for none.")
    operator: str = Field(default="", description="Who runs this instance, or '' for nobody named.")
    operator_url: str = Field(default="", description="Public page of the operator, or ''.")
    contact: str = Field(default="", description="Address readers may write to, or ''.")


class SiteInputs(BaseModel):
    """Everything the site renders, resolved. Frozen, so no renderer can rebind a field."""

    model_config = ConfigDict(frozen=True)

    generated_on: date = Field(description="Passed in at the CLI boundary; never clock-read.")
    run: EvalRun
    report: str = Field(min_length=1, description="Report file name, never its path.")
    acts: tuple[ActSite, ...] = ()
    recent: tuple[tuple[ActSite, ChangelogEntry], ...] = Field(
        default=(),
        description="Every event with its act, newest first by `sort_date`. Resolved once "
        "in `collect_site`; nothing downstream recomputes an order.",
    )
    amending: Mapping[str, AmendingAct] = Field(
        default_factory=dict,
        description="Every amending act a committed change names, by key, sorted by key. The "
        "one mapping here, so the one field a caller could write into and the reason these "
        "inputs are not hashable; every renderer is a pure function of what it is handed.",
    )
    configured: bool = False
    repo_url: str = Field(default="", description="Public home of the source, or ''.")
    changelogs_url: str = Field(default="", description="Public home of the changelog data, or ''.")
    site_url: str = Field(default="", description="Absolute base for feeds, or '' for none.")
    operator: str = Field(default="", description="Who runs this instance, or '' for nobody named.")
    operator_url: str = Field(default="", description="Public page of the operator, or ''.")
    contact: str = Field(default="", description="Address readers may write to, or ''.")

    @property
    def chrome(self) -> PageChrome:
        """The shell's slice of these inputs, in the one form `chrome.page` accepts."""
        return PageChrome(
            generated_on=self.generated_on,
            repo_url=self.repo_url,
            changelogs_url=self.changelogs_url,
            site_url=self.site_url,
            operator=self.operator,
            operator_url=self.operator_url,
            contact=self.contact,
        )

    @property
    def report_markdown(self) -> str:
        """Where a reader finds the report in the repository, by committed convention."""
        return f"{DEFAULT_REPORT_DIR.as_posix()}/{self.report.removesuffix('.json')}.md"


def read_entries(root: Path) -> tuple[ChangelogEntry, ...]:
    """Every committed event in one output repository, in sorted path order.

    The layout and the documents are the output repository writer's own, so a file that does
    not validate means the repository was edited by hand or written by a different version of
    the schema: loud, named, and not something to skip quietly.
    """
    entries: list[ChangelogEntry] = []
    for path in sorted(root.glob("*/*/changes/*.json")):
        try:
            entries.append(ChangelogEntry.model_validate_json(path.read_bytes()))
        except ValueError as error:
            raise ValueError(f"{path} is not a changelog document emendrix wrote: {error}") from (
                error
            )
    return tuple(entries)


def _sorted_entries(
    entries: list[ChangelogEntry], version_dates: VersionDates
) -> tuple[ChangelogEntry, ...]:
    """One act's events, newest first by `sort_date`, the version tag breaking a shared date."""
    return tuple(
        sorted(
            entries,
            key=lambda e: (sort_date(e, version_dates).isoformat(), e.key),
            reverse=True,
        )
    )


def collect_site(
    *,
    generated_on: date,
    run: EvalRun,
    report: Path,
    entries: tuple[ChangelogEntry, ...] = (),
    watchlist: Watchlist | None = None,
    configured: bool = False,
    repo_url: str = "",
    changelogs_url: str = "",
    site_url: str = "",
    operator: str = "",
    operator_url: str = "",
    contact: str = "",
    eurlex_urls: dict[str, str] | None = None,
    amending_numbers: Mapping[str, str] | None = None,
    amending_urls: Mapping[str, str] | None = None,
    version_dates: VersionDates | None = None,
) -> SiteInputs:
    """Group the committed entries under their acts. Pure and total.

    With a watchlist, the watchlist is the roster: watched acts appear even with no events
    (a quiet act is a real answer), unwatched entries do not appear at all. Without one,
    the changelog repository is the roster.

    `version_dates` is consumed here, ordering `entries` and `recent`, and never stored:
    once the lists are resolved there is nothing left for a renderer to ask it.

    `amending_numbers` and `amending_urls` are keyed by the amending act's own key and hold what
    the composition root rendered from an identifier this module may not read; an act nothing
    names never appears in `amending`, declared label or not.
    """
    urls = eurlex_urls or {}
    dates: VersionDates = version_dates or {}
    by_act: dict[ActId, list[ChangelogEntry]] = {}
    for entry in entries:
        by_act.setdefault(entry.act, []).append(entry)
    acts: list[ActSite] = []
    if watchlist is None:
        for act, found in by_act.items():
            acts.append(ActSite(act=act, label=act.key, entries=_sorted_entries(found, dates)))
    else:
        for watched in watchlist.acts:
            act = watched.act
            acts.append(
                ActSite(
                    act=act,
                    # The act's own key, not the config field it was written in: this module
                    # renders whatever corpus the loop ran on and reads no corpus vocabulary.
                    label=watched.name or act.key,
                    long_name=watched.long_name or "",
                    domain=watched.domain or "",
                    aliases=watched.aliases,
                    entries=_sorted_entries(by_act.get(act, []), dates),
                )
            )
    acts.sort(key=lambda item: (item.label.casefold(), item.act.key))
    seen: dict[str, ActId] = {}
    for item in acts:
        if item.slug in seen:
            raise ValueError(
                f"acts {seen[item.slug]} and {item.act} share the URL slug {item.slug!r}"
            )
        seen[item.slug] = item.act
    resolved = tuple(
        item.model_copy(update={"eurlex_url": urls[item.slug]}) if item.slug in urls else item
        for item in acts
    )
    pairs = [(item, entry) for item in resolved for entry in item.entries]
    pairs.sort(
        key=lambda pair: (
            sort_date(pair[1], dates).isoformat(),
            str(pair[1].to_version),
            str(pair[1].act),
        ),
        reverse=True,
    )
    named = watchlist.amending_acts if watchlist else ()
    return SiteInputs(
        generated_on=generated_on,
        run=run,
        report=report.name,
        acts=resolved,
        recent=tuple(pairs),
        amending=collect_amending(
            entries,
            labels={item.celex: item.name for item in named},
            numbers=amending_numbers,
            urls=amending_urls,
        ),
        configured=configured,
        repo_url=repo_url,
        changelogs_url=changelogs_url,
        site_url=site_url,
        operator=operator,
        operator_url=operator_url,
        contact=contact,
    )
