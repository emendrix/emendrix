"""The stylesheet as a measured artifact: contrast in both schemes, and cascade order.

Nothing under `tests/` read a colour before 2026-09-03. The site ships two palettes, one of
them reached only through a media query nobody looks at on a machine set the other way, so a
value that fell below the readable line in one scheme would be invisible to every other test
in this suite and to every reviewer whose laptop prefers the other. This module computes the
WCAG 2.1 contrast ratio itself, in twenty lines and with no dependency, over the pairs the
sheet actually paints, and fails under 4.5:1.

4.5:1 is the AA threshold for body text (WCAG 2.1 SC 1.4.3) and every pair in `_PAIRS` carries
body text at some size, so the large-text allowance of 3:1 is deliberately not used: a
threshold that depends on the rendered size of a run of text is not something a test over a
stylesheet can check honestly.

`_BOUNDARY_PAIRS` is the second floor and a different criterion. A component boundary carries
no text, and SC 1.4.11 asks 3:1 of it rather than 4.5:1, so holding a border to the text
threshold would be a check the sheet could only pass by drawing borders as dark as words. The
two minima are separate constants and neither is ever used for the other's pairs.

The check is only as complete as the palette is closed, so `test_every_colour_in_the_sheet_is
_a_palette_value` asserts that no hex value appears outside a custom-property declaration.
A rule that painted its own `#8a3d10` would otherwise pass by being invisible here.
"""

from __future__ import annotations

import re

import pytest

from emendrix.site_.style import STYLE

_DARK = "@media (prefers-color-scheme: dark)"
"""Where the light palette stops and the override begins. Both blocks name the same tokens."""

_TOKEN = re.compile(r"--([a-z0-9-]+):\s*(#[0-9a-f]{6})\b")
_ANY_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

_PAIRS: tuple[tuple[str, str], ...] = (
    ("fg", "bg"),
    ("fg", "panel"),
    ("fg", "mark"),
    ("fg", "ins"),
    ("fg", "del"),
    ("muted", "bg"),
    ("muted", "panel"),
    ("muted", "mark"),
    ("accent", "bg"),
    ("accent", "panel"),
    ("accent", "mark"),
    ("warn", "bg"),
    ("warn", "panel"),
    ("warn", "mark"),
)
"""Every foreground the sheet sets against every surface it sets it on.

`--mark` is in the list three times over because it is the busiest surface on the site: the
credibility strip, the disclaimer box, a targeted change block, a hovered search result and
the change-type pill all sit on it. `--rule` is absent because it is a hairline that separates
things a reader can already see apart, so nothing depends on finding its edge; `--edge`, which
draws boundaries that are themselves the information, is checked below at its own threshold.
"""

_MINIMUM = 4.5
"""SC 1.4.3, text at normal size. Applies to `_PAIRS` and to nothing else."""

_BOUNDARY_PAIRS: tuple[tuple[str, str], ...] = (
    ("edge", "bg"),
    ("edge", "panel"),
    ("edge", "mark"),
)
"""Every surface the sheet draws a component boundary on.

`--edge` borders the change-type pill and the tag, whose extent is the information: a reader
who cannot find the edge of a pill cannot tell where one label stops and the next begins. The
three surfaces are the page ground, a panel and the busy `--mark`, which is the pill's own
default background and therefore the tightest of the three in both schemes.
"""

_BOUNDARY_MINIMUM = 3.0
"""SC 1.4.11, a non-text boundary. Applies to `_BOUNDARY_PAIRS` and to nothing else."""


def _channel(value: float) -> float:
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(colour: str) -> float:
    """WCAG 2.1 relative luminance of an `#rrggbb` string."""
    red, green, blue = (_channel(int(colour[at : at + 2], 16) / 255) for at in (1, 3, 5))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one: str, other: str) -> float:
    """The WCAG 2.1 contrast ratio of two `#rrggbb` strings, between 1 and 21."""
    first, second = _luminance(one), _luminance(other)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def _palettes() -> dict[str, dict[str, str]]:
    """The two schemes as token maps. Dark is the light one with the override applied."""
    light_source, marker, dark_source = STYLE.partition(_DARK)
    assert marker, "the dark scheme is declared by one media query and this is its text"
    light = dict(_TOKEN.findall(light_source))
    assert light, "the light palette is the `:root` block and it must come first"
    return {"light": light, "dark": light | dict(_TOKEN.findall(dark_source))}


def test_the_two_palettes_declare_the_same_tokens() -> None:
    """A token the dark block forgets falls back to a light value on a dark background."""
    _, _, dark_source = STYLE.partition(_DARK)
    overridden = {name for name, _ in _TOKEN.findall(dark_source)}
    light = set(_palettes()["light"])
    assert light - overridden == set(), "every colour token is answered in both schemes"


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize(("foreground", "background"), _PAIRS)
def test_every_painted_pair_is_readable_in_both_schemes(
    scheme: str, foreground: str, background: str
) -> None:
    """4.5:1 or the build fails, measured rather than eyeballed on one reviewer's machine.

    Measured on 2026-09-03 over the palette as it stands, which is why no hex moved in the
    pass that added this test: the weakest pair of the twenty-eight is muted on mark, 5.66
    light and 5.32 dark, and the strongest is foreground on panel at 17.07.
    """
    palette = _palettes()[scheme]
    ratio = contrast(palette[foreground], palette[background])
    assert ratio >= _MINIMUM, (
        f"{scheme}: --{foreground} on --{background} is {ratio:.2f}:1, under {_MINIMUM}:1"
    )


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize(("boundary", "surface"), _BOUNDARY_PAIRS)
def test_every_component_boundary_is_visible_in_both_schemes(
    scheme: str, boundary: str, surface: str
) -> None:
    """3:1 or the build fails, the floor SC 1.4.11 sets for a boundary carrying no text.

    Measured on 2026-09-03, the day `--edge` was added: light 3.20 to 3.75 and dark 3.44 to
    4.42, the tightest of the six being edge on mark in the light scheme. The pill and the tag
    drew their borders in `--rule` until then, at 1.31:1 light and 1.46:1 dark, which is a
    boundary a reader has to already know is there.
    """
    palette = _palettes()[scheme]
    ratio = contrast(palette[boundary], palette[surface])
    assert ratio >= _BOUNDARY_MINIMUM, (
        f"{scheme}: --{boundary} on --{surface} is {ratio:.2f}:1, under {_BOUNDARY_MINIMUM}:1"
    )


def test_the_two_line_colours_are_used_for_their_own_job() -> None:
    """A component boundary reaches `--edge` and a hairline reaches `--rule`, both by name.

    Cheap, and it catches the one way this pass could rot: a later rule drawing a pill-like
    border in `--rule` would be under the 3:1 floor and invisible to the check above, which
    reads the palette rather than the selectors.
    """
    assert "--edge: " in STYLE
    for selector in (".pill {", ".tag {"):
        block = STYLE.split(selector)[1].split("}")[0]
        assert "var(--edge)" in block, selector
        assert "var(--rule)" not in block, selector


def test_every_colour_in_the_sheet_is_a_palette_value() -> None:
    """No rule paints its own hex, which is what makes the contrast check above total."""
    declared = _TOKEN.findall(STYLE)
    assert len(_ANY_HEX.findall(STYLE)) == len(declared)


# ------------------------------------------------------------------ the sheet's shape


def test_the_sheet_serves_both_schemes_and_paper() -> None:
    """One `color-scheme`, one dark override, one print block, and no toggle anywhere."""
    assert "color-scheme: light dark;" in STYLE
    assert _DARK in STYLE
    assert "@media print" in STYLE


def test_a_diff_mark_says_which_it_is_without_its_tint() -> None:
    """Colour is never the only marker inside a diff, on screen as on paper.

    An insertion is underlined and a deletion struck through by the screen rules themselves,
    which is why the print block no longer redeclares the underline it used to add for a
    printer with no colour: a compensation in one medium is a gap in the other.
    """
    screen, marker, printed = STYLE.partition("@media print")
    assert marker
    # Split on the newline too: the rule these two share names `.diff del` in its own selector.
    assert "text-decoration: underline" in screen.split("\n.diff ins {")[1].split("}")[0]
    assert "line-through" in screen.split("\n.diff del {")[1].split("}")[0]
    assert ".diff ins" not in printed


def test_the_modules_are_concatenated_in_cascade_order() -> None:
    """Tokens, then the shell, then the pages, then the evidence.

    The package is four `Final` strings joined in one place, so what can drift is the order
    they are joined in, and the order is a contract: a rule in a later module may rely on an
    earlier one and never the reverse. One selector from each module, in the order they must
    appear, is the cheapest way to hold it.
    """
    assert STYLE.index("--bg:") < STYLE.index("header.bar")
    assert STYLE.index("header.bar") < STYLE.index(".cardrow")
    assert STYLE.index(".cardrow") < STYLE.index(".chg")


def test_the_sheet_reaches_no_third_party_and_names_no_web_font() -> None:
    """The same promise `tests/site_/test_golden.py` makes over the written file.

    Asserted over the constant as well, because this is where a font import would be typed
    and a failure here names the module that grew it rather than a built artifact.
    """
    for banned in ("http://", "https://", "@import", "url("):
        assert banned not in STYLE, banned
