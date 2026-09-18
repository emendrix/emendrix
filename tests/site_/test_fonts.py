"""The self-hosted fonts as committed files: few, small, licensed, and named for what they are.

The site loads its faces from itself since 2026-09-18. What a reader downloads for them is set
here rather than left to whoever next regenerates them: at most four files, at most 180 KB
between them, and every family's licence text beside its files, because both families are
under the SIL Open Font License 1.1 and that licence travels with every copy.
"""

from __future__ import annotations

from importlib.resources import files

from emendrix.site_.assets import font_files

_MAX_FILES = 4
_BUDGET = 180 * 1024
"""184,320 bytes. The three faces measured 66,268 bytes on 2026-09-18."""

_LICENCES = {"sans": "LICENSE-IBMPlexSans.txt", "serif": "LICENSE-SourceSerif4.txt"}
"""Each family's file-name prefix, and the licence text that must sit beside its files."""


def test_the_fonts_stay_within_their_budget() -> None:
    fonts = font_files()
    assert 0 < len(fonts) <= _MAX_FILES
    assert sum(len(content) for _, content in fonts) <= _BUDGET


def test_every_file_is_a_woff2_named_for_its_family_and_weight() -> None:
    for name, content in font_files():
        assert content.startswith(b"wOF2"), name
        family, _, weight = name.removesuffix(".woff2").partition("-")
        assert family in _LICENCES, name
        assert weight.isdigit(), name


def test_every_family_ships_its_licence_beside_its_files() -> None:
    directory = files("emendrix.site_.static") / "fonts"
    families = {name.partition("-")[0] for name, _ in font_files()}
    for family in families:
        licence = (directory / _LICENCES[family]).read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE Version 1.1" in licence, family
    assert (directory / "README.md").is_file()
