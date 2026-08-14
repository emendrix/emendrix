"""The shipped command chain writes the whole tree, deterministically.

The tree is built the way a deployment builds it: `emendrix explain` writes a real changelog
into an output repository under `tmp_path` from pinned fixtures and committed cassettes, and
`emendrix site build` renders the site from that repository and from the newest committed
evaluation report. Nothing here asserts anything about explanation quality; what it asserts is
that the command writes every surface, twice over, to the same bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import REPORTS, WATCHLIST, _tree, build, runner

from emendrix.cli import app
from emendrix.core import ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import diff_only_entry
from emendrix.site_ import collect_site, write_site
from eu_pins import OBSERVED_ON
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter


def test_the_command_writes_every_surface(tmp_path: Path, changelog_repo: Path) -> None:
    out = build(tmp_path / "site", changelog_repo)
    tree = _tree(out)
    for expected in (
        "index.html",
        "404.html",
        "style.css",
        "search.js",
        "icon.svg",
        "og.png",
        "robots.txt",
        "search-index.json",
        "sitemap.xml",
        "acts/index.html",
        "methodology/index.html",
        "feeds/index.html",
        "feeds/all.xml",
    ):
        assert expected in tree, expected
    assert any(name.startswith("acts/") and name.endswith("/index.html") for name in tree)


def test_the_committed_assets_are_copied_and_not_re_encoded(
    tmp_path: Path, changelog_repo: Path
) -> None:
    """The card is a raster image: decoding it to text and back would corrupt it silently.

    The signature check is the cheap proof that the bytes branch of the writer ran, and the
    icon's opening tag is the same proof for the text one.
    """
    out = build(tmp_path / "site", changelog_repo)
    assert (out / "og.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "<svg" in (out / "icon.svg").read_text(encoding="utf-8")


def test_every_watched_act_gets_a_page_and_a_feed_including_the_quiet_ones(
    tmp_path: Path, changelog_repo: Path
) -> None:
    """A quiet act is a real answer, so a link to its feed may not resolve to nothing."""
    out = build(tmp_path / "site", changelog_repo)
    tree = _tree(out)
    slugs = {
        name.split("/")[1] for name in tree if name.startswith("acts/") and name.count("/") > 1
    }
    assert len(slugs) == 4, slugs
    for act_slug in slugs:
        assert f"feeds/{act_slug}.xml" in tree, act_slug


def test_two_builds_of_one_set_of_artifacts_are_byte_identical(
    tmp_path: Path, changelog_repo: Path
) -> None:
    first = _tree(build(tmp_path / "a", changelog_repo))
    second = _tree(build(tmp_path / "b", changelog_repo))
    assert first == second


def test_the_search_index_is_valid_json_at_the_site_root(
    tmp_path: Path, changelog_repo: Path
) -> None:
    """The script fetches it relative to `data-root`, so the path is part of the contract."""
    out = build(tmp_path / "site", changelog_repo)
    payload = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    assert payload["entries"]
    assert (out / "search.js").read_text(encoding="utf-8").strip()


def test_no_changelog_repository_is_a_site_that_says_so(tmp_path: Path) -> None:
    out = build(tmp_path / "site", None)
    home = (out / "index.html").read_text(encoding="utf-8")
    assert "No changelog repository was configured" in home


def test_the_builder_leaves_everything_else_in_the_directory_alone(
    tmp_path: Path, changelog_repo: Path
) -> None:
    """The operator owns the output directory; the builder writes its own files and no others."""
    out = tmp_path / "site"
    out.mkdir()
    kept = out / "CNAME"
    kept.write_text("example.invalid\n", encoding="utf-8")
    build(out, changelog_repo)
    assert kept.read_text(encoding="utf-8") == "example.invalid\n"


def test_without_a_site_url_no_feed_files_are_written(tmp_path: Path, changelog_repo: Path) -> None:
    """The crawl policy is written either way, because it needs no absolute address.

    The `.xml` sweep below guards two artifacts rather than one: a sitemap's locations are
    absolute for the same reason a feed's links are, so neither file is written without a base.
    """
    arguments = [
        "site",
        "build",
        "--out",
        str(tmp_path / "site"),
        "--report-dir",
        str(REPORTS),
        "--watchlist",
        str(WATCHLIST),
        "--generated-on",
        OBSERVED_ON.isoformat(),
        "--changelogs",
        str(changelog_repo),
    ]
    result = runner.invoke(app, arguments, env={"EMENDRIX_OUTPUT_REPO": ""})
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "site" / "feeds" / "all.xml").exists()
    assert not list((tmp_path / "site").rglob("*.xml"))
    robots = (tmp_path / "site" / "robots.txt").read_text(encoding="utf-8")
    assert robots.startswith("User-agent: *")
    assert "Sitemap:" not in robots
    feeds_page = (tmp_path / "site" / "feeds" / "index.html").read_text(encoding="utf-8")
    assert "no site URL was configured" in feeds_page


def test_without_a_site_url_the_root_assets_and_the_not_found_page_are_still_written(
    tmp_path: Path, changelog_repo: Path
) -> None:
    """What needs a base address is a reference to an asset, never the asset itself.

    The icon is linked relatively from every head and the not-found page is served by the host
    for an address that matched nothing, so neither depends on the site knowing where it lives.
    """
    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--out",
            str(tmp_path / "site"),
            "--report-dir",
            str(REPORTS),
            "--watchlist",
            str(WATCHLIST),
            "--generated-on",
            OBSERVED_ON.isoformat(),
            "--changelogs",
            str(changelog_repo),
        ],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 0, result.output
    for expected in ("404.html", "icon.svg", "og.png"):
        assert (tmp_path / "site" / expected).exists(), expected


def test_the_command_refuses_a_non_https_site_url(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--out",
            str(tmp_path / "s"),
            "--report-dir",
            str(REPORTS),
            "--site-url",
            "http://example.invalid",
        ],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 2
    assert "https://" in result.output


def test_the_command_refuses_a_repo_url_that_is_not_https(tmp_path: Path) -> None:
    """A `javascript:` or `http://` value would put an attacker-shaped link on a public site."""
    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--out",
            str(tmp_path / "s"),
            "--report-dir",
            str(REPORTS),
            "--repo-url",
            "javascript:alert(1)",
        ],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 2
    assert "must be an https:// URL" in result.output


def test_the_command_refuses_a_changelogs_url_that_is_not_https(tmp_path: Path) -> None:
    """The same rule `--repo-url` lives under: only https:// may reach a public footer."""
    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--out",
            str(tmp_path / "s"),
            "--report-dir",
            str(REPORTS),
            "--changelogs-url",
            "http://example.invalid/changelogs",
        ],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 2
    assert "must be an https:// URL" in result.output


def test_the_environment_variable_is_the_second_source_of_the_changelog_repository(
    tmp_path: Path, changelog_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--changelogs` > `EMENDRIX_OUTPUT_REPO` > `watchlist.toml`, the same order `run` uses."""
    monkeypatch.setenv("EMENDRIX_OUTPUT_REPO", str(changelog_repo))
    out = tmp_path / "site"
    result = runner.invoke(
        app,
        [
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
        ],
    )
    assert result.exit_code == 0, result.output
    assert "No changelog repository was configured" not in (out / "index.html").read_text(
        encoding="utf-8"
    )


def test_a_trailing_slash_on_the_site_url_does_not_reach_the_feeds(
    tmp_path: Path, changelog_repo: Path
) -> None:
    """`{site_url}/{path}` is joined once, so the base may not carry a separator of its own."""
    out = build(tmp_path / "site", changelog_repo, "--site-url", "https://example.invalid/site/")
    feed = (out / "feeds" / "all.xml").read_text(encoding="utf-8")
    assert "//acts/" not in feed
    assert "https://example.invalid/site/acts/" in feed


def test_the_summary_names_the_report_the_numbers_came_from(
    tmp_path: Path, changelog_repo: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--out",
            str(tmp_path / "site"),
            "--report-dir",
            str(REPORTS),
            "--watchlist",
            str(WATCHLIST),
            "--generated-on",
            OBSERVED_ON.isoformat(),
            "--changelogs",
            str(changelog_repo),
        ],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 0, result.output
    assert "pages" in result.output
    assert "4 acts" in result.output
    assert "numbers from" in result.output


def test_the_builder_runs_on_a_corpus_that_is_not_law_at_all(tmp_path: Path) -> None:
    """`write_site` is a plain function of its inputs, and the toy corpus is a whole site.

    The paths come back relative and sorted, which is what the summary line counts and what a
    caller would have to compare against a committed tree.
    """
    adapter = ToyCorpusAdapter(observed_on=OBSERVED_ON)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    entry = diff_only_entry(compute_delta(before, after), detected_on=OBSERVED_ON)
    site = collect_site(
        generated_on=OBSERVED_ON,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(entry,),
        configured=True,
        site_url="https://example.invalid",
    )
    written = write_site(tmp_path / "site", site)
    assert list(written) == sorted(written)
    assert all(not path.is_absolute() for path in written)
    assert Path("feeds/all.xml") in written
    assert Path(f"acts/{site.acts[0].slug}/index.html") in written
