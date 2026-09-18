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

from emendrix.site_.fingerprint import FONTS
from emendrix.site_.style import STYLE

_DARK = "@media (prefers-color-scheme: dark)"
"""Where the light palette stops and the override begins. Both blocks name the same tokens."""

_FORCED = "@media (forced-colors: active)"

_TOKEN = re.compile(r"--([a-z0-9-]+):\s*(#[0-9a-f]{6})\b")
_ANY_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

_PAIRS: tuple[tuple[str, str], ...] = (
    ("fg", "bg"),
    ("fg", "panel"),
    ("fg", "mark"),
    ("fg", "notice"),
    ("fg", "ins"),
    ("fg", "del"),
    ("fg", "type-act-tint"),
    ("fg", "type-version-tint"),
    ("fg", "type-provision-tint"),
    ("fg", "type-amending-tint"),
    ("fg", "kind-inserted-tint"),
    ("fg", "kind-deleted-tint"),
    ("fg", "kind-modified-tint"),
    ("fg", "kind-deferred-tint"),
    ("fg", "provenance-tint"),
    ("fg", "alert-tint"),
    ("muted", "bg"),
    ("muted", "panel"),
    ("muted", "mark"),
    ("muted", "notice"),
    ("muted", "type-act-tint"),
    ("muted", "type-version-tint"),
    ("muted", "type-provision-tint"),
    ("muted", "type-amending-tint"),
    ("link", "bg"),
    ("link", "panel"),
    ("link", "mark"),
    ("link", "notice"),
    ("link", "alert-tint"),
    ("link", "type-act-tint"),
    ("link", "type-version-tint"),
    ("link", "type-provision-tint"),
    ("link", "type-amending-tint"),
    ("alert", "bg"),
    ("alert", "panel"),
    ("alert", "mark"),
    ("alert", "alert-tint"),
    ("provenance", "provenance-tint"),
    ("provenance", "bg"),
    ("provenance", "panel"),
    ("kind-inserted", "kind-inserted-tint"),
    ("kind-deleted", "kind-deleted-tint"),
    ("kind-modified", "kind-modified-tint"),
    ("kind-deferred", "kind-deferred-tint"),
    ("kind-inserted", "bg"),
    ("kind-inserted", "panel"),
    ("kind-deleted", "bg"),
    ("kind-deleted", "panel"),
    ("kind-modified", "bg"),
    ("kind-modified", "panel"),
    ("kind-deferred", "bg"),
    ("kind-deferred", "panel"),
    ("provenance", "type-version-tint"),
    ("type-act", "type-act-tint"),
    ("type-version", "type-version-tint"),
    ("type-provision", "type-provision-tint"),
    ("type-amending", "type-amending-tint"),
    ("type-act", "bg"),
    ("type-version", "bg"),
    ("type-provision", "bg"),
    ("type-amending", "bg"),
)
"""Every foreground the sheet sets as text against every surface it sets it on.

The palette was redrawn on 2026-09-18 and this list with it: the ground and its text on every
surface and tint a reader can meet them on, the link on every surface a link sits on, the alert
on the surfaces a disagreement is drawn on, each change kind on its own tint and on the two
grounds, the provenance grey on its tint, and each page type on its band and on the page
ground. Some pairs are declared ahead of the rule that paints them, so a palette change is
checked against every place the palette is meant to be used. `--rule` is absent because it is a
hairline that separates things a reader can already see apart, so nothing depends on finding
its edge; `--edge`, which draws boundaries that are themselves the information, is checked
below at its own threshold.
"""

_MINIMUM = 4.5
"""SC 1.4.3, text at normal size. Applies to `_PAIRS` and to nothing else."""

_BOUNDARY_PAIRS: tuple[tuple[str, str], ...] = (
    ("edge", "bg"),
    ("edge", "panel"),
    ("edge", "mark"),
    ("edge", "notice"),
    ("edge", "type-act-tint"),
    ("edge", "type-version-tint"),
    ("edge", "type-provision-tint"),
    ("edge", "type-amending-tint"),
    ("kind-inserted", "bg"),
    ("kind-inserted", "panel"),
    ("kind-inserted", "mark"),
    ("kind-inserted", "type-version-tint"),
    ("kind-deleted", "bg"),
    ("kind-deleted", "panel"),
    ("kind-deleted", "mark"),
    ("kind-deleted", "type-version-tint"),
    ("kind-modified", "bg"),
    ("kind-modified", "panel"),
    ("kind-modified", "mark"),
    ("kind-modified", "type-version-tint"),
    ("kind-deferred", "bg"),
    ("kind-deferred", "panel"),
    ("kind-deferred", "mark"),
    ("kind-deferred", "type-version-tint"),
    ("alert", "bg"),
    ("alert", "panel"),
    ("alert", "mark"),
    ("alert", "type-version-tint"),
    ("type-act", "type-act-tint"),
    ("type-version", "type-version-tint"),
    ("type-provision", "type-provision-tint"),
    ("type-amending", "type-amending-tint"),
    ("link", "bg"),
    ("link", "panel"),
    ("link", "type-version-tint"),
    ("edge", "provenance-tint"),
    ("fg", "notice"),
    ("type-act", "panel"),
    ("type-version", "bg"),
)
"""Every surface the sheet draws a component boundary on, with the colour it draws it in.

`--edge` borders the tags, the search box, the elision chip and the notice, whose extent is the
information: a reader who cannot find the edge of a tag cannot tell where one label stops and
the next begins. The change kinds, the alert and the page types draw their own borders, rules
and rail nodes, so each is checked on the surfaces it sits on, including the busy `--mark` a
targeted block or a hovered row turns into.
"""

_SEPARATION_MINIMUM = 1.5
"""How far apart the link and the alert must sit, in the same ratio, in both schemes."""

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

    Measured on 2026-09-18 over the palette redrawn that day: the weakest of the hundred and
    twenty-two checks is the link on the amending-act and version tints, 4.67 light, and in
    the dark scheme the alert on mark, 5.02; the strongest is foreground on panel at 17.44.
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

    Measured on 2026-09-18 over the palette redrawn that day, the tightest of the seventy-eight
    checks is edge on the version and amending-act tints, 3.14 light. The search box and the
    elision chip drew their borders in `--rule` until then, at 1.35:1, which is a boundary a
    reader has to already know is there.
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
    reads the palette rather than the selectors. The search box and the elision chip joined
    the list on 2026-09-18, when both moved off `--rule`.
    """
    assert "--edge: " in STYLE
    for selector in (".pill {", ".tag {", "#search input {", ".elided {"):
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


def _print_block() -> tuple[str, str]:
    """The screen rules, and the print block alone, stopping where forced colours begin."""
    screen, marker, rest = STYLE.partition("@media print")
    assert marker
    printed, forced, _ = rest.partition(_FORCED)
    assert forced, "the forced-colours block follows the print block"
    return screen, printed


def test_a_diff_mark_says_which_it_is_without_its_tint() -> None:
    """Colour is never the only marker inside a diff, on screen as on paper.

    An insertion is underlined and a deletion struck through by the screen rules themselves,
    which is why the print block no longer redeclares the underline it used to add for a
    printer with no colour: a compensation in one medium is a gap in the other.
    """
    screen, printed = _print_block()
    # Split on the newline too: the rule these two share names `.diff del` in its own selector.
    assert "text-decoration: underline" in screen.split("\n.diff ins {")[1].split("}")[0]
    assert "line-through" in screen.split("\n.diff del {")[1].split("}")[0]
    assert ".diff ins" not in printed


def test_the_modules_are_concatenated_in_cascade_order() -> None:
    """Faces, tokens, the shell, the pages, the page furniture, the evidence, other media.

    The package is seven `Final` strings joined in one place, so what can drift is the order
    they are joined in, and the order is a contract: a rule in a later module may rely on an
    earlier one and never the reverse. One selector from each module, in the order they must
    appear, is the cheapest way to hold it. The `@font-face` rules come first because they
    declare the families every later rule names, and print and forced colours come last
    because each overrides screen rules from every module before it.
    """
    assert STYLE.index("@font-face") < STYLE.index("--bg:")
    assert STYLE.index("--bg:") < STYLE.index("header.bar")
    assert STYLE.index("header.bar") < STYLE.index(".cardrow")
    assert STYLE.index(".cardrow") < STYLE.index(".timeline")
    assert STYLE.index(".timeline") < STYLE.index(".chg {")
    assert STYLE.index(".chg {") < STYLE.index("@media print")
    assert STYLE.index("@media print") < STYLE.index(_FORCED)


def test_the_three_shapes_of_a_disagreement_are_told_apart_without_a_hue_alone() -> None:
    """The badge is graded by border and fill, and all three keep the one alert colour.

    Measured 2026-09-18 over the palette redrawn that day: the one surface the grading
    introduces is the filled badge of the kind contradiction, `--alert` on `--alert-tint`, at
    7.93:1 light and 5.35:1 dark, a pair `_PAIRS` already checks. The other two shapes reach
    for no colour at all: a dashed border for a row with no text and the sheet's plain disputed
    pill for the evidenced one, which adds no rule.
    """
    assert ("alert", "alert-tint") in _PAIRS
    graded = [line for line in STYLE.splitlines() if line.startswith((".disp-", ".pill.disp"))]
    assert graded == [
        ".pill.disp { background: transparent; border-color: var(--alert); color: var(--alert); }",
        ".disp-none .pill.disp { border-style: dashed; }",
        ".disp-kind .pill.disp { background: var(--alert-tint); border-width: 2px; }",
    ]
    # The two grading rules reach for exactly one custom property between them, the alert's own
    # tint, so the grade is a fill and a border rather than a second hue.
    assert re.findall(r"var\((--[a-z-]+)\)", " ".join(graded[1:])) == ["--alert-tint"]


def test_the_link_and_the_alert_are_told_apart_by_colour_in_both_schemes() -> None:
    """A link and an alert that share a hue cannot be told apart by it, so they may not.

    The two sat 1.04:1 apart in both schemes until 2026-09-18, when the palette was redrawn and
    they became 1.64:1 light and 1.72:1 dark. Their separate tokens exist for this fact.
    """
    for scheme, palette in _palettes().items():
        ratio = contrast(palette["link"], palette["alert"])
        assert ratio >= _SEPARATION_MINIMUM, f"{scheme}: link against alert is {ratio:.2f}:1"


def test_a_row_gathered_with_no_text_is_opened_by_the_permalink_that_names_it() -> None:
    """A `§` that scrolled to a row a reader still could not read is a broken promise.

    The collapse is `display: none` on everything but the row's own heading, and `:target` is
    what a same-page permalink sets, so the link that names a row is the link that opens it,
    with no script and nothing dropped from the markup. Both halves are one rule each and both
    are asserted, because either alone is a row that cannot be read or a list that never
    collapsed.
    """
    assert ".quiet .chg > *:not(h3) { display: none; }" in STYLE
    assert ".quiet .chg:target > *:not(h3) { display: block; }" in STYLE
    assert STYLE.index(".quiet .chg > *") < STYLE.index(".quiet .chg:target > *")


def test_every_tint_a_word_already_says_is_stripped_for_print() -> None:
    """A background that costs ink and says nothing no word beside it says does not print.

    The blanket rule in the print block is one class deep, so every tint drawn by a selector
    of higher specificity has to be named there again or it survives on paper. That is why the
    two verbatim blocks, the insertion pill and a targeted change block are all listed, and it
    is why the filled badge of the kind contradiction is listed too: `.disp-kind .pill.disp`
    outranks `.pill` three simple selectors to one.
    """
    screen, printed = _print_block()
    assert ".disp-kind .pill.disp { background: var(--alert-tint); border-width: 2px; }" in screen
    for selector in (".verbatim.ins", ".verbatim.del", ".pill.ins", ".chg:target"):
        assert selector in printed, selector
    assert ".disp-kind .pill.disp { background: transparent; }" in printed


def test_forced_colours_keep_every_mark_that_was_drawn_as_a_background() -> None:
    """In forced colours a background-only mark vanishes, so the rail's nodes are redrawn.

    The timeline's node was a 7px background dot until 2026-09-18 and disappeared entirely under
    a high-contrast theme. The block now draws both rails' nodes in system colours the browser
    is told not to override, and every boundary that carries meaning in `CanvasText`.
    """
    _, _, forced = STYLE.partition(_FORCED)
    assert forced
    assert "forced-color-adjust: none" in forced
    for selector in (".timeline .event::before", ".chg.step::before", ".elided", ".pill"):
        assert selector in forced, selector
    assert "CanvasText" in forced


# ------------------------------------------------------------------ fonts


_FONT_URL = re.compile(r"url\(([^)]*)\)")
_FINGERPRINTED_FONT = re.compile(r"[a-z0-9-]+\.[0-9a-f]{8}\.woff2")


def test_the_sheet_reaches_no_third_party_and_loads_only_its_own_fonts() -> None:
    """The same promise `tests/site_/test_golden.py` makes over the written file.

    Asserted over the constant as well, because this is where a font import would be typed
    and a failure here names the module that grew it rather than a built artifact. Since
    2026-09-18 the sheet loads three self-hosted faces, so `url(` is allowed in exactly one
    form: a bare, relative, fingerprinted `.woff2` name that the build writes at the root beside
    the stylesheet. An absolute URL, a path climbing out, or any other file stays banned.
    """
    for banned in ("http://", "https://", "@import"):
        assert banned not in STYLE, banned
    named = _FONT_URL.findall(STYLE)
    assert named, "the sheet loads the self-hosted faces"
    for name in named:
        assert _FINGERPRINTED_FONT.fullmatch(name), name
    assert sorted(named) == sorted(FONTS.values())


def test_every_web_face_swaps_in_rather_than_hiding_the_text() -> None:
    """Text is readable before a face arrives, in the metric-matched fallback, never invisible."""
    faces = STYLE.split("@font-face {")[1:]
    loaded = [face.split("}")[0] for face in faces if "url(" in face.split("}")[0]]
    assert len(loaded) == len(FONTS)
    for face in loaded:
        assert "font-display: swap;" in face, face
    assert "font-synthesis: none;" in STYLE
