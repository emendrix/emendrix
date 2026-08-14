"""The watchlist: what it accepts, what it refuses, and what it matches in the firehose."""

from __future__ import annotations

from pathlib import Path

import pytest

from emendrix.eu.feed_atom import FeedEntry, FeedIdentifier
from emendrix.watch.config import (
    EXAMPLE_PATH,
    WatchedAct,
    WatchIndex,
    Watchlist,
    load_watchlist,
)
from eu_pins import AI_ACT, AI_ACT_V2, DSA, MDR, REACH

EXAMPLE = Path(__file__).resolve().parents[2] / EXAMPLE_PATH


def watchlist(*celexes: str) -> Watchlist:
    return Watchlist(acts=tuple(WatchedAct(celex=value) for value in celexes))


def test_the_shipped_example_loads_and_holds_the_four_corpus_acts() -> None:
    """The example is a deliverable, not a comment: it is loaded, not merely read."""
    loaded = load_watchlist(EXAMPLE)
    assert [entry.celex for entry in loaded.acts] == [AI_ACT, MDR, DSA, REACH]
    assert loaded.acts[0].act.display_name == "AI Act"
    assert str(loaded.acts[0].act) == f"eu:{AI_ACT}"


def test_a_missing_file_says_what_to_do(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"copy watchlist\.example\.toml"):
        load_watchlist(tmp_path / "nope.toml")


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('[[acts]]\ncelex = "not-a-celex"\n', "not a CELEX"),
        ('[[acts]]\ncelex = "32024R1689"\n[[acts]]\ncelex = "32024R1689"\n', "same act twice"),
        ('[[acts]]\ncelexx = "32024R1689"\n', "Extra inputs"),
        ("[[acts]\n", "not valid TOML"),
    ],
)
def test_a_hand_written_mistake_is_refused_at_load(
    tmp_path: Path, body: str, expected: str
) -> None:
    """The one input a person writes by hand is the one place worth being strict."""
    path = tmp_path / "watchlist.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises((ValueError, Exception), match=expected):
        load_watchlist(path)


def test_an_act_may_carry_a_domain_and_aliases_for_the_site(tmp_path: Path) -> None:
    """`domain` groups the acts index; `aliases` feed the search index. Neither is identity."""
    path = tmp_path / "watchlist.toml"
    path.write_text(
        '[[acts]]\ncelex = "32016R0679"\nname = "GDPR"\ndomain = "Data & privacy"\n'
        'aliases = ["General Data Protection Regulation"]\n',
        encoding="utf-8",
    )
    watched = load_watchlist(path).acts[0]
    assert watched.domain == "Data & privacy"
    assert watched.aliases == ("General Data Protection Regulation",)


def test_domain_and_aliases_default_to_absent(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.toml"
    path.write_text('[[acts]]\ncelex = "32016R0679"\n', encoding="utf-8")
    watched = load_watchlist(path).acts[0]
    assert watched.domain is None
    assert watched.aliases == ()


def test_the_consolidated_form_of_a_watched_act_matches() -> None:
    """An update usually surfaces as the consolidated id, which drops the sector digit."""
    index = WatchIndex(watchlist(AI_ACT))
    found = index.match(FeedIdentifier(scheme="celex", value=AI_ACT_V2))
    assert found is not None
    assert (found.watched.celex, found.version) == (AI_ACT, AI_ACT_V2)

    path_form = index.match(FeedIdentifier(scheme="consolidation", value="2024R1689/20260727"))
    assert path_form is not None
    assert path_form.version == AI_ACT_V2


def test_the_manifestation_suffix_names_the_same_version() -> None:
    """`2024R1689/20260727_0010010` rides beside the bare form in the real feed."""
    index = WatchIndex(watchlist(AI_ACT))
    found = index.match(FeedIdentifier(scheme="consolidation", value="2024R1689/20260727_0010010"))
    assert found is not None
    assert found.version == AI_ACT_V2


def test_the_plain_celex_form_matches_without_naming_a_version() -> None:
    index = WatchIndex(watchlist(AI_ACT))
    found = index.match(FeedIdentifier(scheme="celex", value=AI_ACT))
    assert found is not None
    assert found.version is None


@pytest.mark.parametrize(
    "identifier",
    [
        FeedIdentifier(scheme="celex", value="32026R1744"),
        FeedIdentifier(scheme="eli", value="reg:2024:1689:2026-07-27"),
        FeedIdentifier(scheme="ep", value="P9_OJQ(2024)03-11"),
        FeedIdentifier(scheme="celex", value="62024CO0821_INF"),
    ],
)
def test_everything_else_in_the_firehose_is_ignored(identifier: FeedIdentifier) -> None:
    """Including `eli:`, which names the watched act through a vocabulary this cannot read."""
    assert WatchIndex(watchlist(AI_ACT)).match(identifier) is None


def test_an_entry_prefers_the_identifier_that_names_a_version() -> None:
    """One entry carries the same work three ways; only one of them says which version."""
    entry = FeedEntry(
        entry_id="cellar:x@t",
        cellar_id="cellar:x",
        identifiers=(
            FeedIdentifier(scheme="celex", value=AI_ACT),
            FeedIdentifier(scheme="consolidation", value="2024R1689/20260727"),
        ),
    )
    found = WatchIndex(watchlist(AI_ACT)).match_entry(entry)
    assert found is not None
    assert found.version == AI_ACT_V2


def test_an_entry_naming_nothing_watched_matches_nothing() -> None:
    entry = FeedEntry(
        entry_id="cellar:y@t",
        cellar_id="cellar:y",
        identifiers=(FeedIdentifier(scheme="celex", value="32026R1913"),),
    )
    assert WatchIndex(watchlist(AI_ACT, MDR)).match_entry(entry) is None


# ------------------------------------------------------------------ the [output] table


def test_the_output_repository_is_read_off_the_watchlist(tmp_path: Path) -> None:
    """One hand-written file, so the second thing a person configures lives beside the first."""
    path = tmp_path / "watchlist.toml"
    path.write_text(
        '[[acts]]\ncelex = "32024R1689"\n\n[output]\nrepo_path = "~/changelog"\n',
        encoding="utf-8",
    )
    assert load_watchlist(path).output.repo_path == Path("~/changelog")


def test_no_output_table_means_no_output_repository() -> None:
    """There is no default path: a git repository the tool commits into is not a cache dir."""
    assert watchlist(AI_ACT).output.repo_path is None
    assert load_watchlist(EXAMPLE).output.repo_path is None, "the example ships it commented out"


def test_a_misspelled_output_key_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.toml"
    path.write_text('[output]\nrepo-path = "~/changelog"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="repo-path"):
        load_watchlist(path)
