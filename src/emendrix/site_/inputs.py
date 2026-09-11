"""What the site is built from: committed artifacts on disk, and nothing else.

```
<output-repo>/<corpus>/<act>/changes/<version>.json   the amendment events
reports/eval/<date>-<sha>.json                        the measured numbers
watchlist.toml                                        which acts are watched, and their labels
```

The same provenance story as the changelog itself: if a number is on a page it was read out
of the committed report or counted off the committed changelog documents, and if a sentence of
legal text is on a page it was read out of a changelog document a diff produced from two
published versions. Missing inputs are stated,
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

`polled` is a deployment fact of the same kind as the operator's name: a reading of the file
the poller on this instance writes, done at the CLI boundary and passed in as a value, so no
module below here knows that a poller exists or what it keeps.

`eurlex_url` and `published_url` are plain strings resolved at the CLI boundary, and they are
two different documents: the newest version an act has been consolidated to, which only a
recorded event can name, and the act as it was published, which is a reading of the act's own
identifier and is therefore known for an act nothing has happened to. `kinds` arrives the same
way, as words and counts rather than as the descriptors they were read off. This module renders
whatever corpus the loop ran on and holds no corpus knowledge; which URL, if any, an act has is
the composition root's business, and an amending act's number and address arrive the same way
into `amending`, whose model and harvest live in `site_.amending` so that the dependency
between the two modules runs one way and this one stays inside the size cap. Reading the
repository, ordering what it holds and counting it is `site_.entries`, split off for the same
reason: `corpus` is that rollup over the events this build renders, and it is where a page gets
a rate about the corpus a reader is browsing rather than about the report's labelled subset,
which answers a different question over a different denominator.

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
from emendrix.site_.chrome import PageChrome
from emendrix.site_.clocks import EventDate, VersionDates, event_date, sort_date
from emendrix.site_.entries import CorpusCounts, corpus_counts, sorted_entries
from emendrix.site_.polled import PolledState
from emendrix.site_.urls import shared_path
from emendrix.watch.config import Watchlist

__all__ = [
    "ActSite",
    "SiteInputs",
    "collect_site",
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
    published_url: str = Field(default="", description="The act as published; '' = none.")
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
    kinds: tuple[tuple[str, int], ...] = Field(
        default=(),
        description="What kinds of act the roster holds and how many of each, biggest group "
        "first, named at the CLI boundary. Empty when no watchlist declared a roster.",
    )
    configured: bool = False
    repo_url: str = Field(default="", description="Public home of the source, or ''.")
    changelogs_url: str = Field(default="", description="Public home of the changelog data, or ''.")
    site_url: str = Field(default="", description="Absolute base for feeds, or '' for none.")
    operator: str = Field(default="", description="Who runs this instance, or '' for nobody named.")
    operator_url: str = Field(default="", description="Public page of the operator, or ''.")
    contact: str = Field(default="", description="Address readers may write to, or ''.")
    polled: PolledState | None = Field(
        default=None,
        description="What the poller last did, when a deployment handed the build its state "
        "file. None where it handed it none, and the pages that would speak for it stay quiet.",
    )

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
    def corpus(self) -> CorpusCounts:
        """The rendered corpus, counted: what a page saying "this many, this often" may claim.

        Derived from `recent`, so the figures describe exactly the corpus on screen: an
        unwatched act's events are counted nowhere because they are rendered nowhere. Nothing
        may pass these in, for the same reason nothing may pass in `recent`'s order.
        """
        return corpus_counts(entry for _, entry in self.recent)

    @property
    def report_markdown(self) -> str:
        """Where a reader finds the report in the repository, by committed convention."""
        return f"{DEFAULT_REPORT_DIR.as_posix()}/{self.report.removesuffix('.json')}.md"


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
    polled: PolledState | None = None,
    eurlex_urls: dict[str, str] | None = None,
    published_urls: Mapping[str, str] | None = None,
    kinds: tuple[tuple[str, int], ...] = (),
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
    names never appears in `amending`, declared label or not. `published_urls` is keyed by the
    act's own slug, like `eurlex_urls`, and `kinds` is stored exactly as it is given: this module
    counts nothing and never learns what a kind is.
    """
    urls = eurlex_urls or {}
    published = published_urls or {}
    dates: VersionDates = version_dates or {}
    by_act: dict[ActId, list[ChangelogEntry]] = {}
    for entry in entries:
        by_act.setdefault(entry.act, []).append(entry)
    acts: list[ActSite] = []
    if watchlist is None:
        for act, found in by_act.items():
            acts.append(ActSite(act=act, label=act.key, entries=sorted_entries(found, dates)))
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
                    entries=sorted_entries(by_act.get(act, []), dates),
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
    for item in acts:
        # An act's events and its provisions are pages in one directory, addressed by two
        # vocabularies; two of them naming one path would write one page where the tree lists
        # both, the same refusal two acts sharing a slug get above.
        clash = shared_path(
            (entry.key for entry in item.entries),
            (e.change.location.canonical for entry in item.entries for e in entry.changes),
        )
        if clash is not None:
            raise ValueError(
                f"act {item.act} addresses an event and the provision {clash[1]!r} as {clash[0]!r}"
            )
    resolved = tuple(
        item.model_copy(
            update={
                "eurlex_url": urls.get(item.slug, ""),
                "published_url": published.get(item.slug, ""),
            }
        )
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
        kinds=kinds,
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
        polled=polled,
    )
