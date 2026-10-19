"""The third sitemap: exactly the twin pages a build writes, named in the sitemap index."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

import pytest
from helpers import SITE_URL, build, twinned

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    root = tmp_path_factory.mktemp("twin-sitemap")
    return build(root / "site", twinned(changelog_repo, root))


def _listed(path: Path, tag: str) -> dict[str, str | None]:
    root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
    return {
        block.findtext(f"{SITEMAP_NS}loc") or "": block.findtext(f"{SITEMAP_NS}lastmod")
        for block in root.findall(f"{SITEMAP_NS}{tag}")
    }


def test_the_twins_sitemap_lists_exactly_the_twin_pages_built(site: Path) -> None:
    listed = _listed(site / "sitemap-twins.xml", "url")
    built = {
        f"{SITE_URL}/{page.relative_to(site).as_posix().removesuffix('index.html')}"
        for page in (site / "twins").rglob("index.html")
    }
    assert set(listed) == built
    assert len(built) == 1 + 1 + 84
    assert set(listed.values()) == {"2025-01-10"}


def test_no_twin_page_is_listed_in_the_main_sitemap(site: Path) -> None:
    assert not any("/twins/" in loc for loc in _listed(site / "sitemap.xml", "url"))


def test_the_index_names_three_sitemaps_and_dates_the_twins_one(site: Path) -> None:
    named = _listed(site / "sitemap_index.xml", "sitemap")
    assert list(named) == [
        f"{SITE_URL}/sitemap.xml",
        f"{SITE_URL}/sitemap-substances.xml",
        f"{SITE_URL}/sitemap-twins.xml",
    ]
    assert named[f"{SITE_URL}/sitemap-twins.xml"] == "2025-01-10"


def test_without_a_map_the_twins_sitemap_is_written_empty(
    tmp_path: Path, changelog_repo: Path
) -> None:
    bare = build(tmp_path / "site", changelog_repo)
    assert _listed(bare / "sitemap-twins.xml", "url") == {}
