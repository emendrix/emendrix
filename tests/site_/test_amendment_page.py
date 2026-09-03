"""One amending instrument's page: every watched act it moved, and only the work it did there.

The page gathers what the event pages already carry, so what needs asserting is the gathering:
that an act it amended appears once with its own events, that a coordinate is listed under the
instrument its own change names and under no other, and that the machine-readable claim says
`legislationChanges` rather than something schema.org has no property for.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from site_entries import attributed_entry

from emendrix.core import ActId
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry
from emendrix.site_.amending import AmendingAct, resolve
from emendrix.site_.build import write_site
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.instruments import amended_by
from emendrix.site_.pages.amendment import render_amendment_page
from emendrix.site_.pages.amendments_index import render_amendments_index
from emendrix.watch.config import Watchlist
from toy_corpus import AMENDMENT

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)
SECOND = ActId(corpus="toy", key="second-house")


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _site(*entries: ChangelogEntry, watchlist: Watchlist | None = None) -> SiteInputs:
    return collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=entries,
        watchlist=watchlist,
        site_url="https://example.invalid/site",
    )


def _two_acts() -> SiteInputs:
    """The toy transition on two acts, both attributed to the one toy instrument."""
    first = attributed_entry()
    return _site(first, first.model_copy(update={"act": SECOND}))


def _page(site: SiteInputs, key: str) -> str:
    return render_amendment_page(site, resolve(site.amending, key), amended_by(site)[key])


def test_the_page_lists_every_watched_act_the_instrument_amended_once() -> None:
    site = _two_acts()
    rendered = _page(site, AMENDMENT.key)
    assert f"<h1>{AMENDMENT.key}</h1>" in rendered
    for act in site.acts:
        assert rendered.count(f'<h2><a href="../../acts/{act.slug}/">') == 1, act.slug
    assert rendered.count('<article class="event"') == 2
    assert "2 watched acts amended · in 2 events" in rendered


def test_a_coordinate_is_listed_under_the_instrument_its_own_change_names() -> None:
    """One consolidation can fold several instruments, so the list is filtered per change.

    The second entry's changes keep the instrument on the first change alone, which is the
    shape a folded consolidation has: the event is still the instrument's, and three quarters
    of what the event did is not.
    """
    whole = attributed_entry()
    kept = whole.changes[0]
    stripped = tuple(
        emitted.model_copy(
            update={"change": emitted.change.model_copy(update={"amending_acts": ()})}
        )
        for emitted in whole.changes[1:]
    )
    partial = whole.model_copy(update={"act": SECOND, "changes": (kept, *stripped)})
    site = _site(whole, partial)
    rendered = _page(site, AMENDMENT.key)
    listed = rendered.count("Attributed to this instrument:")
    assert listed == 2
    coordinates = [emitted.change.location.human for emitted in whole.changes]
    section = rendered.split(f'<h2><a href="../../acts/{SECOND.key}/">')[1].split("</section>")[0]
    for dropped in coordinates[1:]:
        assert f">{dropped}</a>" not in section, dropped
    assert f">{coordinates[0]}</a>" in section


def test_the_structured_data_names_every_act_the_instrument_changed() -> None:
    site = _two_acts()
    rendered = _page(site, AMENDMENT.key)
    body = rendered.split('<script type="application/ld+json">')[1].split("</script>")[0]
    crumbs, described = json.loads(body)
    assert [item["name"] for item in crumbs["itemListElement"]] == [
        "emendrix",
        "Amending instruments",
        AMENDMENT.key,
    ]
    about = described["about"]
    assert about["legislationIdentifier"] == AMENDMENT.key
    assert "legislationAmends" not in rendered
    changed = [item["name"] for item in about["legislationChanges"]]
    assert sorted(changed) == sorted(act.headline for act in site.acts)


def test_an_instrument_with_no_declared_name_and_no_title_is_headed_by_what_is_known() -> None:
    """The number where a CELEX rendered one, else the bare key. A key is always honest."""
    site = _two_acts()
    numbered = dict(site.amending)
    numbered[AMENDMENT.key] = AmendingAct(key=AMENDMENT.key, number="Regulation (EU) 2026/1")
    with_number = site.model_copy(update={"amending": numbered})
    rendered = _page(with_number, AMENDMENT.key)
    assert "<h1>Regulation (EU) 2026/1</h1>" in rendered
    assert f"<code>{AMENDMENT.key}</code>" in rendered
    assert '<p class="official">' not in rendered
    assert "Regulation (EU) 2026/1: every watched act it amended — emendrix" in rendered

    bare = site.model_copy(update={"amending": {AMENDMENT.key: AmendingAct(key=AMENDMENT.key)}})
    assert f"<h1>{AMENDMENT.key}</h1>" in _page(bare, AMENDMENT.key)


def test_the_declared_label_heads_the_page_with_the_number_and_title_under_it() -> None:
    """The one surface that prints the recorded official title verbatim beside the number."""
    site = _two_acts()
    named = dict(site.amending)
    named[AMENDMENT.key] = site.amending[AMENDMENT.key].model_copy(
        update={"label": "The June rules", "number": "Regulation (EU) 2026/1"}
    )
    rendered = _page(site.model_copy(update={"amending": named}), AMENDMENT.key)
    assert "<h1>The June rules</h1>" in rendered
    assert '<p class="official">Regulation (EU) 2026/1</p>' in rendered
    assert '<p class="official">Rule change, June</p>' in rendered
    assert "The June rules (Regulation (EU) 2026/1): every watched act it amended" in rendered


def test_an_instrument_no_committed_event_names_gets_no_page(tmp_path: Path) -> None:
    """A declared short name is not evidence: a page for it would describe work nobody recorded.

    Two routes to the same answer, because the site could lose either. The harvest never
    collects a key no document mentions, so a `[[amending_acts]]` block on its own reaches
    nothing; and a key that is in the mapping but that no watched act's event names still gets
    no page, which is the state an event of an unwatched act produces.
    """
    watchlist = Watchlist.model_validate(
        {
            "acts": [{"celex": "32016R0679", "name": "GDPR"}],
            "amending_acts": [{"celex": "32026R1744", "name": "Digital Omnibus on AI"}],
            "output": {"repo_path": str(tmp_path / "repo")},
        }
    )
    site = _site(watchlist=watchlist)
    assert site.amending == {}
    unnamed = site.model_copy(
        update={"amending": {"32026R1744": AmendingAct(key="32026R1744", label="Omnibus")}}
    )
    assert amended_by(unnamed) == {}
    written = {path.as_posix() for path in write_site(tmp_path / "site", unnamed)}
    assert "amendments/index.html" in written
    assert not any(name.startswith("amendments/32026R1744") for name in written)
    assert "No committed event names an amending instrument yet" in render_amendments_index(unnamed)


def test_the_index_lists_every_instrument_with_a_page_under_the_year_of_its_newest_event() -> None:
    site = _two_acts()
    rendered = render_amendments_index(site)
    assert "<h1>Amending instruments</h1>" in rendered
    assert "1 instrument named by a committed event" in rendered
    assert "2 amendment events" in rendered
    assert f'<a href="../amendments/{AMENDMENT.key}/">' in rendered
    assert "<h2>2026</h2>" in rendered
    assert rendered.count("<li>") == 1
