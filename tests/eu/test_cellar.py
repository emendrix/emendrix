"""The CELLAR surface, against pinned fixtures: versions, packages, and the fallback chain.

Several assertions here re-derive, through this code, numbers also measured on 2026-08-05 by a
completely different route (a standalone script over regexes). Where they agree, two independent
implementations agree; if one of them moves, that is a finding to explain, not a test to update.
"""

from __future__ import annotations

from xml.etree import ElementTree

import httpx
import pytest

from emendrix.core import ConsolidationPending, EnglishUnavailable, VersionId
from emendrix.eu.cache import CachedResponse, FixtureResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.http import CellarHttp
from emendrix.eu.identifiers import Celex
from emendrix.eu.packages import FormexPackage
from eu_pins import AI_ACT, AI_ACT_V1, AI_ACT_V2, MDR, OBSERVED_ON, REACH


def version(raw: str) -> VersionId:
    return VersionId(raw)


# ------------------------------------------------------------------------- notices


def test_resolve_reads_the_act_off_its_own_notice(client: CellarClient) -> None:
    work = client.resolve(Celex.parse(AI_ACT))
    assert work.act.key == AI_ACT
    assert work.act.corpus == "eu"
    assert work.title is not None
    assert work.title.startswith("Regulation (EU) 2024/1689 of the European Parliament")
    assert work.document_date is not None
    assert work.document_date.isoformat() == "2024-06-13"
    assert work.identifier("oj") == "L_202401689"
    assert work.identifier("eli") == "reg:2024:1689:oj"


def test_the_branch_notice_is_fetched_and_cached_as_bytes(
    client: CellarClient,
) -> None:
    """This layer only fetches it; reading the annotations is `eu/modmeta.py`'s job."""
    body = client.branch_notice(Celex.parse(AI_ACT))
    assert body.startswith(b"<?xml")
    work = ElementTree.fromstring(body).find("WORK")
    assert work is not None
    links = work.findall("RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL")
    # One amending act, 88 modification annotations, re-counted here from the notice.
    assert len(links) == 1
    assert len(links[0].findall("ANNOTATION")) == 88
    assert any(
        (uri.findtext("VALUE") or "").endswith("/celex/32026R1744")
        for uri in links[0].findall("SAMEAS/URI")
    )


@pytest.mark.parametrize(
    ("celex", "consolidated", "without_english_formex"),
    [
        # Measured 2026-08-05 by `scripts/validation/trace.py`; re-derived here 2026-08-06.
        (REACH, 68, 5),
        (MDR, 7, 0),
        (AI_ACT, 2, 1),
    ],
)
def test_version_inventories_match_the_validated_counts(
    client: CellarClient, celex: str, consolidated: int, without_english_formex: int
) -> None:
    notice = client.tree_notice(Celex.parse(celex))
    versions = notice.consolidated
    assert len(versions) == consolidated
    missing = [record for record in versions if "fmx4" not in record.formats("ENG")]
    assert len(missing) == without_english_formex


def test_the_five_reach_versions_with_no_structured_text_are_the_named_ones(
    client: CellarClient,
) -> None:
    """A consolidated version existing does not imply a parseable text exists."""
    notice = client.tree_notice(Celex.parse(REACH))
    missing = [
        str(record.version) for record in notice.consolidated if "fmx4" not in record.formats("ENG")
    ]
    assert missing == [
        "02006R1907-20100402",
        "02006R1907-20101201",
        "02006R1907-20110221",
        "02006R1907-20110306",
        "02006R1907-20110505",
    ]


def test_versions_are_core_descriptors_oldest_first_with_the_oj_act_first(
    client: CellarClient,
) -> None:
    versions = client.versions(Celex.parse(AI_ACT))
    assert [str(descriptor.version) for descriptor in versions] == [
        AI_ACT,
        AI_ACT_V1,
        AI_ACT_V2,
    ]
    assert [descriptor.version_date for descriptor in versions] == sorted(
        descriptor.version_date for descriptor in versions if descriptor.version_date
    )
    assert versions[0].has_language("ENG")
    # The eleven-languages-no-English version, as the notice reports it.
    assert not versions[1].has_language("ENG")


def test_other_acts_consolidations_do_not_leak_in(client: CellarClient) -> None:
    """The AI Act amends nine regulations; their consolidations hang off its notice too."""
    for record in client.tree_notice(Celex.parse(AI_ACT)).consolidated:
        assert str(record.version).startswith("02024R1689-")


# ------------------------------------------------------------------------ packages


def test_a_consolidated_package_carries_its_members_and_its_provenance(
    client: CellarClient,
) -> None:
    package = client.fetch_formex(Celex.parse(AI_ACT), version(AI_ACT_V2))
    assert isinstance(package, FormexPackage)
    assert package.served_version == version(AI_ACT_V2)
    assert package.fell_back is False
    assert package.language == "ENG"
    assert package.source_url.endswith("/consolidation/2024R1689%2F20260727.ENG.fmx4")
    assert [member.name for member in package.members] == [
        "CL2024R1689EN0010010.0001.doc.xml",
        "CL2024R1689EN0010010.0001.xml",
    ]
    info = package.consolidation
    assert info is not None
    # The consolidation lag, measured: in force 2026-07-27, text produced 2026-07-15/24.
    assert info.start_of_validity is not None
    assert info.start_of_validity.isoformat() == "2026-07-27"
    assert info.produced_on is not None
    assert info.produced_on.isoformat() == "2026-07-15"
    assert info.end_of_validity is None, "END.DATE=99999999 means still current"


def test_a_package_is_a_bag_of_documents_not_one_file(client: CellarClient) -> None:
    """The OJ publication ships one `ANNEX` document per annex, 16 members in all."""
    package = client.fetch_formex(Celex.parse(AI_ACT), version(AI_ACT))
    assert isinstance(package, FormexPackage)
    assert len(package.members) == 16
    assert all(member.is_xml for member in package.members)


def test_an_old_consolidation_answers_on_the_other_addressing_scheme(
    client: CellarClient,
) -> None:
    """Pre-2018 consolidations answer on `celex/`, not `consolidation/`."""
    package = client.fetch_formex(Celex.parse(REACH), version("02006R1907-20081012"))
    assert isinstance(package, FormexPackage)
    assert "/resource/celex/02006R1907-20081012.ENG.fmx4" in package.source_url


# ------------------------------------------------------------------ fallback chain


def test_the_chain_falls_back_to_the_act_as_published(client: CellarClient) -> None:
    """`02024R1689-20240712` has no English text; the OJ act does, and it is marked."""
    package = client.fetch_formex(Celex.parse(AI_ACT), version(AI_ACT_V1))
    assert isinstance(package, FormexPackage)
    assert package.requested_version == version(AI_ACT_V1)
    assert package.served_version == version(AI_ACT)
    assert package.fell_back is True
    assert package.source_url.endswith("/oj/L_202401689.ENG.fmx4")


def test_with_the_fallback_disabled_the_answer_is_a_state(client: CellarClient) -> None:
    unavailable = client.fetch_formex(
        Celex.parse(AI_ACT), version(AI_ACT_V1), allow_original_fallback=False
    )
    assert isinstance(unavailable, EnglishUnavailable)
    assert unavailable.state == "english_unavailable"
    assert unavailable.requested_language == "ENG"
    assert unavailable.available_languages == ("FRA",)
    assert unavailable.observed_on == OBSERVED_ON
    assert unavailable.version == version(AI_ACT_V1)


def test_a_version_that_is_not_consolidated_yet_is_a_state(client: CellarClient) -> None:
    """Consolidation lags publication by 10 days to 3 weeks."""
    pending = client.fetch_formex(Celex.parse(AI_ACT), version("02024R1689-20260901"))
    assert isinstance(pending, ConsolidationPending)
    assert pending.observed_on == OBSERVED_ON
    assert "tree notice lists" in pending.detail


def test_nothing_in_the_chain_raises_and_nothing_touches_the_network(
    client: CellarClient, http: CellarHttp
) -> None:
    for target in (AI_ACT, AI_ACT_V1, AI_ACT_V2, "02024R1689-20991231"):
        assert client.fetch_formex(Celex.parse(AI_ACT), version(target)) is not None
    assert http.network_calls == 0


def test_the_fallback_is_only_for_the_first_consolidation(client: CellarClient) -> None:
    """Answering a 2020 question with the 2017 original would be a different answer."""
    notice = client.tree_notice(Celex.parse(MDR))
    later = notice.consolidated[1]
    assert client.fetch_formex(Celex.parse(MDR), later.version) is not None


class _PassThroughCache:
    """Reads the pinned notices, but sends every *document* request to the (mocked) transport.

    It misses on zip requests whatever happens to be pinned, so the test states what it means,
    a refusal on a document fetch, instead of depending on which versions the eval corpus pins.
    """

    def __init__(self, inner: FixtureResponseCache) -> None:
        self.inner = inner

    @property
    def offline(self) -> bool:
        return False

    def get(self, key: str) -> CachedResponse | None:
        entry = self.inner.entries.get(key)
        if entry is None or "zip" in (entry.accept or ""):
            return None
        return self.inner.get(key)

    def store(self, response: CachedResponse) -> None:
        return None


def test_a_server_refusal_is_never_read_as_a_fact_about_the_corpus(
    fixture_cache: FixtureResponseCache,
) -> None:
    """A 429 means the server is refusing the request; only 404/406 mean the text is not there.

    Persisting `EnglishUnavailable` because a public endpoint throttled a long eval run would be
    a false statement about an act, which is exactly the failure this project cannot afford.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert "fmx4" in str(request.url)
        return httpx.Response(429, content=b"slow down")

    http = CellarHttp(
        cache=_PassThroughCache(fixture_cache),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
        polite_delay_s=0.0,
    )
    client = CellarClient(http, observed_on=OBSERVED_ON)
    with pytest.raises(LookupError, match="unexpected HTTP 429"):
        client.fetch_formex(Celex.parse(MDR), version("02017R0745-20230311"))
