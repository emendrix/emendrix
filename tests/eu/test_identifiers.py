"""The identifier grammar: every form round-trips, and each knows where it answers."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from emendrix.core import ActId, VersionId
from emendrix.eu.identifiers import (
    Celex,
    ConsolidatedId,
    ResourceRef,
    act_id,
    celex_of,
    parse_version_id,
)


@pytest.mark.parametrize(
    ("raw", "parts"),
    [
        ("32024R1689", ("3", "2024", "R", "1689")),
        ("32017R0745", ("3", "2017", "R", "0745")),
        ("32006R1907", ("3", "2006", "R", "1907")),
        ("32014L0090", ("3", "2014", "L", "0090")),
        ("32026R1744", ("3", "2026", "R", "1744")),
    ],
)
def test_celex_round_trips(raw: str, parts: tuple[str, str, str, str]) -> None:
    celex = Celex.parse(raw)
    assert (celex.sector, celex.year, celex.descriptor, celex.number) == parts
    assert celex.value == raw
    assert str(celex) == raw


def test_celex_keeps_the_leading_zeros_of_the_number() -> None:
    """`0745` is the identifier; `745` is a different string and resolves to nothing."""
    assert Celex.parse("32017R0745").number == "0745"
    assert Celex.parse("32017R0745").act_code == "2017R0745"


@pytest.mark.parametrize("raw", ["", "2024R1689", "32024R168", "32024X1689x", "not a celex"])
def test_a_malformed_celex_is_a_programming_error(raw: str) -> None:
    with pytest.raises(ValueError, match="CELEX"):
        Celex.parse(raw)


def test_consolidated_id_round_trips() -> None:
    consolidated = ConsolidatedId.parse("02024R1689-20260727")
    assert consolidated.act_code == "2024R1689"
    assert consolidated.version_date == date(2026, 7, 27)
    assert consolidated.value == "02024R1689-20260727"
    assert consolidated.consolidation_identifier == "2024R1689/20260727"
    assert ConsolidatedId.parse(consolidated.value) == consolidated


def test_consolidated_id_is_minted_from_the_act_it_consolidates() -> None:
    celex = Celex.parse("32006R1907")
    consolidated = ConsolidatedId.for_act(celex, date(2008, 10, 12))
    assert consolidated.value == "02006R1907-20081012"
    assert consolidated.compact_date == "20081012"


def test_version_ids_parse_back_into_what_minted_them() -> None:
    """A `VersionId` is opaque to the core and readable only here."""
    assert parse_version_id(VersionId("32024R1689")) == Celex.parse("32024R1689")
    assert parse_version_id(VersionId("02024R1689-20260727")) == ConsolidatedId.parse(
        "02024R1689-20260727"
    )


def test_act_ids_carry_the_celex_and_nothing_else_identifying() -> None:
    celex = Celex.parse("32024R1689")
    act = act_id(celex, display_name="AI Act")
    assert act.corpus == "eu"
    assert act.key == "32024R1689"
    assert celex_of(act) == celex
    # The display name is a label, never identity (core contract).
    assert act == act_id(celex)


def test_a_foreign_act_is_not_readable_here() -> None:
    with pytest.raises(ValueError, match="not an EU act"):
        celex_of(ActId(corpus="toy", key="house-rules"))


@pytest.mark.parametrize(
    ("ref", "path"),
    [
        (
            ResourceRef(system="consolidation", identifier="2024R1689/20260727.ENG.fmx4"),
            "/resource/consolidation/2024R1689%2F20260727.ENG.fmx4",
        ),
        (
            ResourceRef(system="celex", identifier="02006R1907-20081012.ENG.fmx4"),
            "/resource/celex/02006R1907-20081012.ENG.fmx4",
        ),
        (
            ResourceRef(system="oj", identifier="L_202401689.ENG.fmx4"),
            "/resource/oj/L_202401689.ENG.fmx4",
        ),
    ],
)
def test_resource_paths_encode_the_slash(ref: ResourceRef, path: str) -> None:
    """`/` inside a consolidation identifier must reach the server as `%2F` (2026-08-06)."""
    assert ref.path == path


@pytest.mark.parametrize(
    "system", ["../../evil", "celex/../oj", "celex?x=1", "celex#frag", "celex x", "/celex", ""]
)
def test_a_system_that_is_not_a_bare_word_is_refused_rather_than_put_in_a_path(
    system: str,
) -> None:
    """`system` reaches the path unencoded and is read off the notice, so it is constrained.

    A `<TYPE>` of `../..` would have httpx resolve the dot segments and fetch a different path
    on the same host; a `?` or `#` would split the URL. CELLAR's system vocabulary is a small
    closed set of bare words, so anything else is a finding rather than an address.
    """
    with pytest.raises(ValidationError):
        ResourceRef(system=system, identifier="32024R1689")


@pytest.mark.parametrize(
    "system", ["celex", "oj", "consolidation", "cellar", "eli", "uriserv", "language", "immc"]
)
def test_every_system_the_pinned_notices_announce_is_accepted(system: str) -> None:
    """The constraint must not cost a real address: these are what the fixtures actually carry."""
    assert ResourceRef(system=system, identifier="x").path.startswith(f"/resource/{system}/")


def test_resource_candidates_are_ordered_best_guess_first() -> None:
    """Both addressing schemes are offered because neither covers everything."""
    consolidated = ConsolidatedId.parse("02006R1907-20081012")
    assert [ref.system for ref in consolidated.resource_refs(".ENG.fmx4")] == [
        "consolidation",
        "celex",
    ]
    celex = Celex.parse("32024R1689")
    assert [ref.system for ref in celex.resource_refs(".ENG.fmx4")] == ["celex", "oj"]
    assert celex.resource_refs(".ENG.fmx4")[1].identifier == "L_202401689.ENG.fmx4"


def test_the_oj_identifier_is_constructed_the_way_the_notice_writes_it() -> None:
    """Checked against the tree notice's own `oj` SAMEAS on 2026-08-06."""
    assert Celex.parse("32024R1689").oj_identifier == "L_202401689"
    assert Celex.parse("32026R1744").oj_identifier == "L_202601744"


@pytest.mark.parametrize(
    ("raw", "number"),
    [
        ("32026R1744", "Regulation (EU) 2026/1744"),
        ("32015R2283", "Regulation (EU) 2015/2283"),
        ("32013R0575", "Regulation (EU) No 575/2013"),
        ("32010R0995", "Regulation (EU) No 995/2010"),
        ("32006R1907", "Regulation (EC) No 1907/2006"),
        ("31992R2913", "Regulation (EEC) No 2913/92"),
        ("31993R2454", "Regulation (EC) No 2454/1993"),
        ("32015L2366", "Directive (EU) 2015/2366"),
        ("32011L0061", "Directive 2011/61/EU"),
        ("32009L0065", "Directive 2009/65/EC"),
        ("32014D0287", ""),
        ("32019H1024", ""),
    ],
)
def test_the_official_number_follows_the_convention_of_the_acts_own_year(
    raw: str, number: str
) -> None:
    """The numbering convention changed twice and the CELEX carries the year, so the reading is
    a lookup rather than a guess. A descriptor naming neither a regulation nor a directive
    answers with nothing, which is what makes the caller fall back to the key.

    `31993R2454` is here as the boundary case rather than as a claim: that act is titled
    `(EEC) No 2454/93`, because the Maastricht Treaty renamed the Community on 1 November 1993
    and it was adopted in July. A CELEX carries no month, so the year is the finest cut
    available and 1993 is taken whole as the first `(EC)` year. Nothing in the corpus is
    affected: the oldest act the committed reports name as amending a watched one is
    `32008R0987` (checked 2026-09-03), and the two bands below 1999 are exercised here and by
    nothing else.
    """
    assert Celex.parse(raw).official_number == number


def _titled_amending_acts() -> dict[str, str]:
    """Every amending act the committed reports record an official title for, by CELEX.

    Read off `reports/eval/*.json` rather than a fixture, because those are the documents the
    site actually renders from: an `ActId` under a change's `amending_acts` or a signal claim's
    `amending_act`, with a `display_name` the corpus published.
    """
    found: dict[str, str] = {}

    def walk(node: object, *, amending: bool) -> None:
        if isinstance(node, dict):
            title = node.get("display_name")
            if amending and isinstance(title, str) and isinstance(node.get("key"), str):
                found.setdefault(str(node["key"]), title)
            for name, value in node.items():
                walk(value, amending=name in ("amending_acts", "amending_act"))
        elif isinstance(node, list):
            for value in node:
                walk(value, amending=amending)

    for report in sorted((Path(__file__).resolve().parents[2] / "reports" / "eval").glob("*.json")):
        walk(json.loads(report.read_text(encoding="utf-8")), amending=False)
    return found


def test_every_recorded_official_title_contains_the_number_rendered_from_its_celex() -> None:
    """The honesty check on the rendering, over the titles the corpus itself published.

    A substring rather than an opening: an act adopted by the Commission is titled `Commission
    Regulation (EC) No 987/2008` or `Commission Delegated Regulation (EU) 2023/502`, and no
    identifier says which. Non-breaking spaces are folded to ordinary ones for the comparison
    only: `Regulation (EC) No\u00a01907/2006` is how the Publications Office wrote that title,
    the stored text keeps it, and a check on the number should not fail over the width of a
    space. Verified over the seven titled amending acts the committed reports carry on
    2026-09-03; a wrong year boundary would fail here rather than on a page.
    """
    titled = _titled_amending_acts()
    assert len(titled) >= 7
    for key, title in sorted(titled.items()):
        number = Celex.parse(key).official_number
        assert number, key
        assert number in title.replace("\u00a0", " "), f"{key}: {number!r} not in {title!r}"
