"""A version in a list and a version on its own page are two components, not one.

The card is a point on the act's rail, headed by the version's name as its one link; the
version page opens with a masthead that is the page's subject. They share the helpers that read
the document's facts and never their markup. Both keep the addresses the site has published,
and every amending act they name goes to its page on this site, with EUR-Lex offered after it.
"""

from __future__ import annotations

import re
from pathlib import Path

from site_entries import attributed_entry

from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_.amending import AmendingAct
from emendrix.site_.build import write_site
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.pages.act import render_act
from emendrix.site_.pages.event import render_event_page
from emendrix.site_.pages.texts import text_blocks
from toy_corpus import AMENDMENT

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
_EURLEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32026R0001"


def _site() -> SiteInputs:
    """One attributed version, its amending act given a number and an address to link."""
    entry = attributed_entry()
    site = collect_site(
        generated_on=entry.detected_on,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(entry,),
    )
    known = dict(site.amending)
    known[AMENDMENT.key] = AmendingAct(
        key=AMENDMENT.key,
        number="Regulation (EU) 2026/1",
        title="Rule change, June",
        eurlex_url=_EURLEX,
    )
    return site.model_copy(update={"amending": known})


def _masthead(rendered: str) -> str:
    return rendered.split('<div class="version-masthead"')[1].split('<h2 class="section">')[0]


def test_the_card_and_the_masthead_are_different_markup() -> None:
    site = _site()
    act = site.acts[0]
    (entry,) = act.entries
    card = render_act(site, act).split('<article class="event"')[1].split("</article>")[0]
    page = render_event_page(site, act, entry, text_blocks(entry))
    masthead = _masthead(page)
    assert "<article" not in page.split("<main")[1].split('<h2 class="section">')[0]
    assert 'class="lede"' not in card
    assert 'class="status"' not in card
    assert 'class="lede"' in masthead and 'class="status"' in masthead
    assert '<p class="subject">Rule change, June</p>' in card


def test_the_card_id_is_the_entry_key_and_its_heading_links_the_version() -> None:
    site = _site()
    act = site.acts[0]
    (entry,) = act.entries
    rendered = render_act(site, act)
    assert f'<article class="event" id="{entry.key}">' in rendered
    assert re.search(rf'<h2><a href="[^"]*{entry.key}/">Version ', rendered)


def test_every_amending_act_link_stays_on_the_site_and_eur_lex_is_marked_external(
    tmp_path: Path,
) -> None:
    """On the act, version and amending-act pages, "Made by" goes to the act's page here, and
    every EUR-Lex link a version or an amending act prints says it leaves the site."""
    site = _site()
    root = tmp_path / "site"
    write_site(root, site)
    pages = [
        page
        for page in root.rglob("index.html")
        if page.relative_to(root).parts[0] in ("acts", "amendments")
    ]
    made = 0
    for page in pages:
        rendered = page.read_text(encoding="utf-8")
        for line in re.findall(r'<p class="amending">Made by (.*?)</p>', rendered):
            first = re.match(r'<a href="([^"]+)">', line)
            assert first is not None and "amendments/" in first.group(1), page
            assert not first.group(1).startswith("http"), page
            made += 1
        body = rendered.split("<main")[1].split("</main>")[0]
        for anchor in re.findall(rf'<a [^>]*href="{re.escape(_EURLEX)}"[^>]*>', body):
            assert 'class="ext"' in anchor, page
    assert made >= 2
