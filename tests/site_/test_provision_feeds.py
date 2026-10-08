"""One provision's Atom feed and one OPML file per act: ids that cannot collide, and no text.

The properties are read off two trees. The golden build, through the shipped command, is where
an id is checked against the `id=` the version page it names actually carries, because a feed
entry pointing at a fragment no page holds is a promise to a subscriber that resolves to the
top of a page. The toy and fixture entries are where the shapes the golden lacks are checked: a
history of two steps, and a change where the sources differ.

The feeds are parsed back with `emendrix.eu.xml_`, the hardened parser, for the habit's sake:
these bytes come from this process, but the project parses XML through that one module.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from helpers import REPORTS, SITE_URL, WATCHLIST, build, runner
from site_entries import OBSERVED_ON, disputed_entry

from emendrix import DISCLAIMER
from emendrix.cli import app
from emendrix.core import ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.eu import xml_
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.dispute import REASON_SENTENCES
from emendrix.site_.feeds import feed_path, render_feed
from emendrix.site_.history import histories
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.pages.provision import render_provision_page
from emendrix.site_.pages.texts import text_blocks
from emendrix.site_.provision_feeds import (
    opml_path,
    provision_feed_files,
    provision_feed_path,
    render_opml,
    render_provision_feed,
)
from emendrix.site_.urls import event_href, location_slug
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

GOLDEN = Path(__file__).resolve().parent / "golden"
ATOM = "{http://www.w3.org/2005/Atom}"
_IDS = re.compile(r'\bid="([^"]+)"')


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("provision-feeds") / "site", changelog_repo)


def _toy_entry(index: int) -> ChangelogEntry:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED_ON)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    delta = compute_delta(before, after).model_copy(
        update={
            "from_version": VersionId(f"v{index}"),
            "to_version": VersionId(f"v{index + 1}"),
        }
    )
    return diff_only_entry(delta, detected_on=OBSERVED_ON + timedelta(days=index))


def _site(*entries: ChangelogEntry, site_url: str = SITE_URL) -> SiteInputs:
    return collect_site(
        generated_on=OBSERVED_ON,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=entries,
        site_url=site_url,
    )


def _parse(text: str) -> Element:
    return xml_.fromstring(text.encode("utf-8"))


def _entry_ids(text: str) -> list[str]:
    root = _parse(text)
    return [entry.findtext(f"{ATOM}id") or "" for entry in root.findall(f"{ATOM}entry")]


def _built_feeds(site: Path) -> dict[str, str]:
    return {
        path.relative_to(site).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted((site / "feeds" / "acts").rglob("*.xml"))
    }


def test_one_feed_per_touched_provision_and_none_for_an_untouched_one(site: Path) -> None:
    feeds = _built_feeds(site)
    assert len(feeds) == 9
    provision_pages = {
        path.parent.name
        for path in (site / "acts" / "32017R0745").glob("*/index.html")
        if not path.parent.name[0].isdigit()
    }
    assert {Path(path).stem for path in feeds} == provision_pages
    assert all(path.startswith("feeds/acts/32017R0745/") for path in feeds)
    # The three quiet acts have no provision to follow, so no directory at all.
    assert [path.name for path in (site / "feeds" / "acts").iterdir()] == ["32017R0745"]


def test_the_path_is_the_location_slug_and_no_two_paths_collide() -> None:
    site = _site(_toy_entry(2), _toy_entry(1))
    act = site.acts[0]
    found = histories(act)
    paths = [provision_feed_path(act, history.location.canonical) for history in found]
    assert len(set(paths)) == len(paths) == len(found)
    for history, path in zip(found, paths, strict=True):
        assert path == f"feeds/acts/{act.slug}/{location_slug(history.location.canonical)}.xml"
    assert opml_path(act) not in paths


def test_every_entry_id_is_the_change_block_on_the_version_page_the_build_writes(
    site: Path,
) -> None:
    entries = 0
    for path, text in _built_feeds(site).items():
        for ident in _entry_ids(text):
            entries += 1
            address, anchor = ident.split("#")
            assert address.startswith(f"{SITE_URL}/acts/"), path
            page = site / address.removeprefix(f"{SITE_URL}/") / "index.html"
            assert anchor in _IDS.findall(page.read_text(encoding="utf-8")), (path, anchor)
            assert anchor.endswith(Path(path).stem), path
    assert entries == 9


def test_the_ids_are_built_from_the_steps_own_anchors() -> None:
    site = _site(_toy_entry(2), _toy_entry(1))
    act = site.acts[0]
    for history in histories(act):
        expected = [
            f"{SITE_URL}/{event_href(act.slug, step.entry.key)}#{step.anchor}"
            for step in history.steps
        ]
        assert _entry_ids(render_provision_feed(site, act, history)) == expected


def test_no_provision_feed_id_is_an_act_feed_or_global_feed_id(site: Path) -> None:
    act_ids = {
        ident
        for path in (site / "feeds").glob("*.xml")
        for ident in _entry_ids(path.read_text(encoding="utf-8"))
    }
    assert act_ids
    provision_ids = {ident for text in _built_feeds(site).values() for ident in _entry_ids(text)}
    assert provision_ids and not provision_ids & act_ids


def test_the_act_feeds_are_the_committed_bytes(site: Path) -> None:
    """No act feed or global feed byte moved when the provision feeds arrived beside them."""
    for path in sorted((GOLDEN / "feeds").glob("*.xml")):
        assert (site / "feeds" / path.name).read_bytes() == path.read_bytes(), path.name


def test_the_two_framings_agree() -> None:
    """Written twice on purpose, so a test holds the declaration, namespace and author lines."""
    site = _site(_toy_entry(1))
    act = site.acts[0]
    act_lines = render_feed(site, act).split("\n")
    lines = render_provision_feed(site, act, histories(act)[0]).split("\n")
    assert lines[:2] == act_lines[:2]
    assert lines[7] == act_lines[7] == "<author><name>emendrix</name></author>"
    assert lines[-2:] == act_lines[-2:] == ["</feed>", ""]
    assert [re.split("[ >]", line)[0] for line in lines[2:7]] == [
        re.split("[ >]", line)[0] for line in act_lines[2:7]
    ]


def test_two_renderings_are_byte_identical_and_a_moved_base_moves_every_id() -> None:
    entries = (_toy_entry(2), _toy_entry(1))
    first, second = provision_feed_files(_site(*entries)), provision_feed_files(_site(*entries))
    assert first == second and first
    moved = provision_feed_files(_site(*entries, site_url="https://example.invalid/moved"))
    assert moved.keys() == first.keys()
    for path, text in first.items():
        if path.endswith(".xml"):
            old, new = _entry_ids(text), _entry_ids(moved[path])
            assert old and not set(old) & set(new), path


def test_every_entry_carries_the_disclaimer_and_none_carries_the_text() -> None:
    site = _site(_toy_entry(2), _toy_entry(1))
    act = site.acts[0]
    checked = 0
    for history in histories(act):
        root = _parse(render_provision_feed(site, act, history))
        for entry, step in zip(root.findall(f"{ATOM}entry"), history.steps, strict=True):
            summary = entry.findtext(f"{ATOM}summary") or ""
            assert summary.endswith(DISCLAIMER)
            for side in (step.change.before, step.change.after):
                if side is not None and len(side.strip()) > 20:
                    sentence = side.strip().splitlines()[-1].strip()
                    assert sentence not in summary
                    checked += 1
    assert checked


def test_a_change_where_the_sources_differ_carries_its_reason_sentence() -> None:
    site = _site(disputed_entry())
    act = site.acts[0]
    said = 0
    for history in histories(act):
        change = history.steps[0].change
        summary = _parse(render_provision_feed(site, act, history)).findtext(
            f"{ATOM}entry/{ATOM}summary"
        )
        assert summary is not None
        if change.disputed:
            assert change.dispute_reason is not None
            assert f"Sources differ: {REASON_SENTENCES[change.dispute_reason]}" in summary
            said += 1
        else:
            assert "Sources differ" not in summary
    assert said == 1


def test_the_opml_lists_exactly_the_acts_provision_feeds_in_history_order() -> None:
    site = _site(_toy_entry(2), _toy_entry(1))
    act = site.acts[0]
    root = _parse(render_opml(site, act))
    assert root.get("version") == "2.0"
    assert root.find("head/dateCreated") is None
    outlines = root.findall("body/outline")
    assert outlines[0].get("text") == DISCLAIMER
    assert [outline.get("xmlUrl") for outline in outlines[1:]] == [
        f"{SITE_URL}/{provision_feed_path(act, history.location.canonical)}"
        for history in histories(act)
    ]
    assert all(outline.get("type") == "rss" for outline in outlines[1:])


def test_the_disclaimer_can_stand_in_an_xml_comment() -> None:
    assert "--" not in DISCLAIMER
    site = _site(_toy_entry(1))
    assert f"<!-- {DISCLAIMER} -->" in render_opml(site, site.acts[0])


def test_without_a_site_url_there_is_no_provision_feed_and_no_link_to_one() -> None:
    entry = _toy_entry(1)
    site = _site(entry, site_url="")
    assert provision_feed_files(site) == {}
    act = site.acts[0]
    history = histories(act)[0]
    page = render_provision_page(site, act, history, text_blocks(entry, act.entries))
    assert "Follow this provision" not in page
    assert "watch-in-ci" not in page
    assert "feeds/acts/" not in page


def test_without_a_site_url_the_build_writes_no_provision_feed_or_opml(
    tmp_path: Path, changelog_repo: Path
) -> None:
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
            "--changelogs",
            str(changelog_repo),
        ],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 0, result.output
    assert not (out / "feeds" / "acts").exists()
    assert not list(out.rglob("*.opml"))
    assert "0 provision feeds" in result.output
    page = (out / "acts" / "32017R0745" / "ar-17" / "index.html").read_text(encoding="utf-8")
    assert "Follow this provision" not in page


def test_the_summary_counts_provision_feeds_apart_from_the_act_feeds(
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
            "--site-url",
            SITE_URL,
            "--changelogs",
            str(changelog_repo),
        ],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 0, result.output
    assert ", 5 feeds, 9 provision feeds, 4 acts," in result.output


def test_a_provision_page_links_its_feed_and_the_ci_example(site: Path) -> None:
    for page in sorted((site / "acts" / "32017R0745").glob("*/index.html")):
        slug = page.parent.name
        if slug[0].isdigit():
            continue
        text = page.read_text(encoding="utf-8")
        feed = f"../../../feeds/acts/32017R0745/{slug}.xml"
        assert f'<a href="{feed}">Follow this provision (Atom)</a>' in text, slug
        assert '<a href="../../../api/#watch-in-ci">Watch it from CI</a>' in text, slug
        assert (site / "api" / "index.html").read_text(encoding="utf-8").count(
            'id="watch-in-ci"'
        ) == 1


def test_the_feeds_page_links_each_acts_opml_with_its_count(site: Path) -> None:
    text = (site / "feeds" / "index.html").read_text(encoding="utf-8")
    assert (
        '<a href="../feeds/acts/32017R0745/provisions.opml">every provision of this act, as '
        'OPML</a> <span class="muted">9 provision feeds</span>'
    ) in text
    assert text.count(".opml") == 1
    assert (site / "feeds" / "acts" / "32017R0745" / "provisions.opml").is_file()
    assert feed_path(None) == "feeds/all.xml"
