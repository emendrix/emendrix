"""`site build --prune`: what a build did not write goes, and what a person placed stays.

The selector is tested on paths alone; the command is tested over a built tree seeded with a
stale page, a superseded asset and the files a person might drop into a deployed directory.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
from helpers import REPORTS, SITE_URL, WATCHLIST, build, runner

from emendrix.cli import app
from emendrix.site_.fingerprint import FONTS, SCRIPT, STYLESHEET
from emendrix.site_.prune import kept, listing, prune, stale
from eu_pins import OBSERVED_ON

P = PurePosixPath

_PLACED = (
    ".well-known/security.txt",
    ".htaccess",
    "acts/.keep",
    "google1a2b3c4d5e6f7a8b.html",
    "BingSiteAuth.xml",
)
_OLD_ASSETS = (
    "style.css",
    "search.js",
    "style.0123abcd.css",
    "search.89abcdef.js",
    *(name.replace(".woff2", ".00000000.woff2") for name in FONTS),
)


@pytest.mark.parametrize("name", [*_PLACED, *_OLD_ASSETS, STYLESHEET, SCRIPT])
def test_a_placed_file_or_a_superseded_asset_is_kept(name: str) -> None:
    assert kept(P(name))
    assert stale([P(name)], []) == ()


@pytest.mark.parametrize(
    "name",
    [
        "acts/32006R1907/an-17/index.html",
        "amendments/32014R0182/index.html",
        "acts/style.0123abcd.css",  # an asset name counts only at the root
        "style.0123abc.css",  # seven hex characters is not a digest this build writes
        "style.extra.css",
        "search.0123abcd.css",
        "googlefoo.txt",
        "acts/google1a2b.html",
        "styles.css",
    ],
)
def test_anything_else_this_build_did_not_write_is_stale(name: str) -> None:
    assert not kept(P(name))
    assert stale([P(name)], []) == (P(name),)


def test_a_written_file_is_never_stale() -> None:
    present = [P("index.html"), P("acts/a/index.html"), P("acts/b/index.html")]
    assert stale(present, [P("index.html"), P("acts/a/index.html")]) == (P("acts/b/index.html"),)


def test_a_written_file_is_kept_whatever_case_the_disk_kept_its_name_in() -> None:
    assert stale([P("acts/A/index.html")], [P("acts/a/index.html")]) == ()


def _seed(out: Path) -> None:
    for name in ("acts/32006R1907/an-17/index.html", "acts/32006R1907/an-17/deep/x.html"):
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_text("stale", encoding="utf-8")
    for name in (*_PLACED, "style.0123abcd.css", "search.js"):
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_text("placed", encoding="utf-8")
    (out / "empty-by-hand").mkdir()


def test_prune_deletes_stale_files_and_the_directories_they_emptied(tmp_path: Path) -> None:
    out = tmp_path / "site"
    (out / "acts" / "a").mkdir(parents=True)
    (out / "acts" / "a" / "index.html").write_text("kept", encoding="utf-8")
    _seed(out)
    dry = prune(out, [Path("acts/a/index.html")], dry_run=True)
    assert dry.files == (
        P("acts/32006R1907/an-17/deep/x.html"),
        P("acts/32006R1907/an-17/index.html"),
    )
    assert dry.directories == ()
    assert (out / "acts/32006R1907/an-17/index.html").is_file()

    done = prune(out, [Path("acts/a/index.html")], dry_run=False)
    assert done.files == dry.files
    assert done.directories == (
        P("acts/32006R1907"),
        P("acts/32006R1907/an-17"),
        P("acts/32006R1907/an-17/deep"),
    )
    assert not (out / "acts/32006R1907").exists()
    assert (out / "acts/a/index.html").is_file()
    assert (out / "empty-by-hand").is_dir()
    assert out.is_dir()
    for name in (*_PLACED, "style.0123abcd.css", "search.js"):
        assert (out / name).is_file(), name


def test_a_link_is_never_followed_nor_deleted(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.html").write_text("x", encoding="utf-8")
    out = tmp_path / "site"
    out.mkdir()
    (out / "linked-dir").symlink_to(outside, target_is_directory=True)
    (out / "linked-file.html").symlink_to(outside / "precious.html")
    assert listing(out) == ()
    assert prune(out, [], dry_run=False).files == ()
    assert (outside / "precious.html").is_file()
    assert (out / "linked-file.html").is_symlink()


def test_an_emptied_out_is_never_removed(tmp_path: Path) -> None:
    out = tmp_path / "site"
    out.mkdir()
    (out / "gone.html").write_text("x", encoding="utf-8")
    assert prune(out, [], dry_run=False).directories == ()
    assert out.is_dir() and not any(out.iterdir())


def _invoke(out: Path, repo: Path, *extra: str) -> str:
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
    return result.stderr


def test_the_command_prunes_only_when_asked(tmp_path: Path, changelog_repo: Path) -> None:
    out = tmp_path / "site"
    out.mkdir()
    _seed(out)
    stale_page = out / "acts/32006R1907/an-17/index.html"

    build(out, changelog_repo)
    assert stale_page.is_file()

    said = _invoke(out, changelog_repo, "--prune-dry-run")
    assert "prune (dry run): 2 files would be deleted" in said
    assert "  acts/32006R1907/an-17/index.html" in said
    assert stale_page.is_file()

    said = _invoke(out, changelog_repo, "--prune")
    assert "pruned: 2 files, 2 empty directories" in said
    assert not stale_page.exists()
    assert (out / "style.0123abcd.css").is_file()
    assert (out / "search.js").is_file()
    assert (out / STYLESHEET).is_file()
    for name in _PLACED:
        assert (out / name).is_file(), name

    assert "pruned: 0 files, 0 empty directories" in _invoke(out, changelog_repo, "--prune")


def test_both_prune_flags_at_once_are_refused(tmp_path: Path, changelog_repo: Path) -> None:
    result = runner.invoke(
        app,
        ["site", "build", "--out", str(tmp_path / "site"), "--prune", "--prune-dry-run"],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 2
    assert "exclusive" in result.stderr
