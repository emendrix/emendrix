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
index.html            search, the latest amendments, and the one-line measured claim
404.html              the page a mistyped address gets, with a way back
acts/index.html       every watched act, grouped by the domain the watchlist gives it
acts/<celex>/         one page per act: the whole watched history, newest first, as cards
acts/<celex>/<key>/   one page per event: the changes and the verbatim text
acts/<celex>/<prov>/  one page per touched provision: its history, newest first
amendments/           every instrument a committed event names, newest first, grouped by year
amendments/<celex>/   one page per instrument: every watched act it amended, and what it moved
about/                who runs the site, and what it does on the reader's machine
methodology/          the metrics table with its caveats, the loop, the disclaimer in full
feeds/                what the feeds are and where they are
feeds/all.xml         every amendment event, as Atom
feeds/<celex>.xml     one act's events, for a reader who watches only that act
robots.txt            what crawlers may read, and where the sitemap is
sitemap.xml           every page, with the date its content last moved
search-index.json     act and instrument names, aliases, CELEX numbers and touched provisions
search.js             the one script; style.css is the one stylesheet
icon.svg              the favicon; og.png is the link-preview card
```

Four things about that tree are not visible in the listing. Every page states its own canonical
address, so the two ways a static host serves one page, with and without the `index.html`, do not
read as two pages. Every page advertises the feeds that cover it in its `<head>`, so a reader's
feed reader finds them from a visit rather than from the feeds page. `sitemap.xml` and that whole
head block, canonical, Open Graph, Twitter card and JSON-LD alike, need an absolute address and
are omitted entirely without `--site-url`, which is the rule the feeds already follow; `robots.txt`
and the favicon link need no base and are written either way, so the only thing `robots.txt` loses
is its `Sitemap:` line. And every `<lastmod>` comes from the corpus, an act's newest event or the
report's run date, never from the build clock, so a rebuild that changed nothing tells a crawler
nothing changed, and an act nothing has happened to yet carries no `<lastmod>` at all rather than
a guessed one.

The evidence is on the site rather than behind a link out of it, one page per event. An act's
own page is the timeline: a card per event with the facts and the anchor every feed entry was
published under, linking the event's page. That split is a weight decision: an act's history is
unbounded and one backfilled act served 6.1 MB as a single page, where an event is bounded by
one consolidation. The event page lists the provision changes with the sentences that survived
the citation gate, and each change opens onto the before and after text in full: a **unified
word diff** computed at build time by
`difflib.SequenceMatcher` over whitespace-split tokens, with deleted and inserted spans marked in
place. Below a similarity of 0.5 the texts are shown stacked instead, labelled as too different
to diff inline, because an inline rendering of a rewrite is noise wearing the clothes of a
comparison. The stored text is never touched: the diff is a comparison-time rendering, the same
category as the whitespace handling inside the comparison functions.

Every change heading, and the index entry that points at it, carries a figure such as `+1,204
−318`: the characters the comparison below it marked inserted and deleted, or for a provision
compared line by line the characters in the lines that changed. It is measured on that one
comparison rather than computed again, it is labelled `characters` wherever it is totalled, and
it is **not a measure of legal effect**, which the methodology page states in full; the index
gives each link a weight by decade of characters so a page of forty-five changes shows where
the text actually moved.

An event of six changes or more opens with an index of the provisions it touched, and from
60rem wide that index is a sticky column beside the changes rather than a row above them, so a
reader forty blocks down can still see the map; narrower than that it stays the wrapping row,
which costs a few lines where a column would cost a screen. The same threshold puts the link
back to the top at the foot of the page. Every change heading, on an event page and on a
provision page alike, ends with a `§` permalink to that change's own anchor, which is the
anchor both pages already publish. The citations a change's sentences carry are printed once
for the change, in first-mention order and deduplicated by the pair of address and label,
rather than after every sentence: a change whose sentences all cite the same before-and-after
pair used to print that pair once per sentence. **This is a rendering decision and nothing
below the page moves**: the committed Markdown and JSON keep every citation on the sentence
that carried it, which is the form the citation gate resolves and the eval harness counts.

The same changes are published a second way, under the provision. `acts/<celex>/<prov>/` is one
coordinate's whole history, newest first: a step per event that touched it, each with the date
and its clock, the change type, the instrument that made it, the applies-from line and the
sentences that survived the gate. The path segment is the slug of the canonical location string
(`ar-6`, `an-xvii`, and `an` or `tit` for a change keyed to a whole annex or title), never a
human reading of it, because a second numbering for one coordinate is a second thing to keep in
step and the corpus writes both `AN 4` and `AN IV`. **The newest step carries its verbatim text
in full and every older step links the block on the event page that holds its own**: one
committed change carries 4.1 million characters of before-and-after text and one coordinate has
been touched by 47 events, so a page repeating the evidence per step would multiply the heaviest
page on the site by its own history. The step ids are the anchors the event pages already
publish, so nothing addressable moved when these pages arrived.

Every event that does name an amending act says which one, on every surface it appears on: the
event page's `<title>`, its description and a line under its heading, the act page's timeline
card, the front page's card, the acts index row's date fact and the Atom entry's title and
summary. The name is, in order, the short name the watchlist declares under `[[amending_acts]]`,
the official number rendered from the CELEX by the numbering convention in force for its year
(`Regulation (EU) 2020/561`, `Directive (EU) 2015/2366`), and the key itself. The CELEX stays
beside the number wherever the number is shown, linked to the act on EUR-Lex, because the number
is a reading of the identifier and the identifier is the fact; the reading happens at the CLI
boundary, which is the one place in the site generator allowed to know what a CELEX is. Where a
committed document recorded the instrument's official title, the event's own page prints it
verbatim under the line, which is the one surface with room for one. None of it is authored: a
label is a label, a number is mechanical and reversible, and a title is the corpus's own words.

Each named instrument also has a page of its own under `/amendments/<celex>/`, addressed by the
key the corpus published and never by a year-and-number reading of it, and every event page
links it. It gathers what the event pages already carry, under the instrument instead of under
the act: every watched act the instrument amended, the timeline card of each event it produced
there, and under each card the coordinates that event's changes attribute to that instrument
and to no other, because one consolidation can fold several instruments and crediting each of
them with all of the work would be a claim the corpus did not make. Where an instrument moved
more than one watched act, the event page names the others beside the link. `/amendments/` is
the roster of every instrument a committed event names, newest first by the newest event each
produced and grouped under the year of that date; an instrument the watchlist names a short
name for and no event names gets no row and no page, a declared label not being evidence that
anything happened. Every event page also carries the events either side of it in its own act's
history, older first as `rel="prev"`, each named by its dated words, the timeline running
newest first.

Some committed events name no amending act at all: their corroboration window turned up no
modification annotations and no amending-act instructions, so only the text comparison observed
them. The commonest shape is the act as published set against its own first consolidation, where
no amending act can exist yet. The site derives the class at build time from the committed
document's own fields (`site_/attribution.py`) and says the fact rather than a cause: the front
page leaves these events out of "Latest amendments" and counts the exclusion in words, the acts
index counts them apart from the amendment events and never answers a date fact with one, the act
page keeps every one in place under the label "no amending act named" with one sentence saying
what it means, and the feeds keep every one with the same fact leading the summary. Nothing is
dropped: the difference in the published text is real and stays shown; what the pipeline did not
establish is which act, if any, caused it, and no page claims more than that.

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
definition. Without it no feed file and no `sitemap.xml` is written, `/feeds/` says why, and no
page carries a canonical, an Open Graph tag or a JSON-LD block at all. All of it or none of it,
per page: a page carrying `og:title` with no `og:url` renders a preview that is wrong, which is
worse than a page with no preview. Entry IDs are the address an event was first published at, the
act page's fragment, and never change, so a rebuild never re-notifies a subscriber; the entry's
link follows the content to the event's own page.

It also never prints where the changelog repository lives on the operator's machine. That path is
somebody's home directory, and a public site is the wrong place for it; the paths it does print
are the stable ones inside that repository. `--repo-url` turns those into links once a public home
exists, `--changelogs-url` names the changelog repository's own public home in the footer and on
the methodology page, and all three URL flags are refused unless they are `https://`.

A `--repo-url` on `github.com` yields file links, at `<repo>/blob/main/<path>`, because that is
where that host serves a committed file. Any other home yields the paths as text: the layout of a
forge nobody has checked is a guess, and a link that 404s under the sentence establishing where
every figure on the methodology page came from is worse than no link at all. The ref is `main`
rather than the evaluation report's own revision, since `eval run` records the revision of the
tree it scored and the report is committed after it.

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
