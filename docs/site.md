# The site: a static reference tool, no backend, one script

What `emendrix site build` writes, what it deliberately does not write, and which flags decide
whether the absolute-address layer exists at all. Start at [`../README.md`](../README.md) for how
to run it; the artifacts it renders are described in [`./output-format.md`](./output-format.md).

```bash
uv run emendrix site build --out site/ \
    --changelogs ~/regulatory-changelog \
    --site-url https://changes.example.invalid \
    --repo-url https://example.invalid/emendrix \
    --changelogs-url https://data.example.invalid/changelogs
```

A directory of files, not a page:

```
index.html            search, the latest versions, and the one measured claim after them
404.html              the page a mistyped address gets, with a way back
acts/index.html       every watched act, by the sector the watchlist gives it, with a jump list
acts/<celex>/         one page per act: the whole watched history, newest first, as cards
acts/<celex>/<key>/   one page per version: its masthead, the changes and the verbatim text
acts/<celex>/<prov>/  one page per touched provision: its history, newest first
amendments/           every amending act a committed event names, newest first, grouped by year
amendments/<celex>/   one page per amending act: every watched act it amended, and what it moved
dates/                every date in the amended texts that has not arrived yet, by sector, nearest first
about/                who runs the site, how current the corpus is, and what it does here
methodology/          the metrics table with its caveats, the loop, the glossary of the site's words
feeds/                what the feeds are and where they are, by sector
feeds/all.xml         every amendment event, as Atom
feeds/<celex>.xml     one act's events, for a reader who watches only that act
robots.txt            what crawlers may read, and where the sitemap index is
sitemap.xml           every page, with the date its content last moved
sitemap_index.xml     the one address a search engine is given, naming the sitemap
search-index.json     act and instrument names, aliases, CELEX numbers and touched provisions
search.<digest>.js    the one script; style.<digest>.css is the one stylesheet
sans-400.<digest>.woff2, sans-600.<digest>.woff2, serif-400.<digest>.woff2
                      the three self-hosted faces the stylesheet loads
icon.svg              the favicon; og.png is the link-preview card
```

**The stylesheet, the script and the three font files carry a digest of their own bytes in
their names**, and that is a caching decision.
An edge that gives an asset a one-day lifetime will happily serve yesterday's stylesheet beside
today's pages, which is what the live site did on 2026-09-04: the edge held 14 424 bytes of CSS
where the origin had 22 056, so a layout that had shipped was invisible until somebody purged
the cache by hand. A name that moves with the content makes that unrepresentable: a build that
changes the bytes writes a new URL and a build that does not leaves the URL alone, so an asset
may be cached for as long as the edge likes and no deploy needs a purge.

The other three keep fixed names on purpose. `search-index.json` changes on every build and is
served with the short lifetime the pages carry, and the script fetches it by a path relative to
the site root. `icon.svg` and `og.png` are identity rather than code: a link-preview image whose
address moves breaks the card every social site has already cached for the pages that name it.
**They are the one part of the tree that still needs a manual purge**, so an operator who
changes either should purge that one path at the edge and expect previews to refresh slowly.

The builder writes its own files and deletes nothing, so a rebuild into a directory a previous
build wrote leaves the previous stylesheet, script and fonts beside the new ones: a few unreferenced
kilobytes, harmless, and useful for the seconds in which a reader is still loading a page that
names them. Sweep them whenever the directory is worth tidying, or let a deployment that
replaces the directory whole do it.

**The fonts are the site's own files, and so the no-third-party promise holds.** Two open-licence
families, chosen on 2026-09-18, subset to the characters the corpus and the site use and committed
as WOFF2 under `src/emendrix/site_/static/fonts/`, beside their SIL Open Font License 1.1 texts
and a README naming each upstream file by release, URL and SHA-256. `scripts/subset_fonts.py`
regenerates them from those upstream files and refuses one whose hash differs; the build copies
the committed bytes and subsets nothing. The serif (Source Serif 4, renamed "Emendrix Serif" as
the licence requires of a modified copy) is only ever the law's own words: official titles,
provision text and diffs. The sans (IBM Plex Sans, renamed "Emendrix Sans") is always the site
speaking. Three files, 66,268 bytes, against a budget of 180 KB and four files that a test holds.
The stylesheet loads each by a bare relative `url()`, which resolves against the stylesheet at the
root, so the tree still works from a subpath and from `file://`; a server's content security
policy has to allow `font-src 'self'` for them. Every face swaps in over a metric-matched system
fallback, so text is readable before a font arrives and wherever one is refused. Firefox refuses a
font file above the page's own directory under `file://`, so a local copy opened there reads in the
fallback below the root, which keeps the layout.

**Colour is spent semantically and nowhere else**, and every colour is a lower-case `#rrggbb`
token declared in both schemes in `style/tokens.py`, which a test enforces by computing WCAG 2.1
contrast over every pair the sheet paints: 4.5:1 for text and 3:1 for a component boundary, in
both schemes. The families are the ground and its text, the two diff tints, one hue for links and
one kept visibly apart from it for an alert, one colour per kind of change with a neutral pair
for provenance, and one colour per page type. Colour never carries a meaning alone: an insertion
is also underlined and a deletion struck through, and a word, a glyph or a border style always
says what a colour says. `scripts/make_og_image.py` and `static/icon.svg` copy a few of the light
values by hand and move in the same commit as they do.

Four things about that tree are not visible in the listing. Every page states its own canonical
address, so the two ways a static host serves one page, with and without the `index.html`, do not
read as two pages. Every page advertises the feeds that cover it in its `<head>`, so a reader's
feed reader finds them from a visit rather than from the feeds page. `sitemap.xml`, `sitemap_index.xml` and
that whole head block, canonical, Open Graph, Twitter card and JSON-LD alike, need an absolute
address and are omitted entirely without `--site-url`, which is the rule the feeds already follow;
`robots.txt` and the favicon link need no base and are written either way, so the only thing
`robots.txt` loses is its `Sitemap:` line. That line names the index rather than the sitemap, and
the index names the sitemap: one address for a search engine to keep, behind which the sitemap may
be split or renamed without the submitted address moving. And every `<lastmod>` comes from the
corpus, an act's newest event or the report's run date, never from the build clock, so a rebuild
that changed nothing tells a crawler nothing changed, and an act nothing has happened to yet
carries no `<lastmod>` at all rather than a guessed one.

No `<lastmod>` is ever later than the date the build was made for. An act's newest event is dated
by the day its changes take effect, and a consolidation is routinely notified before it applies,
so the corpus can hand the sitemap a date that has not arrived. A page's content cannot have moved
after the build that wrote it, so such a date is left out and the newest date the build can stand
behind is published instead; where a page has none, it carries no `<lastmod>`, which is the answer
a quiet act already gets. Clamping to the build date would be worse than omitting: it would stamp
every affected URL with the one value this file refuses to put in a `<lastmod>`.

The evidence is on the site rather than behind a link out of it, one page per version. An act's
own page is the timeline: a version card per version, headed by the version's name as its one
link, carrying the anchor every feed entry was published under. That split is a weight decision: an act's history is
unbounded and one backfilled act served 6.1 MB as a single page, where an event is bounded by
one consolidation. The event page lists the provision changes with the sentences that survived
the citation gate, and each change opens onto the before and after text in full: a **unified
word diff** computed at build time by
`difflib.SequenceMatcher` over whitespace-split tokens, with deleted and inserted spans marked in
place. Below a similarity of 0.5 the texts are shown stacked instead, labelled as too different
to diff inline, because an inline rendering of a rewrite is noise wearing the clothes of a
comparison. The stored text is never touched: the diff is a comparison-time rendering, the same
category as the whitespace handling inside the comparison functions.

Every change, and the index entry that points at it, carries a figure such as `+1,204
−318`, opening the facts line under the change's heading on an event page: the characters the comparison below it marked inserted and deleted, or for a provision
compared line by line the characters in the lines that changed. It is measured on that one
comparison rather than computed again, it is labelled `characters` wherever it is totalled, and
it is **not a measure of legal effect**, which the methodology page states in full; the index
gives each link a weight by decade of characters so a page of forty-five changes shows where
the text actually moved.

An event of six changes or more opens with an index of the provisions it touched, and from
60rem wide that index is a sticky column beside the changes rather than a block above them, so a
reader forty blocks down can still see the map. Narrower than that it is a grid of coordinates,
each marked by its kind's glyph (`+` inserted, `−` deleted, `#` renumbered, `»` deferred,
unmarked for modified) with the kind's words kept in the accessibility tree at no size, which
costs a few lines where a column would cost a screen.

**Long pages keep their place.** `INDEX_ABOVE` in `pages/event_index.py` is the one threshold
for every device a long version page carries, so a page never has half of them: the index, with
`id="changes-index"`; a context bar under the version's masthead (`pages/context_bar.py`),
one line naming the act as a link to its page, the version by its name and `Index`, pinned to
the top of the screen with `position: sticky` as the page scrolls; an `Index` link closing
every change, gathered rows with no text included, where it shows when the row opens; and
`Back to top` at the foot, each with its arrow drawn by the sheet. The bar is a `<div>` holding a `<p>`, not a landmark, since the
page already names four, and it follows the masthead in the markup so a keyboard reader meets it
once. Nothing scrolls under it: the page's `scroll-padding-top` is the bar's height wherever the
bar exists, so a fragment link and a link reached by the keyboard both land below it, and the
sticky index column starts below it too. The bar and every `Index` link are hidden in print. All of
it is CSS; the site's one script is still search. From one to five changes the page carries
none of these; its masthead names the changes on one line instead, so every page with changes
maps them near its top, and zero prints neither.

Every change heading, on an event page and on a
provision page alike, ends with a `§` permalink to that change's own anchor, which is the
anchor both pages already publish. Its accessible name is `Link to this change`, and a `title`
carrying the same words says what the symbol is to a sighted reader on hover. The citations a change's sentences carry are printed once
for the change, in first-mention order and deduplicated by the pair of address and label,
rather than after every sentence: a change whose sentences all cite the same before-and-after
pair used to print that pair once per sentence. **This is a rendering decision and nothing
below the page moves**: the committed Markdown and JSON keep every citation on the sentence
that carried it, which is the form the citation gate resolves and the eval harness counts.

The same changes are published a second way, under the provision. `acts/<celex>/<prov>/` is one
coordinate's whole history, newest first: a step per event that touched it, each with the date
and its clock, linked to that version's page, the change type, the instrument that made it, the
applies-from line and the sentences that survived the gate. The path segment is the slug of the canonical location string
(`ar-6`, `an-xvii`, and `an` or `tit` for a change keyed to a whole annex or title), never a
human reading of it, because a second numbering for one coordinate is a second thing to keep in
step and the corpus writes both `AN 4` and `AN IV`. **The newest step carries its verbatim text
in full and every older step links the block on the event page that holds its own**: one
committed change carries 4.1 million characters of before-and-after text and one coordinate has
been touched by 47 events, so a page repeating the evidence per step would multiply the heaviest
page on the site by its own history. The step ids are the anchors the event pages already
publish, so nothing addressable moved when these pages arrived.

Where a change moved a machine-readable date, the event page and the provision page print those
dates under its applies-from line: the dates its new text names and the ones its old text named,
in the ISO form, as the parser read them off the source's own date markup and never as a reading
of what any of them governs. The act's own page gathers every one of them under **Dates the
amended text names**, sorted by the date rather than by the event, each row linking the
provision's page and the change block that moved it, and folded behind a summary above twelve
rows. It is a list of dates the text contains and never a schedule: whether a provision applies
from one of them is stated for each change under "applies from" and nowhere else, which is the
line the section's own lede points at.

Every event that does name an amending act says which one, on every surface it appears on: the
version page's `<title>`, its description and its masthead, the act page's version card, the
front page's card, the acts index row's date fact and the Atom entry's title and summary. The
name is, in order, the short name the watchlist declares under `[[amending_acts]]`, the official
number rendered from the CELEX by the numbering convention in force for its year
(`Regulation (EU) 2020/561`, `Directive (EU) 2015/2366`), and the key itself; the reading happens
at the CLI boundary, which is the one place in the site generator allowed to know what a CELEX
is. **An amending act is named one way and goes one place**: `Made by X` on a version and
`Amended by X` on a provision's step both link X's page on this site, the key follows as a small
identifier, and EUR-Lex follows that as a secondary link. Every link to EUR-Lex on the site,
these, the one on an amending act's own page, an act's and a provision history's own and the
disclaimer's, is written by `site_/outbound.py`, drawn with an arrow by the sheet and announced
to a screen reader as external, so none can look like an internal one. The arrow carries empty
alternative text, as every glyph the sheet draws in place of a word does, so it is not read out
after the words that already say it. **No link's words carry an arrow either.** `Previous
version`, `Next version`, `Index`, `Back to top`, `What these mean` and the other links that
point somewhere with an arrow get it from a class in the sheet (`.go`, `.back`, `.up`,
`.up-after`), drawn beside the words with empty alternative text, so a screen reader names the
link by its words alone; `tests/site_/test_vocabulary.py` asserts that no link's text in the
golden tree holds `←`, `→`, `↑` or `↗`. The `→` between two version codes is meaning and sits
outside any link. Where a committed document
recorded the amending act's official title, the version's masthead prints it verbatim as its
lede and the version card prints it uncut under the line. None of it is authored: a label is a
label, a number is mechanical and reversible, and a title is the corpus's own words.

Each named instrument also has a page of its own under `/amendments/<celex>/`, addressed by the
key the corpus published and never by a year-and-number reading of it, and every event page
links it. It gathers what the event pages already carry, under the instrument instead of under
the act: every watched act the instrument amended as an H2, the version card of each version it
made there as an H3 under it, and under each card the coordinates that version's changes
attribute to that instrument and to no other, because one consolidation can fold several
instruments and crediting each of them with all of the work would be a claim the corpus did not
make. A card on that page does not say `Made by` the act the page is about, and still names any
other amending act the version folded in. Where an instrument moved more than one watched act,
the version page names the others beside the link. `/amendments/` is
the roster of every instrument a committed event names, newest first by the newest event each
produced and grouped under the year of that date; an instrument the watchlist names a short
name for and no event names gets no row and no page, a declared label not being evidence that
anything happened. Every version page also carries the versions either side of it in its own
act's history, as `← Previous version` and `Next version →` with each date under it, at the top
of the page and again at its foot, as two landmarks named apart. The previous version is the
older one and carries `rel="prev"`, the timeline running newest first.

## A version: its masthead, its card, its tags

A version appears in two places and is drawn two ways. **On its own page it has a masthead**
(`pages/version_masthead.py`), under the page's H1 and before its changes, in the version's band.
A version with one to five changes, too few for the in-page index, opens it with a line naming
them (`pages/version_changes.py`): `Changes: Annex II · SUBSTANCES OR PRODUCTS CAUSING ALLERGIES
OR INTOLERANCES`, each coordinate a link to its block on the anchor the page already computed,
its title after it outside the link, in the entry's own order. On a phone the amending act's
official title can fill the first screen, and this line is what says there what changed. It is a
landmark, `Changes in this version`, the name the index carries, since a page has one or the
other and never both. Then `Made by` the amending act, its official title as a readable serif lede, a status sentence
placing the version in its act's history (`Version 5 of 5 recorded for FIC Regulation, the
newest.`), a dates line that states the clock the heading did not name (`First seen by emendrix
on 4 September 2026, …; that is not a legal date.`, or `In force date not stated.`), the tally,
and, small and secondary, the two consolidated versions with `v1` and `v2` named once. Where a
version the page names is coded with a date other than its in-force date (the FIC version coded
20180101 is in force from 31 December 2015), a note under the codes says what the code's date
is; the coded date is the one the composition root resolved, never read out of the code by a
page. Then the `What changed` H2 opens the changes, so
the page's outline reads version, what changed, each change. **In a list it is a card**
(`pages/version_card.py`): the version's name as its one link, `Made by` and the official title,
the tally without the per-shape tags, and the identifiers. The act's timeline sets the cards as
H2 under a `Versions, newest first` H2; an amending act's page sets them as H3 under each act's
H2. The two share the helpers that read the document's facts and never their markup, and the
card keeps `id="{entry.key}"` on the act page, which every feed `<id>` points at.

**A tally is a total and a few tags** (`site_/tags.py`). The total is always printed: `1 change
in this version`, or the sentence for a version that touched nothing or has no text to show.
Then only the categories present, each a `<span class="tag tag--{kind}">` that counts itself:
`2 substantive`, `6 dates only`, `1 without text`, `3 where sources differ`, and on the
version's own page one tag per shape the disagreements take (`Not in every list`, `No text
found`, `Kinds differ`), then `1 without an explanation`, `2 quoted verbatim`, or one of `All
explained` and `No explanations for this version`. A tag is an adjective, never a link, with one
look per kind everywhere. A category with a count of zero is not printed: what a row of zeros
once guaranteed is kept by printing the total always and the sources-differ tag whenever its
count is not zero. Every number is the committed document's own. One link follows the tags,
`What these mean →`, to the glossary.

**No page says "disputed".** It is the stored field's name and correct in the JSON, the metrics,
the code and the committed changelog's Markdown, but on a page with a not-legal-advice
disclaimer a newcomer reads it as a claim about the law, where it is a claim about emendrix's
three sources. Pages say **sources differ**, and never `disputed`, `contested` or `conflict`,
in any visible text or `<title>`; `tests/site_/test_vocabulary.py` asserts it over the golden
tree and the scale tree. **One stated exception**: the methodology page's measured table keeps
its row `Disputed changes (signals disagree)`, label and meaning, because both are rendered from
the evaluation report's own metric rows that the README's published table shares. The glossary
says that row counts the same thing without printing the word again. The one stored reason the
explain stage records for a change with no text names the stored word, so the site prints that
reason in its own words; every other stored reason is printed as written.

## One change: its heading, where its sources differ, and who is speaking

A change block (`pages/act_event.py`, and the step of a provision page, `pages/provision.py`,
both through `pages/prose.py`) is read in this order:

- **The heading leads with what a reader scans for**: the coordinate, linked to its provision's
  history, then the provision's title, then the kind of change as a tag in sentence case
  (`Modified`, `Inserted`, `Deleted`, `Renumbered`, `Deferred`), each kind with its own colour
  and a glyph or border style, then the `§` permalink. A screen reader names it `Art. 1 Subject
  matter, Modified`. A provision step's heading is the version's name, linked to the version's
  page, then the tag, then the characters on the newest step only.
- **The provision's title** is decided once, in `subject.py`, for all four places a coordinate
  is printed with its title: this heading, the provision page's H1, the version's in-page index
  and the act page's index. It is the stored heading where that says more than the coordinate
  (the comparison folds case and whitespace). An annex whose stored heading is only its
  coordinate, `ANNEX II`, is titled from the first line of its own text under a stated rule:
  the text's first line must be the annex's title, and its second is taken only if it is 1 to
  200 characters, holds no lower-case letter and a run of three letters, opens with no
  numbering token and does not open with `CHAPTER`, `PART`, `SECTION`, `SUBSECTION`, `TITLE`,
  `ANNEX`, `APPENDIX`, `FOREWORD`, `CONTENTS`, `TABLE`, `INTRODUCTION` or `ENTRY`. When the
  rule is unsure it says nothing and the coordinate stands alone. The rule reads committed
  text, so it serves changelogs already published, and `tests/site_/test_subject.py` pins its
  measurement over the committed Formex packages: on 2026-09-19 it read 18 subjects, all 18
  agreeing with the XML's own structure, and none wrong. A title is printed character for
  character; one with no lower-case letter carries `ttl--caps`, which the sheet sets in small
  capitals so it does not shout, and the letters in the markup stay the law's.
- **A facts line**: on a version page the characters that moved, then `Applies from:` with a
  date, `no date changed` (the changelog's `unchanged` read as "the provision did not change")
  or `not readable` with its reason and a `why` link to `#applies-from`.
- **Where the sources differ**, the shape's tag with a small `What this means` link beside it to
  `methodology/#sources-differ` (the tag itself is never a link), then the lead and the detail.
  Three shapes, each with its own tag, lead and weight:

  | Shape | Tag | Lead | Weight |
  |---|---|---|---|
  | found in the text, another source did not list it | `Not in every list` | `Found in the text, but not every source lists it` | neutral provenance |
  | named by a source, no text to show | `No text found` | `A source lists it, but there is no text to show` | neutral provenance, dashed |
  | the sources named different kinds | `Kinds differ` | `The sources name different kinds of change` | the alert colour, `≠`, double border |

  Only the contradiction takes the alert colour: most changes where sources differ are the first
  shape, and an alarm on each of them made the whole site read as unreliable. The block carries
  the shape as a class, `differ-text`, `differ-none` or `differ-kind`, on the version page and on
  a provision step alike, so one change is graded one way wherever it is shown.
- **Two registers.** The model's sentences sit under a label, `Explanation, written by a model
  and checked against the cited text`, in the sans at the largest size on the block, behind a
  rule. The citations follow once, and where a label in them names `v1` or `v2` the line under
  them says `v1 is the previous version, v2 this one.` The law's words are behind a `<details>`
  whose summary reads `Text from EUR-Lex, before and after` (`Text from EUR-Lex` for one side):
  the serif, on a panel, held to the legal measure. **Its sides are named** above the text,
  `Previous version, in force 31 December 2015` and `this version, in force 1 April 2025`, each
  with its consolidation code beside it as a small identifier, and marked with the `−`/`+` and
  tint the text below uses; a one-sided change reads `Inserted in this version` or `Deleted in
  this version, from`. The previous version is dated by the recorded version that produced it,
  and named by its role alone where none did. On a version of fewer than six changes the text is
  open; a longer version, which has an index, keeps it closed.

**The glossary** is the last section of the methodology page, `Words this site uses`, at
`methodology/#glossary`, with an `id` on every term (`#sources-differ`, `#dates-only`,
`#first-seen`, …). Every tag kind the site prints maps to one of its terms, and a test holds the
two together. Every other heading on that page carries an `id` too: `#corpus`, `#measured`,
`#how-it-works`, `#built`.

`/dates/` is the one forward-looking page on the site. Everything else here is a record of
what has already happened; this gathers, across every watched act, the dates an amendment added
to or removed from a provision's text that fall after the date the build was made for, nearest
first, each row linking the provision's own history and the change block that moved the date.

The list is gathered by sector first and by year second, because a reader usually arrives
asking what their own sector's texts name. A sector is the watchlist's `domain`, grouped and
ordered by `sectors.py`, the one grouping the acts roster uses, so `Other` comes last on both
pages and an act never sits in two different places. A jump list of the sectors that have rows
opens the list, each with its number of rows, and each sector heading carries the id
`dates-{anchor}`, prefixed so it never collides with the roster's bare sector ids. Inside a
sector the rows keep their date order, one heading per year present, and each row is the same
sentence it always was. The order of the page is the lede first, which says what the list is and
is not, then the applies-from block, then the list, then the coverage panel `What this is a view
of`, which carries the build date and the reasons no applies-from date could be read as well as
the counts below. Content first and diagnostics after it; nothing was cut to get there.

A year heading more than a hundred years after the build year (`dates_list.FAR_YEARS`) reads,
for example, `2404 as the source's date markup reads it`, the qualifier linking the panel's
sentence that states the range of readings (`#date-range`). The row stays under its own year
and is counted like any other: a reading that far out is not a plausible date on its face, so
the heading says whose reading it is rather than letting it stand as a claim about that year,
and nothing is bucketed, clipped or folded.

Its whole design is a line that must not be crossed. `dates_added` and `dates_removed` are a
set difference over the source's own `<DATE ISO>` markup inside one provision, so the page knows
that a date appeared in the text and nothing at all about what the sentence around it does: the
corpus holds restriction-table cut-offs, one half of a written range, and prohibition dates in
an annex column, in that one field. *A date was added to this provision's text* is strictly
weaker than *this provision applies from that date*, and only the weaker claim is in the data.
The stronger one exists in exactly one field, `applies_from`, and it resolves for well under one
change in a hundred. So the two are two blocks with two headings rather than one list with a
caveat, the phrase "applies from" appears only in the block that is clock 2's own answer and in
the sentence pointing a reader at the applies line on a change, and a test refuses the page if
the word `deadline`, `obligation`, `requirement`, `schedule` or a dozen others like them ever
reaches it. There is no countdown, no highlighting of the nearest date and no grouping of
unrelated acts under a shared calendar day: two drafting teams reaching for the end of a year is
a coincidence, and a row that gathered them would assert a relationship the corpus does not hold.

Two things on it are counted rather than assumed. A date one amendment put into a provision and
a later one took back out is the one row a straightforward list renders wrongly, so each row
carries whatever later committed change of the same act removed that date from that provision,
and says exactly that. And the panel under the list opens the corpus's own coverage, so a reader
does not take the list for a complete one: how many committed changes moved no machine-readable
date at all, how `applies_from` answered across all of them with its stated reasons in the
corpus's own words, how many mentions are already behind, how many acts have nothing ahead, and
the two ends of the range the date markup produced, shown as read rather than clipped. Every one of those numbers is
counted at build time; none is typed into the page. What has already passed is folded to the
last ninety days, with the remainder counted and the route to it given, because each act's own
page carries its complete list in full.

"Ahead" means later than the date the build was made for, which arrives on the command line as
`--generated-on` and is the same date the footer prints on every page. Nothing under the render
path reads a clock, so two builds of one changelog repository on one date produce identical
bytes, and a build made on another day divides the list at another date, which the lede says.
The page carries no `<lastmod>` in the sitemap for the same reason `/about/` carries none: its
content moves with the build rather than with the corpus.

The roster page says what it covers before it lists anything. The lede counts the acts and
then says what kinds they are, in words the composition root chose from each CELEX's descriptor
(`Regulation`, `Directive`, `Decision`, and any other descriptor as its own letter), because
"67 acts" says nothing about whether the act a reader came for could be here at all. Under it
sits one fixed paragraph: every act is watched in its English text, no Directive is on the
watchlist, and a consolidated version with no English text is recorded as such rather than
translated. It is printed **only while the roster's own kinds make it true**, so the day a
Directive is watched the sentence goes rather than becoming the site being wrong about itself,
and the about page prints the same constant in "What it is not" so the two cannot drift. Each
domain heading carries an id, which is what an act page's neighbours line links to.

An act with no recorded event gets a page of facts rather than a page of apology. It carries the
act's identifiers and its domain, its own Atom feed, a link to the act **as published** on
EUR-Lex, the other watched acts the watchlist puts in its group, and one sentence saying what an
empty timeline means: no transition between two versions of it is in the changelog this site is
built from. **There is no date in it, because the site has none**: when an act was last checked
lives in the poller's own state file and reaches no committed artifact, and `emendrix backfill`
can still write an older transition tomorrow, so an empty timeline is a fact about the record and
never about time. The two EUR-Lex links are labelled apart, "on EUR-Lex" for the newest
consolidated version and "as published, on EUR-Lex" for the act as the Official Journal published
it, because they are two different documents: a page shows the consolidated one where an event
resolved one and the published one otherwise, which is the only one an act nothing has happened
to can have. Every act page with at least one neighbour in its domain closes its header with
them, up to six by name and then a link to the group on the roster; a domain is the watchlist's
label, so nothing there is inferred.

Some committed events name no amending act at all: their corroboration window turned up no
modification annotations and no amending-act instructions, so only the text comparison observed
them. The commonest shape is the act as published set against its own first consolidation, where
no amending act can exist yet. The site derives the class at build time from the committed
document's own fields (`site_/attribution.py`) and says the fact rather than a cause: the front
page leaves these events out of "Latest versions" and counts the exclusion in words, the acts
index counts them apart from the versions naming an amending act and never answers a date fact with one, the act
page keeps every one in place under the label "no amending act named" with one sentence saying
what it means, and the feeds keep every one with the same fact leading the summary. Nothing is
dropped: the difference in the published text is real and stays shown; what the pipeline did not
establish is which act, if any, caused it, and no page claims more than that.

## Every page says what it is and where it sits

A reader who lands cold from a search result or a feed on a deep page has, until the page tells
them, no idea whether they are looking at an act, one version of it or one provision's history.
So **every page below home opens with a masthead**, `<header class="masthead masthead--{kind}">`
inside `<main>`, holding three things in order: a breadcrumb, a caption naming the kind of page,
and the page's own heading. Home keeps its hero, which is its identity, and has no masthead.

| Kind | Pages | Caption | Heading |
|---|---|---|---|
| `act` | `acts/<celex>/` | `Act · {domain}`, or `Act` with no domain | the act's name |
| `version` | `acts/<celex>/<key>/` | `Version · {act}`, the act linked | `Version in force 1 April 2025`, or `Version detected …` |
| `provision` | `acts/<celex>/<prov>/` | `Provision history · {act}`, the act linked | `Annex II · {its title}`, the title only where one says more than the coordinate (see the provision's title above) |
| `amending` | `amendments/<celex>/` | `Amending act` | the amending act's short name |
| `index` | `acts/`, `amendments/` | `Index` | `All watched acts`, `Amending acts` |
| `prose` | `dates/`, `methodology/`, `about/`, `feeds/`, `404.html` | what the page is about | its own heading |

The first four kinds are the objects a reader moves between, and each gets a band tinted in its
own colour with a shape before the caption; the rosters and the pages about the site share a
neutral rule. The caption always says the kind in words, so the colour and the shape are never
the only carriers. The not-found page prints no breadcrumb, an address that matches nothing
having no place in the tree.

**One trail, two renderings.** `site_/trail.py` builds each page type's trail once, as names and
site-root-relative paths. `identity.py` renders it as the visible breadcrumb, every rung a
relative link but the last, which is the page itself, unlinked and marked
`aria-current="page"`; on a phone the sheet shows only the parent rung, as a way back. `seo.py`
renders the same rungs as the JSON-LD `BreadcrumbList` a search engine prints under a result. A
test holds the two equal on every page that has both, so a reader and a crawler cannot be told
two different trails.

**The header bar marks the section a page belongs to** with `aria-current="page"`, by weight and
an underline rather than by colour alone: act, version and provision pages mark `All acts`,
amending-act pages and their roster mark `Amending acts`, and each page about the site marks
itself. Home and the not-found page mark nothing. On a phone (up to 40rem) the wordmark heads
the bar, the six section links sit in one row beside it that scrolls sideways, faded over its
last 2.5rem so the cut reads as more to come, with as much padding at its end so the last link
scrolls clear of the fade, and search takes the row under that. Nothing is folded behind
a menu: a menu would need a script to open, and it would hide the site's structure.

**Pages speak the reader's vocabulary; the stored one does not change.** On a page, an event is a
*version*, named by its date and the clock that date answers to, and an instrument is an
*amending act*. Headings and crumbs write a date as `1 April 2025` inside
`<time datetime="2025-04-01">`, built from a fixed month table and never from the locale. The ISO
form stays wherever a machine reads it: every `<title>`, every feed title and entry, the
`datetime` attribute and the committed changelogs. The JSON, the Markdown, the metrics and the
code keep `event`, `instrument` and `disputed`. **"Event" is not a reader word**: no page's
visible text or `<title>` says it, and `tests/site_/test_vocabulary.py` asserts that over the
golden tree and the scale tree. The one place a page prints it is the law's own verbatim text,
where the Medical Devices Regulation says "in the event that", and the test counts those per
page. The feeds' own summaries keep their wording, so a subscriber sees no churn.

## Every list names things the way the pages it leads to do

A list is a promise about the page each row opens, so a row names its object in the words that
page's heading uses, and each object in a row has one link, to its own page.

**Home** is the hero, then `Latest versions`, then the stat strip, then the lines counting what
the list leaves out. Each card is led by its act, a caption in the act's colour and shape
linking the act's page, and headed by the version's name, `Version in force 1 April 2025`,
linking the version's page. Under it: `Made by` and the amending act's short name in plain
text, the tally every version card prints, and the version pair as two small identifiers. One
link to the glossary sits above the cards rather than beside each tag. The stat strip is the
localisation figure in the sentence that says what it does not mean, set large beside it,
**after** the list: a stranger meets the versions before a measure of the engine that found
them, and the sentence, the number and the caveat are unchanged. It links the methodology
page's `#measured` section. Versions past the cap and versions naming no amending act are
counted in words, never dropped silently. The hero's act links use the long name where the
watchlist gives one, the name the act's own heading uses.

**An act page's index follows its timeline in the markup.** A phone reads in markup order, so a
reader there meets the versions first, then the index, then the dates the text names; from
60rem the grid places the index in the left column by named area (`"index main" "index dates"`),
sticky and capped at the height of the screen with its own scroll, so a short timeline never
stands beside a taller box of links. It stays a `<details open>` at every width.

**An act page's index** lists `Touched provisions`, each with its kind tags and, where one says
more than the coordinate, the title of its newest change, the one the provision's own page is
headed by; the sheet cuts it to one line and the markup carries it whole. Then `Versions`,
each by its date, `detected` written out where no in-force date is known, and the short name of
the amending act that made it. No version pair is printed there: an act of two hundred versions
pays every byte of a row two hundred times. A version card whose code carries another date than
its in-force date says so in one note, `Coded 20180101, the date EUR-Lex gives this consolidated
text; in force from 31 December 2015.`, and a card whose two dates agree says nothing.

**The acts roster opens with a jump list of its sectors**, each with its count, each link the
fragment the sector heading has always carried, so no address moved. A row leads with the act's
name, the label and key beside it one step down, the official title in the law's face cut
visibly with `[…]` (the rule is below), then the dated words. **Sectors are decided in one place**,
`site_/sectors.py`: the watchlist's `domain`, `Other` where none is declared and always last,
then case-folded order. The acts roster and the feeds page both read it, so an act sits under
the same sector on both.

**The amending-acts roster** keeps its year headings and is not grouped by sector: one amending
act can change acts in several sectors, and sector headings would list it twice. Each row names
the amending act, its key, its subject (the recorded official title, cut visibly) and the
watched acts it changed, each linking its page, three by name and the rest counted, then the
date with its clock. The act names carry the sector.

**A roster's subtitle keeps what the act is about** (`site_/titling.py`). An official title opens
with the act's own number and date, which the row already stands for, so both rosters drop that
opening clause and mark its absence with `[…]`. Where the rest is still over the 120-character
cap, the cut keeps its head and the `as regards …` or `with regard to …` clause, where an
amending act's title states its subject, with `[…]` for each elision; with no such clause it
keeps the head alone, marked. A title whose opening the rule does not recognise is cut from the
start exactly as the changelog's headings cut it. Nothing kept is changed, no-break spaces
included. Measured on 2026-09-19 over the 140 distinct amending-act titles the published
changelog repository records, all over the cap: 113 now show their subject clause on the roster,
where the cut from the start showed 9. The changelog's own `short_title` is not changed, because
it renders the committed public changelogs.

**The methodology tables stack on a phone.** Under 40rem each row becomes a block: the measure
as its heading, then the result, `n` and the meaning, each under its column's words, printed
from the cell's `data-label` by the sheet, so nothing sits off screen in a scroll box. The header
row is hidden visually and kept for a screen reader, and the markup carries explicit table roles,
because `display: block` drops a table's semantics in WebKit.

**The feeds page** lists the global feed, then one feed per act under the same sector headings,
with one clause saying what Atom is. The note about the one reissue of 2026-09-05 follows the
list. No feed file and no entry id moved.

**Search says `No results` on screen** as a row in the panel that is not an option, as well as
in the live region, so a sighted reader is not left looking at an empty box and the combobox
still reports no options. Each result's kind is a word in sentence case, `Act`, `Provision` or
`Amending act`, where the index holds a code; an alias reads `Act` like the name it stands for,
and an identifier reads as whichever of the two it leads to. The index's `kind` values are
unchanged.

## No backend, and that is the more interesting decision

A minimal backend is the obvious alternative, and this project has **none**. Static generation wins
on longevity (files have no dependencies to expire after six untouched months), on security
surface (no server, no store, no cookies, no analytics and no third-party request), and on ops
cost (a volume and a web server that serves files). The one
concession is search: `search-index.json` is built at build time and read by a hand-written,
dependency-free script that renders the search box itself, so a reader without JavaScript meets
no dead control and still has `acts/` and the feeds. An architecture test holds the generator to
loading that one committed file and writing no markup of its own. The box is a combobox owning a
listbox of options: focus stays in the input, `ArrowDown` and `ArrowUp` move the highlight and
wrap at both ends, `Home` and `End` jump to them, `Enter` opens the highlighted result and
`Escape` empties the box and closes the list. An off-screen live region says how many results a
query found, politely, which is also what makes `Enter` on nothing highlighted honest: it opens
the first result, and the count of results has already been announced. Each result is a plain
link before it is an option, so the pointer, the middle click and copy-address never depended on
any of that.

**The site loads that one script and no analytics of any kind, and that is a decision rather than
an omission.** Every page footer says "no cookies, no analytics, no third-party requests", and
analytics that cost nothing are paid for with a beacon script on every page: enabling one costs
that sentence, and the sentence is worth more than the numbers it would buy. What is used instead
adds nothing to the HTML. The host's own request statistics are derived server-side from traffic
it already proxies, which for a site whose product is a feed also gives the number that matters
most, how often `feeds/*.xml` was fetched. The two search consoles, which are the only place the
queries that surfaced a page and whether the act pages were indexed at all can be read, verify by
a DNS record and need no markup either; and if a verification file is used instead of a DNS record,
`write_site` never reads, moves or deletes anything it did not write, so a file dropped into the
deployed directory survives every rebuild. No code was needed for either console, and none is
planned.

## `--site-url`, `--repo-url` and `--changelogs-url`

`--site-url` is the one fact the generator cannot infer, and everything absolute needs it: an Atom
link, an entry ID, a canonical address, an `og:image` and a sitemap `<loc>` are all absolute by
definition. Without it no feed file, no `sitemap.xml` and no `sitemap_index.xml` is written, `/feeds/` says
why, and no page carries a canonical, an Open Graph tag or a JSON-LD block at all. All of it or none of it,
per page: a page carrying `og:title` with no `og:url` renders a preview that is wrong, which is
worse than a page with no preview. Entry IDs are the address an event is published at, the
act page's fragment under the site base, so a rebuild at one base never re-notifies a subscriber
and moving the base reissues every entry once; the entry's link follows the content to the event's
own page.

It also never prints where the changelog repository lives on the operator's machine. That path is
somebody's home directory, and a public site is the wrong place for it; the paths it does print
are the stable ones inside that repository. `--repo-url` turns those into links once a public home
exists, `--changelogs-url` names the changelog repository's own public home in the footer and on
the methodology page and turns the path each event page closes with into a link into that
repository, and all three URL flags are refused unless they are `https://`.

A `--repo-url` or a `--changelogs-url` on `github.com` yields file links, at
`<repo>/blob/main/<path>`, because that is where that host serves a committed file (verified for
the report on 2026-09-03 and for a changelog document on 2026-09-04). Any other home yields the
paths as text: the layout of a forge nobody has checked is a guess, and a link that 404s under the
sentence establishing where every figure on the methodology page came from is worse than no link
at all. The ref is `main` rather than the evaluation report's own revision, since `eval run`
records the revision of the tree it scored and the report is committed after it. An event page's
link is to the changelog file and never to a heading inside it: that host derives heading anchors
from heading text, so a deeper link would break silently the day a heading is reworded.

## `--operator`, `--contact` and `--watch-state`: the facts only a deployment has

Four flags carry things no committed artifact can know, and each renders on its own or not at all.
`--operator` and `--operator-url` name whoever runs this instance, `--contact` is an address a
reader may write to, and a build given none of them renders `/about/` without its "Who runs it"
section rather than with a placeholder where a person should be.

`--watch-state` is the fourth and points at the file the poller keeps its own record in, the path
`emendrix watch --state-file` names and, in the reference deployment, the file on the `state`
volume. With it `/about/` says two things it cannot otherwise know: the date the corpus was last
checked for changes published up to, and how many consolidations have been announced whose text is
not published yet, with the date the oldest of them was first seen. That is the difference between
a corpus that is quiet and one that has stopped, and it is the reader's to judge: the page states
the two facts and draws no verdict from them.

**The date is a cursor, not a run time.** Every poll reads a window ending at midnight that
morning, so what the file records is how far the corpus has been read, which is what the sentence
says. A missing, unreadable or foreign-schema file is not an error: the build says nothing about
polling and writes the page it writes without the flag, because a site that goes down over a
courtesy is worse than a page with one fewer sentence. Nothing is imported from the poller to read
it, the site being a rendering of documents somebody else wrote; the file's shape is pinned by a
test that builds a real state file and reads it back.

## The honesty rule, made structural

What all of this makes structural rather than aspirational is the honesty rule. Every page is a
*rendering of things already committed*, the changelog documents the loop wrote and the dated
evaluation report, so no page can obtain a figure with no provenance: there is nothing to fetch
and nothing to compute. The methodology table is built from the same `MetricRow` objects the
published table is
([`../src/emendrix/eval_/metric_rows.py`](../src/emendrix/eval_/metric_rows.py)), so the
two cannot disagree about a number *or* about the caveat attached to it, and a synthetic-cassette
qualification softened in one place softens in both. The committed golden tree
[`../tests/site_/golden/`](../tests/site_/golden/) is asserted file-by-file against what the command
writes, and it is wired to the *newest* committed report, so a new measurement breaks the test
until the site is regenerated, exactly as it does for the published table. Two builds of one set of
artifacts are byte-identical; a rebuild on a quiet day produces no diff.
