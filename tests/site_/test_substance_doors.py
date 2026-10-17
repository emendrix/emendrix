"""The doors to the substance pages: each where it belongs, each in its one wording.

An act page's door is decided by whether the act has a register, read off the inputs, never by
a list of acts typed into the site; the toy act has one, and the same act without it has none.
"""

from __future__ import annotations

import re

from toy_substances import SITE_URL, substance_site

from emendrix.site_.llms import llms_txt
from emendrix.site_.markup import escape, inline
from emendrix.site_.pages.act import render_act
from emendrix.site_.pages.api_page import render_api_page
from emendrix.site_.pages.event import render_event_page
from emendrix.site_.pages.home import render_home
from emendrix.site_.pages.not_found import render_not_found
from emendrix.site_.pages.texts import text_blocks
from emendrix.site_.substance_doors import API_DOOR, EVENT_DOOR, LLMS_DOOR


def test_home_leads_to_the_lookup_after_the_measured_claim_and_before_the_take_away() -> None:
    page = render_home(substance_site())
    door = page.index('<p class="lookup"><a href="substances/">Look up a CAS or EC number</a>')
    assert page.index('<aside class="stat">') < door < page.index('<section class="doors"')


def test_an_act_with_a_register_opens_its_list_and_asks_for_the_substance_index() -> None:
    site = substance_site()
    act = site.acts[0]
    page = render_act(site, act)
    assert '<a href="../../substances/acts/house-rules/">Find an entry of this act' in page
    assert " data-substances></div>" in page
    bare = site.model_copy(update={"substances": type(site.substances)()})
    plain = render_act(bare, bare.acts[0])
    assert "Find an entry of this act" not in plain
    assert " data-substances" not in plain


def test_an_event_page_says_its_numbers_link_and_links_them() -> None:
    site = substance_site()
    act = site.acts[0]
    entry = act.entries[0]
    page = render_event_page(site, act, entry, text_blocks(entry, act.entries))
    assert page.index(escape(EVENT_DOOR)) < page.index('<section class="entries"')
    assert '<a href="../../../substances/cas-toy-1/">CAS toy-1</a>' in page
    assert '<a href="../../../substances/ec-toy-e1/">EC toy-e1</a>' in page
    assert "<span>Index No toy-i1</span>" in page, "an Index No has no page and no link"


def test_the_not_found_page_says_a_missing_page_is_not_a_statement_about_the_law() -> None:
    page = render_not_found(substance_site())
    assert "so a missing page is not a statement about the law" in page
    assert re.search(r'href="/site/substances/#lookup">the substances page</a>', page)


def test_the_api_page_and_llms_txt_name_the_two_substance_files() -> None:
    site = substance_site()
    page = render_api_page(site)
    assert inline(API_DOOR) in page
    for path in ("/api/v1/substances.json", "/api/v1/substances/&lt;scheme&gt;-&lt;value&gt;.json"):
        assert f"<code>{path}" in page or f"{path}</a></code>" in page, path
    assert "substance.schema.json" in page
    text = llms_txt(site)
    assert f"- [Substances]({SITE_URL}/api/v1/substances.json): {LLMS_DOOR}" in text
