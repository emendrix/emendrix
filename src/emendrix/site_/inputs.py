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
events sort by the date they came into force, then by version tag and act.

No absolute path reaches a page. Where the output repository lives is the operator's home
directory and a public site is the last place it belongs, so `configured` records only whether
there was one; the report is named by its file name and the committed convention, which is the
same string in a container and in a checkout.

`eurlex_url` is a plain string resolved at the CLI boundary. This module renders whatever
corpus the loop ran on and holds no corpus knowledge; which URL, if any, an act has is the
composition root's business.

No clock: `generated_on` arrives from the CLI boundary like every other date in this project.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId
from emendrix.eval_.report import DEFAULT_REPORT_DIR
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry
from emendrix.output.json_out import slug
from emendrix.watch.config import Watchlist

__all__ = ["ActSite", "PageChrome", "SiteInputs", "collect_site", "event_dated", "read_entries"]


def event_dated(entry: ChangelogEntry) -> date:
    """When an event took effect: clock 1 if the changes carry it, else when it was seen."""
    return max(entry.in_force) if entry.in_force else entry.detected_on


class ActSite(BaseModel):
    """One act as the site shows it: its label, its grouping, and every committed event."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    label: str = Field(min_length=1)
    domain: str = Field(default="", description="Index grouping; empty lands under 'Other'.")
    aliases: tuple[str, ...] = ()
    eurlex_url: str = Field(default="", description="Resolved at the CLI boundary; '' = none.")
    entries: tuple[ChangelogEntry, ...] = Field(default=(), description="Newest first.")

    @property
    def slug(self) -> str:
        """The act's path segment: its own key, made filesystem-safe."""
        return slug(self.act.key)

    @property
    def dated(self) -> date | None:
        """The newest event's date, for the index; None when nothing was ever seen."""
        return event_dated(self.entries[0]) if self.entries else None


class PageChrome(BaseModel):
    """The site-wide facts every page's shell renders, whatever the page is about.

    Gathered into one frozen model because `chrome.page` had reached ten keyword arguments,
    and its own docstring named an eleventh as the signal to gather rather than grow. It lives
    here rather than in `chrome` because `seo` reads this module and `chrome` reads `seo`, so
    this is the one place both can import it from without a cycle.
    """

    model_config = ConfigDict(frozen=True)

    generated_on: date = Field(description="Passed in at the CLI boundary; never clock-read.")
    repo_url: str = Field(default="", description="Public home of the source, or ''.")
    changelogs_url: str = Field(default="", description="Public home of the changelog data, or ''.")
    site_url: str = Field(default="", description="Absolute base for feeds, or '' for none.")


class SiteInputs(BaseModel):
    """Everything the site renders, resolved. Frozen, so rendering cannot change it."""

    model_config = ConfigDict(frozen=True)

    generated_on: date = Field(description="Passed in at the CLI boundary; never clock-read.")
    run: EvalRun
    report: str = Field(min_length=1, description="Report file name, never its path.")
    acts: tuple[ActSite, ...] = ()
    configured: bool = False
    repo_url: str = Field(default="", description="Public home of the source, or ''.")
    changelogs_url: str = Field(default="", description="Public home of the changelog data, or ''.")
    site_url: str = Field(default="", description="Absolute base for feeds, or '' for none.")

    @property
    def chrome(self) -> PageChrome:
        """The shell's slice of these inputs, in the one form `chrome.page` accepts."""
        return PageChrome(
            generated_on=self.generated_on,
            repo_url=self.repo_url,
            changelogs_url=self.changelogs_url,
            site_url=self.site_url,
        )

    @property
    def report_markdown(self) -> str:
        """Where a reader finds the report in the repository, by committed convention."""
        return f"{DEFAULT_REPORT_DIR.as_posix()}/{self.report.removesuffix('.json')}.md"

    @property
    def recent(self) -> tuple[tuple[ActSite, ChangelogEntry], ...]:
        """Every event on the site, newest first, with the act it belongs to."""
        pairs = [(act, entry) for act in self.acts for entry in act.entries]
        pairs.sort(
            key=lambda pair: (
                event_dated(pair[1]).isoformat(),
                str(pair[1].to_version),
                str(pair[1].act),
            ),
            reverse=True,
        )
        return tuple(pairs)


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


def _sorted_entries(entries: list[ChangelogEntry]) -> tuple[ChangelogEntry, ...]:
    """One act's events, newest first, with the version tag breaking a shared date."""
    return tuple(sorted(entries, key=lambda e: (event_dated(e).isoformat(), e.key), reverse=True))


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
    eurlex_urls: dict[str, str] | None = None,
) -> SiteInputs:
    """Group the committed entries under their acts. Pure and total.

    With a watchlist, the watchlist is the roster: watched acts appear even with no events
    (a quiet act is a real answer), unwatched entries do not appear at all. Without one,
    the changelog repository is the roster.
    """
    urls = eurlex_urls or {}
    by_act: dict[ActId, list[ChangelogEntry]] = {}
    for entry in entries:
        by_act.setdefault(entry.act, []).append(entry)
    acts: list[ActSite] = []
    if watchlist is None:
        for act, found in by_act.items():
            acts.append(ActSite(act=act, label=act.key, entries=_sorted_entries(found)))
    else:
        for watched in watchlist.acts:
            act = watched.act
            acts.append(
                ActSite(
                    act=act,
                    # The act's own key, not the config field it was written in: this module
                    # renders whatever corpus the loop ran on and reads no corpus vocabulary.
                    label=watched.name or act.key,
                    domain=watched.domain or "",
                    aliases=watched.aliases,
                    entries=_sorted_entries(by_act.get(act, [])),
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
    return SiteInputs(
        generated_on=generated_on,
        run=run,
        report=report.name,
        acts=resolved,
        configured=configured,
        repo_url=repo_url,
        changelogs_url=changelogs_url,
        site_url=site_url,
    )
