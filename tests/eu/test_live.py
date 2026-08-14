"""Live re-verification of the facts this adapter is built on. `uv run pytest -m live`.

Excluded by default and in CI, and never a dependency of anything: everything else in the
suite runs against pinned fixtures. This exists because the worst failure mode for a tool about
legal change is being wrong about legal change. When the Publications Office changes something,
this is what says so, and the fixtures are re-pinned with
`uv run python -m emendrix.eu.fetch_fixtures`.

Every assertion below was true on 2026-08-06.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from emendrix.core import ProvisionTree, StructuredTextUnavailable, VersionId
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import DiskResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.feed import ACCEPT_ATOM, fetch_notifications
from emendrix.eu.http import ACCEPT_ZIP, BASE_URL, CellarHttp
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.packages import FormexPackage
from eu_pins import AI_ACT, AI_ACT_V1, AI_ACT_V2, FEED_ENTRIES, FEED_WINDOW, OBSERVED_ON, REACH

pytestmark = pytest.mark.live


@pytest.fixture
def live_client(tmp_path: Path) -> CellarClient:
    """A client with an empty cache, so every call in this module really goes out."""
    return CellarClient(CellarHttp(cache=DiskResponseCache(tmp_path)), observed_on=OBSERVED_ON)


def test_https_resolves_and_the_tree_notice_still_says_what_it_said(
    live_client: CellarClient,
) -> None:
    assert BASE_URL.startswith("https://")
    notice = live_client.tree_notice(Celex.parse(AI_ACT))
    assert notice.work.identifier("oj") == "L_202401689"
    versions = [str(record.version) for record in notice.versions]
    assert versions[:3] == [AI_ACT, AI_ACT_V1, AI_ACT_V2]
    v1, v2 = notice.versions[1], notice.versions[2]
    # The first consolidation has no English text; the second does.
    assert "ENG" not in v1.languages
    assert "fmx4" in v2.formats("ENG")


def test_a_missing_manifestation_answers_404_not_406(live_client: CellarClient) -> None:
    """The detection signal for the fallback chain, checked against the live endpoint."""
    response = live_client.http.get(
        "/resource/consolidation/2024R1689%2F20240712.ENG.fmx4", accept=ACCEPT_ZIP
    )
    assert response.status_code == 404
    assert "not found" in response.text().lower()


def test_a_post_2023_act_is_unfetchable_by_celex(live_client: CellarClient) -> None:
    """Acts published from 2023-10 answer only on the `oj` identifier."""
    assert (
        live_client.http.get("/resource/celex/32024R1689.ENG.fmx4", accept=ACCEPT_ZIP).status_code
        == 404
    )
    assert live_client.http.get("/resource/oj/L_202401689.ENG.fmx4", accept=ACCEPT_ZIP).ok


def test_the_flagship_package_is_still_there_with_its_provenance(
    live_client: CellarClient,
) -> None:
    package = live_client.fetch_formex(Celex.parse(AI_ACT), VersionId(AI_ACT_V2))
    assert isinstance(package, FormexPackage)
    assert package.consolidation is not None
    assert package.consolidation.start_of_validity is not None
    assert package.consolidation.start_of_validity.isoformat() == "2026-07-27"


def test_the_fallback_chain_end_to_end(live_client: CellarClient) -> None:
    package = live_client.fetch_formex(Celex.parse(AI_ACT), VersionId(AI_ACT_V1))
    assert isinstance(package, FormexPackage)
    assert package.fell_back is True
    assert package.served_version == VersionId(AI_ACT)


def test_the_notification_channel_segment_is_still_mandatory(live_client: CellarClient) -> None:
    """Both bare paths answered 404 on 2026-08-06. A 404 here is the finding, not a failure."""
    for path in ("/webapi/notification/", "/webapi/notification"):
        assert live_client.http.get(path, accept=ACCEPT_ATOM).status_code == 404


def test_a_real_day_window_still_parses_to_entries(live_client: CellarClient) -> None:
    """The `-m live` smoke of the WATCH stage: the pinned window still reads as it was pinned.

    If this drifts, the fixtures are re-pinned with
    `uv run python -m emendrix.eu.fetch_fixtures` and the numbers in `tests/eu_pins.py` move
    with them, deliberately rather than silently.
    """
    result = fetch_notifications(live_client.http, start=FEED_WINDOW[0], end=FEED_WINDOW[1])
    assert len(result.entries) == FEED_ENTRIES
    assert result.skipped == 0
    assert any("2024R1689" in item.value for entry in result.entries for item in entry.identifiers)
    # The trap: nothing usable is in the standard Atom fields.
    assert all(entry.cellar_id.startswith("cellar:") for entry in result.entries)


def test_the_reach_versions_that_parse_to_nothing_still_do(live_client: CellarClient) -> None:
    """Verified 2026-08-11: the corpus really does ship these two packages this way.

    `02006R1907-20150513` and `02006R1907-20150601` answer with a Formex package whose member
    names do not describe their contents: the `CONS.ACT` document sits on a member named
    `.tif`, and the member named `…0001.xml` holds a short `DOC` wrapper. Reading a package by
    name therefore finds no act document in either, which is why `fetch_version` answers
    `StructuredTextUnavailable` for them rather than an empty tree a diff would report as the
    repeal of all 158 units.

    The neighbour `02006R1907-20150323` carries the same scrambling and parses to the full act
    only because its `CONS.ACT` payload happens to have landed on the `.xml`-named member. It
    is asserted beside them so a corpus-side repacking shows up as this test going green in an
    unexpected place rather than as silence.
    """
    adapter = EuCorpusAdapter(live_client)
    act = act_id(Celex.parse(REACH))
    for version in ("02006R1907-20150513", "02006R1907-20150601"):
        answer = adapter.fetch_version(act, VersionId(version))
        assert isinstance(answer, StructuredTextUnavailable), version
        assert "no provisions" in answer.detail
    readable = adapter.fetch_version(act, VersionId("02006R1907-20150323"))
    assert isinstance(readable, ProvisionTree)
    assert len(readable.roots) == 158
