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
"""
