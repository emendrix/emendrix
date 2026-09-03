"""The dated record of every regeneration of the committed golden tree.

Each paragraph is one regeneration, in the house form: which files moved, by what, and
whether any measured figure moved with them. It is a record rather than documentation, so
nothing is ever trimmed from it, and it is a module of its own because it grew to half of
`test_golden.py` and pushed that module past its size cap on 2026-09-02; the properties and
the regeneration instructions stay there, beside the assertions they describe. The first
reading, on 2026-08-12, is described in that module's docstring, since it is the bar every
reading below was held to.

Read again the same day, when two files moved and nothing else did. The MDR act page carries a
new recording of its nine explanations and, in the collapsed before/after blocks, provision text
that keeps its words apart across block boundaries. The methodology page's provenance line and
its sampled-faithfulness cell follow the newest report, which is what the newest-report rule
in `test_golden.py` makes them do.

Read again on 2026-08-13, when the hand review of the 2026-08-12 recording was published. Two
files moved: the methodology page, whose spot-review cell names a reviewer and a date instead of
`pending` and whose provenance line follows the newest report, and that page's `lastmod` in the
sitemap. No measured figure moved with them.

Read again on 2026-08-14, when the footer grew the sentence naming the public changelog-data
repository. Nine files moved, the nine pages that carry the footer: `404.html`, `index.html`,
`acts/index.html`, `feeds/index.html`, `methodology/index.html`, and the four act pages under
`acts/`. Each moved by that one footer line, which now says the changelog data is public in the
changelog repository, in plain words because the golden build passes no `--changelogs-url`; the
linked form is asserted next to the shell itself. No feed, no `sitemap.xml` and no `style.css`
moved, and no measured figure moved with them.

Read again on 2026-08-14, later the same day, when the methodology page stopped claiming that
the only links leaving the site go to EUR-Lex. One file moved, `methodology/index.html`, by one
sentence: the closing claim now says no link leaves the site except to EUR-Lex and the
repositories the page names, which stays literally true here, where the golden build passes
neither repository URL and the how-built paragraph keeps its old wording, and on a deployment
that configures both links. The footer line of the earlier entry did not move again, no other
page moved, and no measured figure moved with it.

Read again on 2026-08-31, when every dated line on the site started naming its clock. Two
files moved. The acts index row and its meta description stopped saying "last amended": the
label had printed `event_dated`'s fallback, a detection date, as an amendment date, so an act
touched only by a backfill read as amended the day the backfill ran. The row now says
"in force" or "detected", the words the home page cards already used, and the MDR act page's
header says "newest amendment in force 2020-04-24" where it had claimed "reflects the
consolidated version of" over the same ambiguous value. No measured figure moved with them.

Read again on 2026-08-31, later the same day, when the site started counting events naming no
amending act apart from amendments. One file moved, `acts/index.html`, by one line: the lede
now reads "1 amendment event recorded, plus 0 events naming no amending act", both numbers
always printed so the split can never quietly collapse back into one figure. Nothing else
moved, because the golden's one event is the MDR postponement, whose window names `32020R0561`
and which is therefore not in the class: the front-page exclusion, the event label, the row
fallback and the feed lead are all asserted on toy entries in the unit suites instead. No
measured figure moved with it.

Read again on 2026-08-31, later again, when the act page split into a timeline and one page per
event. Ten files moved. The four act pages became indexes: a card per event keeps the versions,
the facts lines and the `id` every feed entry was published under, and links the event's own
page, which is new under `acts/<slug>/<key>/` and carries what the card used to hold, the
change blocks and the verbatim text, beneath a header naming the act. The MDR feed and the
global feed keep every `<id>` byte-identical and move only `<link rel="alternate">` to the
event page, so no subscriber is re-notified; the sitemap gains the event page under the event's
own date; the search index sends provisions to the event page at the same fragments; the home
card follows. The live site's heaviest act page was 6.1 MB in one document when this was
decided, and the split bounds a page by one consolidation instead of by an act's whole history.
No measured figure moved with it.

Read again on 2026-09-02, when every page started naming its act the way a person types it.
Seven files moved. The AI Act and REACH act pages, the two the example watchlist gives a
`long_name`, carry the long form as H1, in the title as `{long name} ({label}): every
amendment`, in the description and as the JSON-LD `Legislation`'s `name`, with the short label
on the facts line before the key and as `alternateName`; the MDR and DSA act pages, which carry
no long name, moved by `: every amendment` in the title alone. The MDR act page also renders
its official title whole, all 284 characters, where it had been cut at the changelog's cap with
`[…]`: the cut stays in the changelog and on the acts index, which is a list. The MDR event
page's title moved from the version pair to `9 provisions changed, in force 2020-04-24`, and
its description says the same in a sentence. `acts/index.html` links the long form on two rows
with the label beside it, and `search-index.json` gained one alias row, REACH's long form; the
AI Act's was already an alias and is indexed once. Every feed and `sitemap.xml` are
byte-identical, and so is `index.html`, whose card builds its dated words through the same
one helper the event title now uses. No measured figure moved with it.

Read again on 2026-09-02, later the same day, when every provision on an event page became a
heading. Two files moved. The MDR event page's nine change blocks each open with an `<h3>`
holding the pill, the coordinate and the title as three spans, where a paragraph had held
them with a dash between, and the applies line follows as a paragraph of its own; above the
first block the page gains a `nav.touched` listing the nine provisions in the page's own
order, each a fragment link to the anchor its block already carries, because nine is past the
six at which a list stops being a second copy of what is on screen. Every `id` on the page is
byte-identical and stays on the `div`, so the search index, both feeds and `sitemap.xml` did
not move. `style.css` gained seven lines, the minimum for the heading and the list to keep
the page's current look. No measured figure moved with it.

Read again on 2026-09-03, when the site gained a page saying who runs it. Twelve files moved.
`about/index.html` is new: what emendrix is in one paragraph, what it is not in the
disclaimer's own words, the two repositories in the footer's linked-or-plain form, and what
the site does on a reader's machine. It carries no "Who runs it" section, because that
section renders only from the three command-line values a deployment supplies and the golden
build passes none of them; the configured shapes are asserted on a rendered string in
`test_about.py` instead, since nothing personal is committed here. The ten pages that carry
the shell each moved by three edits and no others: the header bar gained a fourth link, the
footer gained a closing one, and the disclaimer paragraph stopped printing `Not legal advice`
twice, its lead now bolded inside the constant rather than prefixed to it. `sitemap.xml`
gained one `<url>` with no `<lastmod>`, the about page's content moving with the build rather
than with the corpus. Both feeds, `search-index.json`, `robots.txt`, `style.css` and the three
assets are byte-identical. No measured figure moved with it.

Read again on 2026-09-03, later the same day, when the stylesheet became a package and the
front door and the roster were rebuilt around it. Three files moved. `style.css` grew from
8111 to 11 504 bytes: a type scale and a spacing scale the rules now read instead of writing
their own sizes, a reading measure on prose, a visible focus ring on every interactive
element, a print block, and the rules for the two reshaped lists. It is one file the whole
tree shares, so those 3393 bytes are paid once per reader and never per page. `index.html`
gained 53 bytes: the credibility strip moved above the list it qualifies, and the card became
name first, its heading now the act and the link alone, with the counts on their own line and
the version pair below them in the mono face at reduced contrast. `acts/index.html` gained
273: 15 bytes for each of three lists that named themselves `roster`, and 57 for each of four
rows that gained the act's key beside its label, spans and the two literal spaces that keep
the row readable with no stylesheet at all. No palette value moved, which is why `og.png`
and the other two assets are byte-identical, and the fourteen contrast pairs the new
`test_style.py` measures pass in both schemes over the palette as it already stood. The nine
other pages, both feeds, `sitemap.xml`, `search-index.json` and `robots.txt` are
byte-identical, and no pinned size moved: the chrome markup did not change, and the heaviest
page in the tree is the MDR event page, which this pass did not touch. No measured figure
moved with it.

Read again on 2026-09-03, later again, when the act page and the event page were rebuilt around
what a reader arrives asking. Six files moved. Each of the four act pages split its header in
two: the identifying facts stay in `p.facts`, and the Atom feed and the EUR-Lex link move to a
`p.links` of their own, 18 bytes a page, because an action sitting in a chain between a domain
and a date read as another fact about the legislation. The MDR act page and the MDR event page
share the other change, 28 bytes each: an event now opens with its date as the `<h2>` and
carries the version pair below it in `p.ident`, one `<code>` where the heading had two, so the
heading answers when and the identifier stays on the page one step down. Every `id`, every
fragment link and every relative path is byte-identical, which is why both feeds, `sitemap.xml`
and `search-index.json` did not move, and neither did the home page, the roster, the about,
methodology, feeds and 404 pages or the three assets. `style.css` grew from 11 504 to 13 330
bytes, paid once per reader for the whole tree: the timeline is drawn as one, a rail with a node
per event in place of four rounded cards; a change block gained horizontal padding so the tint
on `.chg:target` has room and its title reads in the sans beside the coordinate; the touched
index became one wrapping row instead of two columns, so forty-five provisions cost a few lines
of height; the diff and the verbatim blocks gained line height, both tints state `--fg` rather
than inheriting it, and an elided run is a bordered chip that says what it stands for.
`.chg:target` is named again in the print block, a pseudo-class selector outranking the blanket
line whatever the order. No hex value moved, so the fourteen contrast pairs are unchanged in
both schemes and `og.png` is byte-identical. `_LARGEST_PAGE` moves by the 28 bytes above and
both at-scale pins by the same change over two hundred events. No measured figure moved with
it.

**2026-09-03, four fixes read off a measured build.** Every one of the twelve pages moved by
the same 82 bytes of chrome: a skip link, off-screen until it takes focus, as the first
focusable element on the page; `aria-label="Site"` on the header navigation, because an event
page whose provision index is also a `<nav>` announced two landmarks with one name between
them; and the `id` the skip link points at, on `<main>`. Three pages moved by more. The about
page no longer reprints the disclaimer under "What it is not", the footer carrying that
constant here as on every other page, and says what the tool is not in its own words instead;
a reader who met the same sentence twice on one screen read the second as a further claim to
compare against the first. The MDR act and event pages each gave back 23 bytes: the heading of
an event names one clock and its date, so the line under it carries only the clock the heading
did not, while an event with no in-force date says so and one carrying several lists them all.
Those two pages also gained 43 bytes for the class that keeps `EUR-Lex` off the line break it
took at 390px. Both feeds, `sitemap.xml`, `search-index.json`, `robots.txt` and the three
assets are byte-identical, and no `id`, fragment link or relative path moved. `style.css` grew
from 13 330 to 14 424 bytes, paid once per reader: the skip link's own rules, and a bound on
the act page's index, which `<details open>` had left unbounded below 60rem, where an act with
hundreds of provisions stood 20 510px tall on a 390px screen and pushed the timeline below all
of it. The index prints whole, a scroll box being unscrollable on paper. No hex value moved, so
the fourteen contrast pairs are unchanged in both schemes and `og.png` is byte-identical.
`_LARGEST_PAGE` moves by 102 bytes; `_HEAVIEST` falls 4518, the first downward move that pin
has made, and `_TOTAL_BYTES` rises 7282, 201 pages of chrome less 400 dates lines. No measured
figure moved with it.

**2026-09-03, five places where the site's own claim about itself was false.** One file moved,
`style.css`, from 14 424 to 14 976 bytes, paid once per reader for the whole tree. The palette
gained `--edge` in both schemes, the colour of a component boundary as distinct from the
hairline `--rule` draws: the pill and the tag border in it, at 3.20 to 3.75 light and 3.44 to
4.42 dark over the three surfaces they sit on, where `--rule` had drawn them at 1.31 and 1.46,
under the 3:1 WCAG 2.1 SC 1.4.11 asks of a boundary carrying no text. Inserted text inside a
diff is now underlined on screen as well as tinted, so neither mark depends on colour, and the
print block's `.diff ins` line is gone, having been compensating for exactly the gap the screen
rule now closes. `test_style.py` measures the three new pairs against a second, separate
minimum. Nothing else in the tree moved: no page carries a bare head code, the golden build
passes no `--repo-url`, so the methodology page's provenance line still prints its path as
text, and it passes no `--contact`, so the about page renders no address for the new opt-out
markers to wrap. Both feeds, `sitemap.xml`, `search-index.json`, `robots.txt` and the three
assets are byte-identical, `og.png` included, none of the four hexes it copies having moved,
and no pinned size moved: the two at-scale pins and `_LARGEST_PAGE` count pages, and this pass
changed one asset. No measured figure moved with it.

**2026-09-03, the amending act named on every surface.** Seven files moved and every one of
them says which instrument made an event. The MDR event page gained 618 bytes: a
`p.amending` line under the version pair, the number `Regulation (EU) 2020/561` linked to
EUR-Lex with `32020R0561` beside it, and under that the recorded official title of that
regulation, printed verbatim from the instruction signal's own claim, which is the one place
those words appear on the site. Its title and description name the instrument too, and each is
written three times in the head, so most of the rest of the growth is there; the description
also stopped repeating the version pair the page carries under its own heading and now names
the consolidated version the text was read from. The act page's timeline card gained the same
`p.amending` line and not the official title, thirty events being thirty titles. The front
page's card reads `9 provisions by Regulation (EU) 2020/561 · in force 2020-04-24`, the clause
riding with the count it is a count of, and the roster row's date fact gained the same clause.
Both feeds gained 63 bytes: the entry title is now the event page's own minus the site's name,
and the summary names the instrument by its number after the counts. Every feed `<id>` is
byte-identical, which is the promise that may never move; `sitemap.xml`, `search-index.json`,
`robots.txt` and the three assets are byte-identical too, `og.png` included, and no anchor or
relative path moved. `style.css` grew from 14 976 to 15 300 bytes for two rules and their
comment, and no hex value moved, so the contrast pairs are unchanged in both schemes. The name
shown is a label the watchlist declares, else the number rendered from the CELEX by the
convention of its year, else the key, and the CELEX stays beside it wherever a number is shown.
`_LARGEST_PAGE` moves by 618 bytes and `_TOTAL_BYTES` by 4508, about 23 bytes on each of two
hundred event pages whose titles and descriptions were reworded and which name no amending act
at all. No measured figure moved with it.

**2026-09-03, the amending instrument given a page.** Two files were added and fourteen moved.
`amendments/index.html` is the roster of every instrument a committed event names, one row per
instrument under the year of that instrument's newest event, and
`amendments/32020R0561/index.html` is the one instrument the golden corpus names: its number as
the heading, the recorded official title verbatim under it, its CELEX linked to EUR-Lex, and
then the Medical Devices Regulation with the timeline card of the one event it produced there
and, under the card, the nine coordinates that event's changes attribute to it, each linked to
its own block on the event page. Its `ld+json` declares a three-rung breadcrumb and a
`Legislation` whose `legislationChanges` names the act it moved; `legislationIdentifier`
carries the CELEX, and `legislationAmends`, which the technical review suggested, is not a
schema.org property and appears nowhere. Every page on the site gained the header bar's fifth
link, `Amendments`, between `All acts` and `Methodology`, which is the whole of the diff on ten
of the fourteen. The MDR event page gained 157 bytes: that link at three directories down, and
a line under the act's facts pointing at everything `Regulation (EU) 2020/561` amended. It is
the act's only event, so it carries no pager; an act with a history now closes each event page
with the events either side of it, older as `rel="prev"` because the timeline runs newest
first, each named by its own dated words. `sitemap.xml` gained the roster, dated by the newest
event on the site like the home page, and the instrument's page, dated by its newest event.
`search-index.json` gained two rows for that instrument, one of kind `amending` under the
number it is shown by and one of kind `celex` under its key. `style.css` grew from 15 300 to
16 201 bytes for the amended-act section, the event pager, their comments and one widened
selector, the timeline's rail now being drawn on both pages that carry a timeline, and no hex
value moved, so the contrast pairs are unchanged in both schemes. Both feeds,
`robots.txt` and the three assets are byte-identical, `og.png` included, every feed `<id>` with
them, and no anchor or relative path already published moved. `_LARGEST_PAGE` moves by 157
bytes, `_HEAVIEST` by 43 and `_TOTAL_BYTES` by 43 917, three quarters of that last being the
pager on two hundred generated event pages. No measured figure moved with it.

**2026-09-03, one page per provision.** Nine files were added and four moved. Each of the nine
is one coordinate the golden's single event touched, at `acts/32017R0745/<slug>/`, where the
slug is `location_slug` of the canonical string (`ar-113`, `an-ix`) and never a human reading
of it. A page carries the coordinate as its H1 in human form, the act and its identifier, the
provision's own title from the consolidated text where that says more than the H1 already does
(`Penalties` under `Art. 113`; `ANNEX IX` under `Annex IX` is skipped, case and whitespace
folded for the comparison and nothing stored rewritten), a count of the history, and then one
step per event that touched it. This act has one event, so each of the nine has one step: the
date with its clock, the change type, the instrument linked to its own page with the CELEX
beside it, the applies-from line, the sentences that survived the gate, and the verbatim text
open in a `<details>`. An older step would carry a link to the block on its event page instead
of the text, which is the weight rule these pages exist under and which no page in this golden
exercises. The step id is the anchor the event page already publishes, so nothing addressable
was minted. Each page's `ld+json` declares four breadcrumb rungs and a `WebPage` whose `about`
is the act's `Legislation` extended by one `hasPart` carrying the coordinate's name and nothing
else: a provision has no address at EUR-Lex that resolves and no identifier outside this
corpus's location vocabulary. The MDR event page gained 102 bytes, the nine coordinates in its
change headings now being links to those pages. The act page lost 360 bytes: each entry in its
touched-provisions index linked the newest change's fragment on the event page and now links
the coordinate's own history, which is the question that index has always been asking.
`sitemap.xml` gained the nine pages, each dated by the newest event that touched it, which for
this act is the only one. `search-index.json` lost 360 bytes for the same reason, its nine
provision rows moving off the event anchors and onto the pages; the labels are unchanged, and
the dedupe by canonical string now means one page rather than one arbitrary event.
`style.css` grew from 16 201 to 16 926 bytes for three
rules and their comments, the coordinate link and the two that set a step's margins and heading
level, and no hex value moved, so the contrast pairs are unchanged in both schemes. Both feeds,
`robots.txt` and the three assets are byte-identical, `og.png` included, every feed `<id>` with
them, and no anchor or relative path already published moved. `_LARGEST_PAGE` moves by 102
bytes and stays the MDR event page; the largest of the nine new pages is 11 225 bytes.
`_HEAVIEST` moves down by 3586, the at-scale act index having 401 shorter sidebar links, and
`_TOTAL_BYTES` by 1 036 140 over 401 new pages. No measured figure moved with it.

**2026-09-03, wayfinding on the pages that show a change.** Eleven files moved and none was
added. The MDR event page, which carries nine changes and so renders the index, now wraps that
index and the blocks in the act page's own two-column grid: at 60rem and wider the index is a
sticky column beside the changes, and below it the wrapping row is untouched, uncapped and
exactly as it was. The index opens with `9 changes in this event`, the label a column needs when it
stands on its own, counting the blocks it lists rather than the provisions those blocks touch,
because a coordinate one event touched twice is two blocks and the facts line above already
counts provisions; every change heading ends with a `§` permalink to its own block,
named for a screen reader because the mark is a symbol; and the page closes, inside the
section holding the blocks, with a link back to `#content`, the id the skip link already
targets. All three key off the one threshold the index does, so a short page gained none of
them. The nine provision pages gained the same permalink on each step heading, on the same
anchor, so one change is linkable from either view of it. The citations moved out of the
sentences: a change now ends with one `<p class="cites">Cited: ...</p>` of its distinct
citations in first-mention order, deduplicated by the rendered pair of address and label
rather than by address alone, each label held on one line. Eighteen inline pairs on the event
page became nine rows, and Art. 59, whose three sentences each cited the same single anchor,
prints it once. Nothing below the page moved: the committed Markdown and JSON keep every
citation on the sentence that carried it, which is the form the citation gate resolves and the
eval harness counts, and neither file in the changelog repository differs by a byte.
`style.css` grew from 16 926 to 18 701 bytes for the grid at one media query, the permalink,
the citation row, one margin on the index's new label, and their comments, plus three print
rules that un-cap the column and take the permalink and the back link off paper; no hex value
moved, so the contrast pairs are unchanged in both schemes and every colour used here is a
token already measured. Both feeds, `sitemap.xml`, `search-index.json`, `robots.txt` and the
three assets are byte-identical, `og.png` included, every feed `<id>` with them, and no anchor
or relative path already published moved. `_LARGEST_PAGE` moves by 491 bytes and stays the MDR
event page, about 1050 of wayfinding less about 559 the citation row gave back; `_HEAVIEST`
does not move, its page being a timeline of cards with no change block on it; `_TOTAL_BYTES`
moves by 133 304, which is 1600 permalinks over two hundred event pages and four hundred and
one provision pages of diff-only changes, where no citation row exists to pay any of it back.
No measured figure moved with it.

**2026-09-03, how much of each provision moved.** Twelve files moved and none was added: the
MDR event page, its nine provision pages, `methodology/index.html` and `style.css`. Every
change now prints the characters the comparison under it marked inserted and deleted, beside
the pill in the heading on both surfaces that show a change, with a `title` saying what the
characters are and, at line granularity, that a whole changed line is counted. The event
page's index carries the same figure per item, a weight class by decade of characters, and
the event's totals on its label, `9 changes in this event · +1,050 −248 characters`. The
reading of that page is the point of the pass: six of the nine changes are date moves of 4 to
50 characters and three are prose, +576 −15 on Art. 59, +236 −130 on Art. 123, +151 −16 on
Art. 122, which is the honest picture of a postponement and was previously visible only by
opening nine `<details>`. The count is the rendered comparison's own and no second comparison
is made. The methodology page gained one paragraph in the build section saying what a
character count is and what it is not, and the metrics table is untouched, because that table
is the eval harness's and this number evaluates nothing. `style.css` grew from 18 701 to
19 587 bytes for the figure's own rule and four weight classes; no hex value moved, so the
contrast pairs are unchanged in both schemes and the only colour used here is `--muted`,
already measured on every surface it sits on. Both feeds, `sitemap.xml`,
`search-index.json`, `robots.txt` and the three assets are byte-identical, `og.png` included,
every feed `<id>` with them, and no anchor or relative path already published moved.
`_LARGEST_PAGE` moves by 2310 bytes and stays the MDR event page, eighteen figures at about
128 bytes; `_HEAVIEST` does not move, its page being a timeline of cards; `_TOTAL_BYTES`
moves by 142 719 over 1201 figures. No measured figure moved with it.
"""
