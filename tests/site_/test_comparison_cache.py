"""A stored comparison makes a build faster and never different.

What is held here is the rule `site_/comparisons.py` is written around: whatever table of stored
answers a comparison is handed, it returns what `worddiff.compare` returns, because an entry is
used only once it is shown to fit its texts. The ratio is derived from the opcodes rather than
stored, so it is checked here against `difflib` itself, exactly. And the command line writes the
same tree with no cache, a cold one and a warm one.
"""

from __future__ import annotations

import random
from difflib import SequenceMatcher
from pathlib import Path

import pytest
from helpers import REPORTS, SITE_URL, WATCHLIST, _tree, runner
from typer.testing import Result

from emendrix.cli import app
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_ import collect_site, read_entries, worddiff, write_site
from emendrix.site_.comparisons import (
    NO_COMPARISONS,
    Stored,
    compare_known,
    comparison_key,
    fits,
    pairs,
    resolve,
)
from emendrix.site_.worddiff import LINE_TOKEN_CEILING, Opcode, compare, tokenise
from eu_pins import OBSERVED_ON

_VOCABULARY = ("shall", "may", "Article", "5", "the", "of", "Member", "States", "(a)", "and")


def _words(rng: random.Random, length: int) -> list[str]:
    return [rng.choice(_VOCABULARY) for _ in range(length)]


def _edited(rng: random.Random, words: list[str]) -> list[str]:
    """`words` after a few insertions, deletions and repeated runs."""
    edited = list(words)
    for _ in range(rng.randint(0, 6)):
        operation = rng.choice(("insert", "delete", "repeat"))
        at = rng.randint(0, len(edited))
        if operation == "insert":
            edited[at:at] = _words(rng, rng.randint(1, 4))
        elif operation == "delete" and edited:
            del edited[at : at + rng.randint(1, 3)]
        else:
            edited[at:at] = edited[max(0, at - 3) : at]
    return edited


def _corpus() -> list[tuple[str, str]]:
    """Seeded text pairs, from empty against empty to a line-granularity table."""
    rng = random.Random(20261007)
    texts: list[tuple[str, str]] = [("", ""), ("", "shall apply"), ("shall apply", "")]
    texts.append(("the Member States shall", "the Member States shall"))
    for _ in range(520):
        words = _words(rng, rng.randint(0, 40))
        texts.append((" ".join(words), " ".join(_edited(rng, words))))
    rows = [f"row {row} " + "x" * 400 + " y" * 80 for row in range(300)]
    table = "\n".join(rows)
    texts.append((table, table.replace("row 150 ", "row 150 CHANGED ", 1)))
    return texts


CORPUS = _corpus()


def test_the_corpus_reaches_line_granularity() -> None:
    before, _ = CORPUS[-1]
    assert len(before.split()) > LINE_TOKEN_CEILING
    assert tokenise(*CORPUS[-1]).granularity == "line"


def test_the_ratio_derived_from_the_opcodes_is_difflibs_own_float() -> None:
    for before, after in CORPUS:
        tokens = tokenise(before, after)
        expected = SequenceMatcher(None, list(tokens.a), list(tokens.b), autojunk=False).ratio()
        assert worddiff.assemble(tokens, worddiff.opcodes(tokens)).ratio == expected


def test_with_no_table_a_comparison_is_the_one_compare_makes() -> None:
    for before, after in CORPUS:
        assert compare_known(before, after, NO_COMPARISONS) == compare(before, after)


def _no_matcher(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(tokens: worddiff.Tokens) -> tuple[Opcode, ...]:
        raise AssertionError("the matcher ran although every answer was stored")

    monkeypatch.setattr(worddiff, "opcodes", refuse)


def test_a_resolved_table_answers_every_pair_without_the_matcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved = resolve(CORPUS, NO_COMPARISONS)
    assert resolved.reused == 0 and resolved.rejected == 0
    assert len(resolved.computed) == len(set(resolved.table)) == len(set(CORPUS))
    expected = [compare(before, after) for before, after in CORPUS]
    _no_matcher(monkeypatch)
    assert [compare_known(b, a, resolved.table) for b, a in CORPUS] == expected
    again = resolve(CORPUS, resolved.table)
    assert again.reused == len(resolved.table) and again.computed == ()


_BEFORE = "pay within one month of receipt"
_AFTER = "pay within two weeks of receipt"


def _true() -> Stored:
    """The honest entry for `_BEFORE` against `_AFTER`, as the matcher computes it."""
    resolved = resolve([(_BEFORE, _AFTER)], NO_COMPARISONS)
    return resolved.table[comparison_key(_BEFORE, _AFTER)]


def test_the_honest_entry_fits() -> None:
    assert _true().opcodes == (
        ("equal", 0, 2, 0, 2),
        ("replace", 2, 4, 2, 4),
        ("equal", 4, 6, 4, 6),
    )
    assert fits(_true(), tokenise(_BEFORE, _AFTER))


_WRONG: dict[str, dict[str, object]] = {
    "a wrong a": {"a": 7},
    "a wrong b": {"b": 5},
    "the wrong granularity": {"granularity": "line"},
    "a gap": {"opcodes": (("equal", 0, 2, 0, 2), ("replace", 3, 4, 2, 4), ("equal", 4, 6, 4, 6))},
    "an overlap": {
        "opcodes": (("equal", 0, 2, 0, 2), ("replace", 1, 4, 2, 4), ("equal", 4, 6, 4, 6))
    },
    "an equal over differing tokens": {"opcodes": (("equal", 0, 6, 0, 6),)},
    "an equal with unequal lengths": {
        "opcodes": (("equal", 0, 2, 0, 2), ("replace", 2, 4, 2, 3), ("equal", 4, 6, 3, 6))
    },
    "a delete with a b range": {
        "opcodes": (("equal", 0, 2, 0, 2), ("delete", 2, 4, 2, 4), ("equal", 4, 6, 4, 6))
    },
    "an insert with an a range": {
        "opcodes": (("equal", 0, 2, 0, 2), ("insert", 2, 4, 2, 4), ("equal", 4, 6, 4, 6))
    },
    "a replace with an empty side": {
        "opcodes": (
            ("equal", 0, 2, 0, 2),
            ("replace", 2, 4, 2, 2),
            ("insert", 4, 4, 2, 4),
            ("equal", 4, 6, 4, 6),
        )
    },
    "a match split in two": {
        "opcodes": (
            ("equal", 0, 1, 0, 1),
            ("equal", 1, 2, 1, 2),
            ("replace", 2, 4, 2, 4),
            ("equal", 4, 6, 4, 6),
        )
    },
    "a replace split into a delete and an insert": {
        "opcodes": (
            ("equal", 0, 2, 0, 2),
            ("delete", 2, 4, 2, 2),
            ("insert", 4, 4, 2, 4),
            ("equal", 4, 6, 4, 6),
        )
    },
    "no opcodes for non-empty texts": {"opcodes": ()},
    "a range past the end": {"opcodes": (("equal", 0, 2, 0, 2), ("replace", 2, 7, 2, 6))},
}


@pytest.mark.parametrize("wrong", sorted(_WRONG))
def test_an_entry_that_does_not_fit_is_ignored_and_the_answer_is_unchanged(wrong: str) -> None:
    stored = Stored.model_validate({**_true().model_dump(by_alias=True), **_WRONG[wrong]})
    assert not fits(stored, tokenise(_BEFORE, _AFTER))
    known = {comparison_key(_BEFORE, _AFTER): stored}
    assert compare_known(_BEFORE, _AFTER, known) == compare(_BEFORE, _AFTER)
    resolved = resolve([(_BEFORE, _AFTER)], known)
    assert (resolved.rejected, resolved.reused) == (1, 0)
    assert resolved.table[comparison_key(_BEFORE, _AFTER)] == _true()


def test_the_key_is_the_algorithm_and_both_texts_unambiguously(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = comparison_key("ab", "c")
    assert key == comparison_key("ab", "c")
    assert key != comparison_key("a", "bc")
    assert key != comparison_key("c", "ab")
    assert len(key) == 64 and set(key) <= set("0123456789abcdef")
    monkeypatch.setattr("emendrix.site_.comparisons.ALGORITHM", "another matcher")
    assert comparison_key("ab", "c") != key


def test_pairs_are_exactly_what_the_rendering_compares(
    tmp_path: Path, changelog_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A whole site built from a resolved table runs no matcher, so nothing was missed."""
    site = collect_site(
        generated_on=OBSERVED_ON,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=read_entries(changelog_repo),
        configured=True,
        site_url=SITE_URL,
    )
    assert list(pairs(site.acts)), "the fixture repository compares at least one pair"
    table = resolve(pairs(site.acts), NO_COMPARISONS).table
    write_site(tmp_path / "plain", site)
    expected = _tree(tmp_path / "plain")
    _no_matcher(monkeypatch)
    write_site(tmp_path / "cached", site, comparisons=table)
    assert _tree(tmp_path / "cached") == expected


def _build(out: Path, repo: Path, *extra: str) -> Result:
    """`emendrix site build` as `helpers.build` runs it, with the output kept for reading."""
    arguments = [
        "site",
        "build",
        "--out",
        str(out),
        "--report-dir",
        str(REPORTS),
        "--watchlist",
        str(WATCHLIST),
        "--generated-on",
        OBSERVED_ON.isoformat(),
        "--site-url",
        SITE_URL,
        "--changelogs",
        str(repo),
        *extra,
    ]
    result = runner.invoke(app, arguments, env={"EMENDRIX_OUTPUT_REPO": ""})
    assert result.exit_code == 0, result.output
    return result


def test_no_cache_a_cold_cache_and_a_warm_cache_write_the_same_bytes(
    tmp_path: Path, changelog_repo: Path
) -> None:
    cache = tmp_path / "comparisons"
    plain = _build(tmp_path / "none", changelog_repo)
    cold = _build(tmp_path / "cold", changelog_repo, "--comparison-cache", str(cache))
    warm = _build(tmp_path / "warm", changelog_repo, "--comparison-cache", str(cache))
    tree = _tree(tmp_path / "none")
    assert _tree(tmp_path / "cold") == tree
    assert _tree(tmp_path / "warm") == tree
    assert "comparisons:" not in plain.output
    assert "comparisons: 0 reused" in cold.output and "0 rejected" in cold.output
    assert "0 computed" in warm.output and "0 rejected" in warm.output
    assert list(cache.rglob("*.json")), "the cold build wrote what it computed"
    assert not list(cache.rglob("*.tmp")), "no temporary file is left behind"
    assert cold.output.splitlines()[0] == plain.output.splitlines()[0].replace("/none", "/cold")


def test_a_damaged_entry_is_recomputed_and_repaired(tmp_path: Path, changelog_repo: Path) -> None:
    cache = tmp_path / "comparisons"
    _build(tmp_path / "cold", changelog_repo, "--comparison-cache", str(cache))
    entries = sorted(cache.rglob("*.json"))
    good = entries[0].read_bytes()
    entries[0].write_bytes(good[: len(good) // 2])
    rebuilt = _build(tmp_path / "again", changelog_repo, "--comparison-cache", str(cache))
    assert _tree(tmp_path / "again") == _tree(tmp_path / "cold")
    summary = f"comparisons: {len(entries) - 1} reused, 1 computed, 1 rejected"
    assert summary in rebuilt.output, "a truncated entry is rejected and computed again"
    assert entries[0].read_bytes() == good


def test_an_unwritable_cache_is_reported_and_the_site_is_unchanged(
    tmp_path: Path, changelog_repo: Path
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file where the directory should be\n", encoding="utf-8")
    _build(tmp_path / "none", changelog_repo)
    result = _build(tmp_path / "blocked", changelog_repo, "--comparison-cache", str(blocker))
    assert _tree(tmp_path / "blocked") == _tree(tmp_path / "none")
    assert "--comparison-cache could not be written" in result.stderr
    assert "without saving" in result.stderr
    assert "comparisons: 0 reused" in result.stdout


def test_without_the_flag_the_summary_is_one_line(tmp_path: Path, changelog_repo: Path) -> None:
    result = _build(tmp_path / "site", changelog_repo)
    assert len(result.output.splitlines()) == 1
    assert "comparisons" not in result.output
