"""What the twin pages show, resolved once from the committed maps and the record.

A twin page is about one pair of units, each the other's best textual match, and says what the
committed map says about them: the score, the versions they were paired on, the aligned
sub-provisions, the differing passages or that they were withheld, and where to read both
whole. The record adds one thing the map cannot hold, the changes to either unit recorded
after the version it was paired on, newest first, each linking the version page that carries
it. Before those versions a change is already in the texts that were compared.

Every view is frozen and every tuple keeps the map's order, A's document order, so two builds
of one repository state render the same bytes. Nothing here reads the text store: the passages
are the map's, which is the one place a twin page's quoted words come from.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId
from emendrix.site_.clocks import sort_date
from emendrix.site_.history import ProvisionStep, histories
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.twin_inputs import pageless, pair_slug
from emendrix.site_.urls import twin_page_href, twin_pair_href
from emendrix.twins.model import TwinMap, TwinPair, TwinSide

__all__ = ["TwinChange", "TwinPageView", "TwinPairView", "TwinSideView", "twin_views"]


class TwinSideView(BaseModel):
    """One unit of a pair, in its act, and where a reader can read it whole."""

    model_config = ConfigDict(frozen=True)

    act: ActSite = Field(description="The act the unit belongs to, as the site shows it.")
    unit: str = Field(description="The unit's canonical location.")
    version: str = Field(description="The version of the act the pair was computed on.")
    paired_on: date | None = Field(description="That version's date, where one was resolved.")
    url: str = Field(description="Its public address in that version, or ''.")
    page: bool = Field(description="Whether the site wrote a provision page for the unit.")


class TwinChange(BaseModel):
    """One recorded change to either unit after the version its act was paired on."""

    model_config = ConfigDict(frozen=True)

    act: ActSite = Field(description="The act whose unit the change touched.")
    step: ProvisionStep = Field(description="The change, its entry and its version-page anchor.")
    on: date = Field(description="The version's date, the order the list is newest first by.")


class TwinPageView(BaseModel):
    """One pair whose texts differ in more than numbering: everything its page shows."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description="The page's site-root-relative path.")
    pair: TwinPair = Field(description="The pair, as the committed map holds it.")
    a: TwinSideView
    b: TwinSideView
    changes: tuple[TwinChange, ...] = Field(description="Newest first; empty for none.")


class TwinPairView(BaseModel):
    """One pair of acts: the committed map, both acts and a page view per pair that has one."""

    model_config = ConfigDict(frozen=True)

    slug: str = Field(description="The map's file stem, every address's name for the pair.")
    path: str = Field(description="The pair index's site-root-relative path.")
    document: TwinMap = Field(description="The committed map.")
    a: ActSite
    b: ActSite
    pages: tuple[TwinPageView, ...] = Field(description="In A's document order.")

    def page_of(self, pair: TwinPair) -> TwinPageView | None:
        """The page of a pair, or None for one with no page (see `pageless`)."""
        return next((view for view in self.pages if view.pair == pair), None)


def _act_id(side: TwinSide) -> ActId:
    return ActId(corpus=side.corpus, key=side.key)


def _side(
    site: SiteInputs, act: ActSite, side: TwinSide, unit: str, pages: set[str]
) -> TwinSideView:
    return TwinSideView(
        act=act,
        unit=unit,
        version=side.version,
        paired_on=site.twins.dates.get(side.version),
        url=site.twins.urls.get(side.version, {}).get(unit, ""),
        page=unit in pages,
    )


def _changes(
    site: SiteInputs, side: TwinSideView, steps: dict[str, tuple[ProvisionStep, ...]]
) -> list[TwinChange]:
    """The unit's recorded changes after its paired version; every one where it has no date."""
    found = []
    for step in steps.get(side.unit, ()):
        on = sort_date(step.entry, site.version_dates)
        if side.paired_on is None or on > side.paired_on:
            found.append(TwinChange(act=side.act, step=step, on=on))
    return found


def twin_views(site: SiteInputs) -> tuple[TwinPairView, ...]:
    """Every shown map's views, in the maps' sorted path order."""
    shown = {str(act.act): act for act in site.acts}
    stepped: dict[str, dict[str, tuple[ProvisionStep, ...]]] = {}
    views: list[TwinPairView] = []
    for document in site.twins.maps:
        a, b = shown[str(_act_id(document.a))], shown[str(_act_id(document.b))]
        for act in (a, b):
            if str(act.act) not in stepped:
                stepped[str(act.act)] = {
                    one.location.canonical: one.steps for one in histories(act)
                }
        slug = pair_slug(document)
        pages: list[TwinPageView] = []
        for pair in document.pairs:
            if pageless(pair):
                continue
            left = _side(site, a, document.a, pair.a, set(stepped[str(a.act)]))
            right = _side(site, b, document.b, pair.b, set(stepped[str(b.act)]))
            changes = [
                *_changes(site, left, stepped[str(a.act)]),
                *_changes(site, right, stepped[str(b.act)]),
            ]
            changes.sort(key=lambda change: change.on, reverse=True)
            pages.append(
                TwinPageView(
                    path=twin_page_href(slug, pair.a),
                    pair=pair,
                    a=left,
                    b=right,
                    changes=tuple(changes),
                )
            )
        views.append(
            TwinPairView(
                slug=slug,
                path=twin_pair_href(slug),
                document=document,
                a=a,
                b=b,
                pages=tuple(pages),
            )
        )
    return tuple(views)
