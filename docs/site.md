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
acts/<celex>/         one page per act: the whole watched history, newest first
methodology/          the metrics table with its caveats, the loop, the disclaimer in full
feeds/                what the feeds are and where they are
feeds/all.xml         every amendment event, as Atom
feeds/<celex>.xml     one act's events, for a reader who watches only that act
robots.txt            what crawlers may read, and where the sitemap is
sitemap.xml           every page, with the date its content last moved
search-index.json     act names, aliases, CELEX numbers and touched provisions
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

An act page carries the evidence rather than a link to it. Each amendment event lists its
provision changes with the sentences that survived the citation gate, and each change opens onto
the before and after text in full: a **unified word diff** computed at build time by
`difflib.SequenceMatcher` over whitespace-split tokens, with deleted and inserted spans marked in
place. Below a similarity of 0.5 the texts are shown stacked instead, labelled as too different
to diff inline, because an inline rendering of a rewrite is noise wearing the clothes of a
comparison. The stored text is never touched: the diff is a comparison-time rendering, the same
category as the whitespace handling inside the comparison functions.

## No backend, and that is the more interesting decision

A minimal backend is the obvious alternative, and this project has **none**. Static generation wins
on longevity (files have no dependencies to expire after six untouched months), on security
surface (no server, no store, no cookies, no analytics and no third-party request), and on ops
cost (a volume and a web server that serves files). The one
concession is search: `search-index.json` is built at build time and read by a hand-written,
dependency-free script that renders the search box itself, so a reader without JavaScript meets
no dead control and still has `acts/` and the feeds. An architecture test holds the generator to
loading that one committed file and writing no markup of its own.

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
worse than a page with no preview. Entry IDs are the permalink of the event, so a rebuild never
re-notifies a subscriber.

It also never prints where the changelog repository lives on the operator's machine. That path is
somebody's home directory, and a public site is the wrong place for it; the paths it does print
are the stable ones inside that repository. `--repo-url` turns those into links once a public home
exists, `--changelogs-url` names the changelog repository's own public home in the footer and on
the methodology page, and all three URL flags are refused unless they are `https://`.

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
