"""The shell and everything more than one page family needs: type, links, chrome.

Third in the cascade, after the faces and the tokens. What lives here is what a rule further
down is allowed to assume: the box model, the body face and its feature settings, the heading
scale, the shared small-print classes (`.muted`, `.small`, `.facts`, `.ident`, `.none`,
`.quoted`), each of which is minted by two or more of the page renderers. A class
one page owns lives with that page instead, in `pages`, `timeline` or `evidence`.

The body is the sans face with ligatures off and synthesis off: no two characters anywhere on
the site merge into one glyph, and no weight or slant the site does not load is faked. An
identifier is set in the same sans, smaller, with its slashed zero and tabular figures, which
is why the sheet needs no monospace face.

Three rules are about being usable rather than about looking a way, and one of the three is
not here:

- **The measure.** `main` holds its content to `--shell`, wide enough for the act page's two
  columns and for tables, but every paragraph is capped at `--measure`, so prose never runs
  the full width of a desktop window. The header and the footer paint the full width and pad
  their content in to the same shell.
- **The focus ring.** Every interactive element shows one, through `:focus-visible`, in the
  link colour, so a reader navigating by keyboard can see where they are. The site has no
  script that could restore one that the sheet removed.
- **Print and forced colours.** The rules are at the foot of `evidence`, the last module,
  because an override has to win the cascade against the screen rule it overrides and most of
  those are written after this module. What they do belongs to the shell all the same, so the
  reason they are not here is stated here.

The `#search` selectors are the script's contract with this sheet (`static/search.js` builds
`input`, `ul.results`, `li.active`, `span.ttl` and `span.kind` inside each row's link, `li.empty`
for a query that found nothing, and a `div.visually-hidden` inside `#search`); they are
restyled here and never renamed. `.visually-hidden` is written as a reusable class rather than
as a `#search` rule because what it does, keep an element in the accessibility tree and out of
the layout, belongs to no one page family.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["BASE"]

BASE: Final = """\
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 400 var(--text-body)/1.6 var(--sans);
  font-variant-ligatures: none;
  font-synthesis: none;
}
main { max-width: var(--shell); margin: 0 auto;
       padding: var(--space-5) var(--gutter) var(--space-6); }
h1, h2, h3, .display { font-family: var(--sans); font-weight: 600; color: var(--fg); }
h1 { font-size: var(--text-h1); line-height: 1.08; letter-spacing: -.018em;
     margin: 0 0 var(--space-3); }
h2 { font-size: var(--text-h2); line-height: 1.2; letter-spacing: -.01em;
     margin: var(--space-5) 0 var(--space-3); }
h3 { font-size: var(--text-h3); line-height: 1.3; margin: 0 0 var(--space-2); }
p, ul, ol { margin: 0 0 var(--space-3); }
p { max-width: var(--measure); }
a { color: var(--link); text-decoration-thickness: 1px; text-underline-offset: .18em; }
a:hover { text-decoration-thickness: 2px; }
:focus-visible { outline: 3px solid var(--link); outline-offset: 2px; border-radius: 2px; }
strong { font-weight: 600; }
/* Identifiers are set in the sans with its slashed zero rather than in a monospace face, and
   every figure a reader compares down a column is tabular. */
time, .date, .mag, code, .id { font-variant-numeric: tabular-nums lining-nums; }
code, .id {
  font-family: var(--sans);
  font-size: var(--text-code);
  font-feature-settings: "zero" 1;
  color: var(--muted);
  letter-spacing: .01em;
  overflow-wrap: anywhere;
}
.lede { max-width: var(--measure); font-size: var(--text-body); }
.muted { color: var(--muted); }
.small { font-size: var(--text-meta); line-height: 1.5; }
/* A proper noun carrying a hyphen, kept off the line break that would read as two words. */
.nowrap { white-space: nowrap; }
.scroll { overflow-x: auto; }
.facts { margin: var(--space-1) 0 var(--space-3); font-size: var(--text-meta); line-height: 1.55;
         color: var(--muted); }
.ident { font-size: var(--text-meta); color: var(--muted); }
.quoted { color: var(--muted); }
.none { color: var(--muted); }
/* A link that leaves the site says so with a drawn arrow; its words for a screen reader are
   in the markup (`outbound.py`). A drawn glyph is also read out unless its alternative text is
   empty (`/ ""`); each is declared twice, so a browser without that syntax keeps the glyph. */
.ext { white-space: nowrap; }
.ext::after { content: "\\2197"; content: "\\2197" / ""; display: inline-block;
              margin-left: .12em; font-size: .85em;
              text-decoration: none; }
/* A direction arrow beside a link's words is drawn here, silent in the same way, so the link's
   accessible name is its words alone. The no-break space keeps the underline unbroken and the
   arrow on its words' line. */
.go::after { content: "\\00a0\\2192"; content: "\\00a0\\2192" / ""; }
.back::before { content: "\\2190\\00a0"; content: "\\2190\\00a0" / ""; }
.up::before { content: "\\2191\\00a0"; content: "\\2191\\00a0" / ""; }
.up-after::after { content: "\\00a0\\2191"; content: "\\00a0\\2191" / ""; }
/* Off-screen until it takes focus, then placed over the header rather than moving it, so
   arriving at the page shifts nothing. It is the first focusable element on every page. */
.skip {
  position: absolute;
  left: var(--space-3);
  top: var(--space-3);
  z-index: 30;
  padding: var(--space-2) var(--space-3);
  background: var(--panel);
  color: var(--link);
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  font-size: var(--text-meta);
  transform: translateY(-300%);
}
.skip:focus { transform: none; }
/* Read aloud and never drawn: the search control's result count lives here. Clipped rather
   than hidden, because `display: none` and `visibility: hidden` take it out of the
   accessibility tree, which is the one place it exists to be. */
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}
/* The header and the footer paint the full width and hold their content to the shell, so a
   wide screen shows no empty margins beside them. */
header.bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-4);
  padding: var(--space-3) max(var(--gutter), calc((100% - var(--shell)) / 2 + var(--gutter)));
  border-bottom: 1px solid var(--rule);
  background: var(--bg);
}
.wordmark { font-weight: 600; font-size: var(--text-explain); letter-spacing: -.02em;
            color: var(--fg); text-decoration: none; margin-right: var(--space-2); }
.wordmark:hover { color: var(--link); }
header.bar nav { display: flex; flex-wrap: wrap; gap: 0 var(--space-4); flex: 1 1 auto; }
header.bar nav a { color: var(--fg); text-decoration: none; font-size: var(--text-meta);
                   padding: .7rem 0; border-bottom: 2px solid transparent; }
header.bar nav a:hover { color: var(--link); border-bottom-color: currentColor; }
/* It does not grow: a search box that takes half of a wide header reads as the page's main
   business, and it is a shortcut past navigation that already works. */
#search { position: relative; flex: 0 1 20rem; min-width: 12rem; margin-left: auto; }
/* A form control's boundary is the information, so it is `--edge`, at 3:1 or better. */
#search input {
  width: 100%;
  padding: .55rem .75rem;
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--fg);
  font: 400 var(--text-meta)/1.4 var(--sans);
}
#search input::placeholder { color: var(--muted); opacity: 1; }
#search .results {
  position: absolute;
  z-index: 20;
  top: calc(100% + .25rem);
  left: 0;
  right: 0;
  max-height: 60vh;
  overflow-y: auto;
  margin: 0;
  padding: var(--space-1) 0;
  list-style: none;
  background: var(--panel);
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  font-size: var(--text-meta);
}
#search .results:empty { display: none; }
/* The label and the kind share the first line; a provision's title, where it has one, takes a
   line of its own under both. */
#search .results a { display: grid; grid-template-columns: minmax(0, 1fr) auto;
                     align-items: baseline; gap: 0 var(--space-3); padding: .45rem .75rem;
                     color: var(--fg); text-decoration: none; }
/* One declaration for three states, so the row the arrow keys highlight and the row the
   pointer is over cannot come to look different from each other. */
#search .results a:hover, #search .results a:focus,
#search .results li.active a { background: var(--mark); }
/* What kind of thing a result is, said once at the end of the row rather than under it. */
#search .results .kind { grid-area: 1 / 2; font-size: var(--text-label); font-weight: 600;
                        color: var(--muted); }
/* Cut to one line by the sheet only: the whole title stays in the row's accessible name. */
#search .results .ttl { grid-area: 2 / 1 / 3 / -1; overflow: hidden; white-space: nowrap;
                       text-overflow: ellipsis; color: var(--muted); line-height: 1.35; }
/* A query that found nothing says so in the panel, as a row that is not an option. */
#search .results .empty { padding: .45rem .75rem; color: var(--muted); }
/* How far in the phone nav row's start fade reaches: 0 at rest, grown by scrolling below.
   Registered as a length so the scroll timeline interpolates it rather than flipping it. */
@property --fade-start { syntax: "<length>"; inherits: false; initial-value: 0px; }
/* A phone gets two rows: the wordmark with the navigation beside it, then the search box
   across the width rather than the sliver left beside the links. The header stays under a
   sixth of the screen, and every link stays in the markup and on screen, never in a menu. */
@media (max-width: 40rem) {
  header.bar { gap: var(--space-2); padding-top: var(--space-1); padding-bottom: var(--space-2); }
  .wordmark { flex: none; }
  /* One row that scrolls sideways to the screen's edge, faded at its end so the cut reads as
     more to come. The fade is a fixed 2.5rem and the row's end padding as wide, so the last
     link scrolls clear of it at full contrast. A scroll box clips a focus ring, so the row
     keeps 5px of room on the other three sides and gives it back in margin. */
  header.bar nav {
    flex: 1 1 0; min-width: 0; flex-wrap: nowrap; overflow-x: auto; gap: 0 var(--space-3);
    scrollbar-width: none; margin: -5px calc(-1 * var(--gutter)) -5px -5px;
    padding: 5px 2.5rem 5px 5px;
    mask-image: linear-gradient(to right, transparent 0, black var(--fade-start, 0px),
                                black calc(100% - 2.5rem), transparent);
  }
  /* Once scrolled, the row fades at its start as well, so the cut there reads as more behind.
     Where scroll timelines are unsupported the start stop stays at 0 and only the end fades. */
  @supports (animation-timeline: scroll()) {
    header.bar nav { animation: nav-fade-start linear both;
                     animation-timeline: scroll(self inline); animation-range: 0 2.5rem; }
    @keyframes nav-fade-start { to { --fade-start: 2.5rem; } }
  }
  header.bar nav a { white-space: nowrap; padding: .75rem 0; }
  #search { flex: 1 1 100%; margin-left: 0; }
}
footer {
  padding: var(--space-5) max(var(--gutter), calc((100% - var(--shell)) / 2 + var(--gutter)))
    var(--space-6);
  border-top: 1px solid var(--rule);
  color: var(--muted);
  font-size: var(--text-meta);
  line-height: 1.55;
}
footer p { max-width: 62ch; }
/* The not-legal-advice notice: its own surface, an `--edge` boundary and a drawn `!` in the
   text colour, and the only block on the site that looks like it. */
.disclaimer {
  position: relative;
  max-width: 62ch;
  margin: 0 0 var(--space-4);
  padding: var(--space-3) var(--space-3) var(--space-3) 3.25rem;
  background: var(--notice);
  color: var(--fg);
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  font-size: var(--text-meta);
  line-height: 1.55;
}
.disclaimer::before {
  content: "!";
  position: absolute;
  left: var(--space-3);
  top: var(--space-3);
  width: 1.4rem;
  height: 1.4rem;
  border: 2px solid var(--fg);
  border-radius: 50%;
  font-weight: 600;
  line-height: 1.2rem;
  text-align: center;
}
"""
