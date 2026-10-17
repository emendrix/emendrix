"""A watchlist holding CAS and EC numbers: the Watching tab, every other account page, the
personal feed and the data export all draw it, and the Watching tab groups it apart.

The record is the one the load tests give a table-entry diff (`tabled`): `house-rules` v3 moves
entry 7 (CAS 50-00-0, EC 200-001-8), entry 9 only in typography (CAS 64-17-5) and adds the entry
for Dust of the shelves (CAS 7732-18-5).
"""

from __future__ import annotations

import json
import re
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from emendrix_service.db import Db
from emendrix_service.db.enums import ItemKind
from emendrix_service.db.tables import Change, Event, TableHit
from emendrix_service.db.watchlists import add_item, create_watchlist
from tests.conftest import NOW, SITE_URL
from tests.test_svc_watch_account import assert_clean, body
from tests.test_svc_watch_fixtures import HOUSE, csrf, sign_in
from tests.test_svc_watch_fixtures import tabled as tabled

pytestmark = pytest.mark.anyio

NUMBERS = ("ec:200-001-8", "cas:7732-18-5", "cas:64-17-5", "cas:50-00-0", "cas:999-99-5")
"""Watched numbers: three a stored change names, one only in typography, one no row carries."""


async def watching(db: Db, user: UUID, *, act: bool = True) -> UUID:
    async with db.transaction() as tx:
        wl = await create_watchlist(tx, user, "My watchlist", NOW)
        if act:
            assert await add_item(tx, user, wl, ItemKind.ACT, "toy", HOUSE, None, NOW)
        for identifier in NUMBERS:
            added = await add_item(
                tx, user, wl, ItemKind.SUBSTANCE, None, None, None, NOW, identifier=identifier
            )
            assert added is True
    return wl


async def the_change(db: Db) -> tuple[str, str]:
    """The event page and anchor of the change the table rows moved in, and its in-force date."""
    async with db.transaction() as tx:
        url, anchor, in_force, detected = (
            await tx.execute(
                select(Event.url, Change.anchor, Change.in_force, Event.detected_on)
                .join(Change, Change.event_key == Event.event_key)
                .where(Event.event_key == "toy/house-rules@v3", Change.location == "AN I")
            )
        ).one()
    dated = f"in force {in_force}" if in_force else f"recorded {detected}"
    return f"{url}#{anchor}", dated


async def test_svc_watch_substances_render_on_every_account_page(
    client: AsyncClient, tabled: Db
) -> None:
    user = await sign_in(tabled, client, "owner@example.org")
    wl = await watching(tabled, user)
    link, dated = await the_change(tabled)
    page = await client.get("/account/")
    assert page.status_code == 200
    text = body(page.text)
    assert "6 items across 1 act and 5 CAS or EC numbers" in text
    assert '<span class="act-name" id="substances">Substances</span>' in text
    labels = re.findall(r'class="tag"[^>]*>((?:CAS|EC) [\d-]+)<', text)
    assert labels == ["CAS 50-00-0", "CAS 64-17-5", "CAS 999-99-5", "CAS 7732-18-5", "EC 200-001-8"]
    assert f'<a class="tag" href="{SITE_URL}/substances/cas-50-00-0/">CAS 50-00-0</a>' in text
    assert (
        f'<a href="{link}">Entry 7 in House Rules of Flat 3B Annex I was amended in the '
        f"version {dated}</a>" in text
    )
    assert (
        "The entry for Dust of the shelves in House Rules of Flat 3B Annex I was added in the "
        f"version {dated}" in text
    )
    assert '<span class="tag">CAS 64-17-5</span>' in text, "a typography-only change names none"
    assert text.count("No recorded change to an entry printing this number yet.") == 2
    assert "regulated" not in text and "restricted" not in text
    assert 'aria-label="Stop watching CAS 999-99-5"' in text
    assert f'href="/account/watchlists/{wl}/add#numbers"' in text
    assert_clean(page.text)
    for path in ("/account/delivery", "/account/settings", f"/account/watchlists/{wl}/add"):
        other = await client.get(path)
        assert other.status_code == 200, path
        assert_clean(other.text)
    exported = await client.get("/account/export")
    assert exported.status_code == 200
    items = json.loads(exported.content)["items"]
    assert sorted(i["identifier"] for i in items if i["identifier"]) == sorted(NUMBERS)
    assert {(i["corpus"], i["act_key"]) for i in items if i["identifier"]} == {(None, None)}
    rows = re.findall(rf'action="/account/watchlists/{wl}/items/([0-9a-f-]+)/delete"', text)
    gone = await client.post(
        f"/account/watchlists/{wl}/items/{rows[-1]}/delete", data={"csrf": await csrf(client)}
    )
    assert gone.headers["location"] == f"/account/?list={wl}&notice=removed"
    after = body((await client.get("/account/")).text)
    assert "EC 200-001-8" not in after and "5 items across 1 act and 4 CAS or EC numbers" in after


async def test_svc_watch_substances_alone_make_no_act_group(
    client: AsyncClient, tabled: Db
) -> None:
    user = await sign_in(tabled, client, "owner@example.org")
    await watching(tabled, user, act=False)
    text = body((await client.get("/account/")).text)
    assert "5 items: 5 CAS or EC numbers" in text
    assert '<span class="tag">Act</span>' not in text
    assert "Nothing is watched here yet." not in text
    assert "Emails repeat what the record says." in text


async def test_svc_watch_substances_an_index_no_points_at_the_numbers_its_row_prints(
    client: AsyncClient, tabled: Db
) -> None:
    async with tabled.transaction() as tx:
        await tx.execute(
            update(TableHit).where(TableHit.row_key == "7").values(row_key="605-001-00-5")
        )
    page = await client.get("/account/watch?substance=index-605-001-00-5")
    assert page.status_code == 200
    assert "An Index No cannot be watched" in page.text
    assert "watch a CAS or EC number that its entry prints instead." in page.text
    for scheme, value in (("cas", "50-00-0"), ("ec", "200-001-8")):
        label = f"{scheme.upper()} {value}"
        assert f'<a href="{SITE_URL}/substances/{scheme}-{value}/">{label}</a>' in page.text
        assert f'href="/account/watch?substance={scheme}-{value}">watch {label}' in page.text
    assert "regulated" not in page.text
    assert_clean(page.text)
