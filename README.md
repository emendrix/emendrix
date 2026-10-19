# emendrix

> Your regulatory dependencies, with a changelog.

EU law changes constantly, and EUR-Lex shows the *current* text but not *what changed*. `emendrix`
subscribes to the EU's own publication feed, detects when a watched act is amended, computes a
provision-level structural delta between versions, and explains it in plain English where **every
sentence cites a provision that actually resolves**: a git-committable changelog, so you subscribe
to a regulation the way you subscribe to a dependency. This is **v0.1.0**, and
[`CHANGELOG.md`](./CHANGELOG.md) is the release record and the limitations it ships with.

## Not legal advice

**`emendrix` produces engineering assistance, not legal advice.** Its output is a machine-computed
description of textual differences between published versions of legal acts. It may be incomplete,
out of date, or wrong. It is not a substitute for reading the official consolidated text on
[EUR-Lex](https://eur-lex.europa.eu/) or for professional legal counsel. Nothing it produces creates
a lawyer-client relationship, and no warranty of accuracy is given or implied; see
[`LICENSE`](./LICENSE). Every user-facing output carries this disclaimer.

## Install and first run

Python ≥ 3.12, managed with [`uv`](https://docs.astral.sh/uv/). Never `pip`. `diff`, `watch`, `eval`
and `site build` call no model and need no account; only `explain`, `run` and `backfill` reach a
provider, and only when not replaying a cassette. Every fetching command takes `--fixture-dir` and
then touches no network, which is how CI runs the suite.

```bash
git clone https://github.com/emendrix/emendrix.git
cd emendrix && uv sync --all-extras --dev && uv run emendrix --help

# the MDR's one-year postponement, offline, against the fixtures committed here
uv run emendrix diff 32017R0745 02017R0745-20170505 02017R0745-20200424 \
    --fixture-dir tests/fixtures/eu
```

```
eu:32017R0745 02017R0745-20170505 -> 02017R0745-20200424
0 inserted · 3 modified · 0 deleted · 0 renumbered · 6 deferred
9 touched units · 131 unchanged · 0 disputed

[eight of the nine units elided here; the command prints all of them]

~ MODIFIED   AR 122 — Repeal
    within: AR 122 ALN 1
    dates: -[2020-05-26] +[2020-04-24, 2021-05-26]
    applies from: unknown (the text changed beyond its dates, so no date that moved can be read as the application date)

Not legal advice: this output is machine-computed from published texts, carries no lawyer's review, and is engineering assistance only.
```

## The CLI

| Command | What it does |
|---|---|
| `emendrix diff <celex> <from> <to>` | Diff two versions of one act and print what changed. A version is named the way the corpus names it: `32017R0745` is the act as published in the Official Journal, `02017R0745-20200424` a consolidation. `--markdown` renders the changelog entry and `--json` the serialised `Delta`; neither calls a model or needs a key. `--observed-on` stamps the first-class states. |
| `emendrix watch --once` | Poll the notification feed for amendments to the watched acts. `--since`, `--until`, `--watchlist`, `--state-file`, `--channel`, `--json`. `--loop --interval` is a while/sleep; use cron. |
| `emendrix explain <celex> <from> <to>` | The whole loop over one named transition, skipping the feed. The manual trigger. `--json-out`, `--output-repo`, `--cassettes`. |
| `emendrix run --once` | The cron-able command: poll, fetch, diff, corroborate, explain, gate, emit. `--summary json` puts the counts on stderr as one JSON object, for a log collector. |
| `emendrix backfill` | The same loop over every historical transition of every watched act; an output repository is required. Start with `--dry-run`, which lists what would run and spends nothing. `--since`, `--act`, `--limit`, `--polite-delay`, `--ledger`, `--retry-limit`. |
| `emendrix repair corroboration` | Recompute the third signal on entries that are already committed and correct the ones it moves. Explicitly invoked and never reached from a resume: a backfill treats a settled entry as settled on purpose. The entry is replaced in place, every other entry in that act's changelog keeps its bytes, and every committed explanation is carried over rather than re-asked for. `--dry-run` prints what would move, including how many disputed flags would flip, and writes nothing at all. `--act`, `--limit`, `--fixture-dir`, `--summary`. |
| `emendrix repair signals` | Bring every committed entry with a corroboration block under the signal rules in force since 2026-10-08: an instruction parse that claims nothing in its window is unavailable, a unit only the instruction parse names moves from the change list to the entry's report, and the metadata's location codes are read as the units they name. It rebuilds both second opinions from the claims the entry already carries, so it fetches nothing and calls no model, and every committed explanation is carried over byte-identical. An entry is rewritten only when a signal, a verdict or a row moves, and records a repair of kind `signals`. `--dry-run` prints the changes and the disputed changes before and after, per act and in total, and writes nothing at all. `--act`, `--limit`, `--repaired-on`, `--summary`. |
| `emendrix repair tables` | Give every committed change to a profiled substance table its keyed diff of table entries, and write each profiled act's register from its newest published version. It re-parses both versions of each such entry through the cache, sets only `table_entries` and the schema version `1.3`, and carries every verbatim text, explanation, signal and date over byte-identical; no model is asked anything. A version the cache cannot produce leaves its entry as it is, counted and named. `--dry-run` prints per act what would move, with typography-only amendments and whitespace-only pairs apart, and writes nothing. `--act`, `--limit`, `--fixture-dir`, `--repaired-on`, `--summary`. |
| `emendrix repair explanations` | Ask the model again for a change that shipped with no explanation because the answer was unusable, and splice the answer into the entry that already exists. Explicitly invoked, never reached from a resume, and it fetches nothing: the prompt is rebuilt from the entry's own stored texts, so the model is shown exactly what the page shows. Its citation check is narrower than the loop's, resolving against those texts rather than against two whole provision trees, and no coordinate check runs at all; the entry records both. A change that fails again keeps its stated reason and is counted. `--dry-run` names every change it would ask about and prices them at the published rate, builds no engine and spends nothing. `--act`, `--limit` (counting changes, which is what a call is paid for), `--cassettes`, `--summary`. |
| `emendrix repair unexplained` | Restate a note that quoted the provider library's own error text, which entries written before the curated reasons existed carry, and stamp the counted kind that goes with it, so the note says what the code would say today and the change becomes selectable by `repair explanations`. It matches an exact set of measured strings rather than a prefix, because most of that field is the house register and a curated reason can carry no kind either. A note naming a provider that never answered is counted and left exactly as it is: neither kind is true of one, and the unfinished kind would send a later backfill to re-run whole transitions that are already correct. No model, no network, no key. `--dry-run`, `--act`, `--limit`, `--summary`. |
| `emendrix texts build` | Store the verbatim text of every listed version of every watched act that the store lacks, in a directory beside the changelog repository that nothing publishes. A version the corpus answers with a state (pending, no English, no structured text) is recorded as that state, never raised; a second run over an unchanged listing writes nothing. `--act`, `--limit`, `--dry-run`, `--rebuild`, `--fixture-dir`, `--observed-on`, `--summary`. `emendrix texts show <celex> <version> [coordinate]` prints a stored version's units, or one node's text verbatim, for an operator. |
| `emendrix twins build` | Pair the provisions of each `[[twins]]` pair of acts by textual similarity, from each act's newest stored version, and commit the twin map into the changelog repository when its bytes move. No network, no model, no clock. `--pair`, `--dry-run`, `--summary`. |
| `emendrix eval <subcommand>` | `run`, `publish-readme`, `sample-digest`, `judge-benchmark`, and the pair `build-corpus` then `build-subset` **in that order**: the first writes `explain_subset: null` and only the second fills it in, so stopping after it leaves the model layer with no pinned subset to measure over. `build-corpus` also defaults to `--fetch` and stamps `built_on` from the clock, so reproducing the committed `corpus.json` byte for byte takes `--no-fetch --built-on 2026-08-06`, the date already in the file. |
| `emendrix site build --out site/` | Write the static site from the committed changelogs and the newest committed eval report. `--changelogs`, `--site-url`, `--repo-url`, `--watchlist`. `--operator`, `--operator-url`, `--contact` and `--watch-state` are the deployment's own: they fill the about page's "Who runs it" section, none has a default, and a build given none of them renders that page without it. `--watch-state` is the poller's state file, and with it the page says the date the corpus was last checked and how many consolidations are waiting for their text. `--comparison-cache` names a directory the before/after comparisons are kept in between builds, which changes how long a build takes and never what it writes. `--prune` deletes afterwards what the build did not write, keeping dotfiles, search-console verification files and earlier stylesheets, scripts and fonts; `--prune-dry-run` lists it instead. |

## Configuration

Copy [`watchlist.example.toml`](./watchlist.example.toml) to `watchlist.toml` and name the acts by
CELEX. `[output] repo_path` is where a run commits its changelog: a git repository of its own,
created if absent, owned by you and never pushed. There is no default path, so with nothing
configured a run prints its report and writes nothing. [`.envrc`](./.envrc) is committed and holds
no secret; it sources the gitignored `.envrc.local`, where a key goes.

**The text store** is the other thing a deployment keeps. `emendrix texts build` writes the
verbatim text of every provision of every stored version of every watched act, one gzipped file
per version, into a directory beside the changelog repository: `--text-store`, else
`EMENDRIX_TEXT_STORE`, else `[output] text_store_path`, with no default, and refused inside any
git working tree so no commit can publish it. It is there for computation, the twin map below is
built from it, and **it is never served**: no page, feed, sitemap or API file carries it, and
losing it costs a rebuild from the corpus. Measured on 2026-10-19 with a writer of the same layout
over the 456 versions of 72 acts the disk cache held, it comes to 219,486,762 bytes gzipped
(1.58 GB raw); that is the cache on that day, not a deployment's store.
[`docs/text-store.md`](./docs/text-store.md) is the whole of it.

| Variable | Default | What it sets |
|---|---|---|
| `OPENROUTER_API_KEY` | unset | Provider access, read only when the explain stage records or runs live. |
| `EMENDRIX_EXPLAIN_CASSETTES` | `replay` | `replay`, `record` or `live`. |
| `EMENDRIX_MODEL` | `openrouter:anthropic/claude-sonnet-5` | The explainer. |
| `EMENDRIX_JUDGE_MODEL` | `openrouter:openai/gpt-5.6-sol` | The faithfulness judge. |
| `EMENDRIX_OUTPUT_REPO` | unset | The changelog repository, below `--output-repo` and above `watchlist.toml`. |
| `EMENDRIX_TEXT_STORE` | unset | The text store, below `--text-store` and above `watchlist.toml`. |
| `EMENDRIX_POLITE_DELAY_S` | `1.0` | Seconds between network calls; cache hits never sleep. |
| `EMENDRIX_EXPLAIN_TEXT_CAP` | `40000` | Per-side character cap on the text the model is shown; overrun is marked, never silent. Six more `EMENDRIX_EXPLAIN_*` knobs, the context cap among them, are declared and reasoned about beside their fields in [`explain/settings.py`](./src/emendrix/explain/settings.py). |

**`replay` is the safe default, and the reason is money.** Every model exchange is recorded as JSON
under `tests/cassettes*/`, keyed by `sha256(model_id + system + user + schema_version)` with the
prompt beside the answer, so a reviewer can re-derive the key by hand. Under `replay` a prompt
nobody recorded fails loudly naming the file it wanted rather than reaching for a provider, and CI
builds no provider client at all.

## Running it on a server

```bash
docker build -f deploy/Dockerfile --build-arg VERSION=0.1.0 -t ghcr.io/emendrix/emendrix:0.1.0 .
cd deploy && cp .env.example .env    # then set EMENDRIX_PUBLIC_HOST to your own host
docker compose up -d web mcp && docker compose run --rm poller && docker compose run --rm page
```

Compose refuses to start until `deploy/.env` sets `EMENDRIX_PUBLIC_HOST`, the one place the
deployment's host is named: the site's links and feed ids, and the hosts the MCP server at `/mcp`
answers, are all built from it.

A two-stage build (`uv sync --frozen`, non-root runtime, `git` and nothing else beside the
interpreter), an `nginx` serving the generated directory, the read-only MCP server it proxies `/mcp`
to, and two one-shot jobs. There is
deliberately **no scheduler container**: the schedule is host cron calling `docker compose run`,
because a scheduler image is a third thing to keep patched and a second place a failure can hide.
`deploy/compose.yaml` documents what runs when and which volumes are disposable, and `VERSION` is
the caller's to set: omitting it labels the image `dev`.

Three things the operator handles outside this repository. `deploy/absolute-redirect.conf` is the
web service's one line of nginx configuration, for anyone putting this behind a TLS-terminating
proxy: without it nginx builds the redirect to a missing trailing slash out of the scheme it can
see, the proxy's plain HTTP, and sends an `https://` reader through one unencrypted request.
Caching is the second: the stylesheet and the script are named for a digest of their own bytes, so
they may be cached for as long as you like and a deploy never needs a purge, while the pages and
`search-index.json` want a short lifetime. `icon.svg` and `og.png` keep fixed names, so changing
either is the one thing on the site that still needs one. And **this deployment does not yet serve
the site's own 404 page.** `site build` writes `404.html` on every build, and a host that serves it
for an unmatched address gives the reader the search box and a way back, but nothing under
`deploy/` names it as nginx's error page. That is server configuration rather than a generator
change, and the file is already there.

### The optional account service

[`packages/emendrix-service`](./packages/emendrix-service/) sends email alerts for watched acts,
provisions and CAS or EC numbers: a reader follows "Watch this" on the site, confirms an address,
and gets an instant, daily or weekly email listing exactly the watched provisions and table
entries the record says changed,
or follows them in a personal feed, with one-click unsubscribe, export and delete. It reads only
the published record and the catalogue, and the pipeline does not know it exists. It is optional:
`deploy/compose.yaml` runs it, with its own Postgres, only under the compose profile `accounts`,
and a site built without `--accounts` links nothing to it.

Running it makes the operator the controller of the addresses it holds, with a privacy notice to
publish (a template is in [`docs/privacy-notice.template.html`](./docs/privacy-notice.template.html)),
processor agreements to sign, and a database to back up, because its accounts and watchlists
cannot be rebuilt from anything else. [`docs/accounts.md`](./docs/accounts.md) is the whole of it:
the matching rules, the data held and for how long, the security checklist, the backups and the
compose recipe; [the service's README](./packages/emendrix-service/README.md) lists every setting
and command.

## What it does not do

It is **not legal advice**; not a compliance assessment tool, since it never asks about your
business; **not a consolidation engine**, since it does not *apply* amendments to produce
authoritative text of its own, it detects, localises and explains them; not a search engine over
law, which adjacent tools do well; it does not republish the law, since the text it keeps for
computation is never served; and it is not a paid service: the optional account service sends
email alerts for watched provisions and holds nothing but an address and a watchlist. Inside that
mandate the release still has holes, documented rather than hidden.
[`CHANGELOG.md`](./CHANGELOG.md) §"Known limitations" is the authority on what `0.1.0` cannot do,
with the measurement behind each entry; [`docs/limitations.md`](./docs/limitations.md) explains the
mechanisms. Neither is restated here, because a limitation summarised is a limitation softened.

## How it works

The loop is `WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → GATE → EMIT`, and **every stage except
`EXPLAIN` is deterministic Python.** The model never decides *whether* something changed, *which*
provisions are involved, or *how* to classify a change; it phrases the difference between two
verbatim texts it is handed, citing keys it did not mint, and the gate discards anything citing a
provision it was not offered. The thesis is that the amending act already tells you what changed, so
that part is parsing rather than inference: three signals answer the question independently, the
structural diff, the corpus's own modification metadata and the amending act's prose instructions,
and where they disagree the change ships marked `disputed`.
[`docs/architecture.md`](./docs/architecture.md) is the layering, the `CorpusAdapter` seam and the
diff; [`docs/pipeline.md`](./docs/pipeline.md) walks the stages;
[`docs/evaluation.md`](./docs/evaluation.md) is the measurement.

## The chemicals lens

Eight acts print tables of substances: REACH, CLP, Cosmetics, Biocides, PIC, POPs, plant
protection products and Batteries. emendrix reads the rows of 28 of those tables out of the act's
own markup, keys each row by the column the act numbers it by, and recognises the CAS, EC and CLP
Index numbers its cells print by their check digits, never from a list outside the corpus. A
change to one of those tables then says which **table entries** were added, removed or amended,
each with its rows before and after as the act prints them, in the payload, the Markdown and on
the event page; no model is involved, and the model never sees the rows.

Every CAS and EC number an entry prints has a page, `substances/cas-50-00-0/`, saying in which
entries of which acts it **appears** in the newest version the record holds, with every recorded
change to those entries; the site search finds a number with or without hyphens. The same is
data at `/api/v1/substances.json` and `/api/v1/substances/<scheme>-<value>.json`, the MCP tool
`find_substance` answers it for a model, and the optional account service watches a number
across every act. **Appearing is all it says.** Many entries name a group of substances and print
no number, so a number no entry prints may still be covered by one, and no page, file or answer
says what the law makes of a substance. The tables read and left out, and every gap of the
lens, are in [`docs/limitations.md`](./docs/limitations.md) §"Substance tables".

## Textual twins

Some acts were written as variants of each other: most articles of the Medical Devices
Regulation have a near-copy in the In Vitro Diagnostic Medical Devices Regulation, often under
another number. For each pair of watched acts named in a `[[twins]]` block of the watchlist,
`emendrix twins build` scores every article of one against every article of the other, and every
annex against every annex, by the share of their words that match in order, and calls two
provisions **twins** when each is the other's closest match and the score reaches a floor read
off the corpus (0.90, measured 2026-10-19). Sub-provisions below a pair are aligned the same way.

A reader gets, under every change to a provision with a twin, one line naming it, with its score,
the dates of the texts it was paired on and whether the record holds a change to it by the same
amending act: `Twin in IVDR: Art. 106(1), textually similar (0.958)`. The provision page names its
twin in its header. Each pair whose texts differ beyond their numbering has a twin page showing
**only the passages where the two texts differ**, a few words of context around each, never either
provision whole, with both on EUR-Lex; a pair whose texts are identical, or identical apart from
numbering, is said to be so and has no page. A pair index lists every pair and every provision with
no twin ([MDR and IVDR](https://emendrix.eu/twins/eu-32017R0745--eu-32017R0746/)), and the map is
data at `/api/v1/twins/<pair>.json`. **Twin means textually similar and nothing more**: no page says
a provision is equivalent to its twin, has the same effect, or should change because the other did.
The example watchlist pairs the MDR and the IVDR; the hosted instance also pairs the three European
Supervisory Authorities regulations with each other and the anti-dumping and anti-subsidy
regulations. The figures and the gaps are in [`docs/limitations.md`](./docs/limitations.md)
§"Twin provisions".

## Measured results

`uv run emendrix eval publish-readme` reads every number below out of the newest committed report,
and a test regenerates the section and fails on any difference: a figure cannot drift from its run,
or be quoted without what it does not mean.

<!-- emendrix:metrics:start -->

*Generated by `uv run emendrix eval publish-readme` from the report named below. Do not edit between the sentinel comments — a test regenerates this section and fails on any difference.*

| Measure | Result | n | What it means — and what it does not |
|---|---|---|---|
| **Localisation** (which provisions changed) | P 0.976 / R 1.000 / **F1 0.988** | 17 transitions | Structural diff against the corpus's own modification metadata, at article-or-annex granularity. Not a measure of whether the explanation is any good; precision is dragged down by blanket amendments the reference set annotates only once. |
| Instruction-parse agreement (cross-check) | P 1.000 / R 1.000 / F1 1.000 | 7 transitions | A third, independent reading of the same question, from the amending act's own prose. Weaker by construction: it cannot read a range or an instruction that delegates to an annex, and those are counted as unread, never approximated. |
| Disputed changes (signals disagree) | 0.020 | 98 changes | Changes at least one signal named and another did not. They ship marked `disputed`; a high rate is a data-quality finding, not a hidden failure. |
| Change classification | accuracy 1.000 | 81 units | Insert / modify / delete against the metadata's role codes, on units both signals named. The role semantics are empirical — the authority tables publish no labels. |
| Citation grounding (gate pass, no retry) | 1.000 | 55 changes | Of the changes with an explanation to check, the share whose first answer cited only provisions it had been offered. **Citation validity, not explanation quality** — a wrong sentence with a good citation passes. |
| Quote-fallback rate | 0.000 | 55 changes | The share where the gate replaced the model's prose with a verbatim quotation of the provision after one failed retry. Correct by construction and visibly marked; this is where grounding losses go, and no change is ever dropped. |
| Explanation faithfulness (sampled) | 0.750 | n = 20, LLM judge + spot review (pending) | Whether the shipped sentences follow from the evidence the writer was given: the prompt's deterministic-facts header and the two capped texts (the header joined the evidence base on 2026-08-09, so earlier rates answer a narrower question and are not comparable). The weakest number here: a sampled judgement by `openrouter:openai/gpt-5.6-sol`, which is a different and stronger model than the explainer but not an independent one. The raw fraction, no confidence interval — at this n an interval would be wider than the number is useful. |

Measured on **2026-10-08** at revision `dfe620a`, from [`reports/eval/2026-10-08-dfe620a.md`](./reports/eval/2026-10-08-dfe620a.md). The deterministic rows cover every transition in the committed corpus (18 of 18 scored); the model rows cover the pinned explanation subset only, because each change in it is one recorded call to a provider.

<!-- emendrix:metrics:end -->

[`docs/evaluation.md`](./docs/evaluation.md) reads the table: which figures may be compared with
which, and why the model rows describe one recording rather than a model. `eval_/thresholds.py`
floors each and CI fails on a breach; a measured number may rise silently and may never fall.

## Development

The quality gate is four commands, all four green. CI mirrors it exactly, and nothing is reported
green on a narrowed run.

```bash
uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest

uv run pytest --ignore=tests/eval    # the iterating tier
uv run pytest -n0 <nodeid>           # one test, serially, which is how a failure gets read
uv run pytest -m live                # network tests: opt-in, excluded by default and in CI
uv run pytest -m record              # rewrites the committed cassettes; opt-in for the same reason
```

The account service's tests start one `postgres:17-alpine` container through Docker, or use the
server `EMENDRIX_SERVICE_TEST_DATABASE_URL` names, and fail rather than skip without either.

`pytest` runs on all cores (`-n auto --dist loadscope`). Measured 2026-08-12 on a ten-core machine
over the 1173 tests then committed, the same count passing every way: 205s serially, 81s on eight
workers, 17s on all cores with `tests/eval` left out, where nearly two thirds of the serial time
sits in three tests that re-derive the eval corpus. That tier is the cheap loop, never the
definition of passing. Read a failure with `-n0`: one that passes serially and fails in parallel is
a finding about shared state.

## Documentation

[`docs/README.md`](./docs/README.md) indexes the reference material by question: the architecture,
the pipeline stage by stage, the evaluation, the output format (repository layout, Markdown shape,
versioned JSON schema, every cap that can truncate a quote), the site, the JSON API the site serves
the record through (with an example workflow that watches one provision from CI) and the MCP server
that hands the same record to a model, the text store kept for computation and never served, the
optional account service that emails watched provisions ([`docs/accounts.md`](./docs/accounts.md)),
the limitations, the roadmap, and HTML walkthroughs of the shipped code. The empirical grounding is
seven end-to-end traces against live Publications Office endpoints, across three acts spanning 2006
to 2026, and any data-source claim made anywhere else in this repository is subordinate to what
those traces measured. They were produced by [`scripts/validation/`](./scripts/validation/), kept
only so the published numbers are reproducible artifacts, with the reports committed beside it; it
is the only code here that hits the network outside the opt-in `live` tests, and CI never runs it.

A program finds the record and the MCP server from `/llms.txt`, `/.well-known/api-catalog` and
`/.well-known/ai-catalog.json`, which the site build writes, and the card the server answers at
`/mcp/server-card`; [`docs/mcp-discovery.md`](./docs/mcp-discovery.md) lists every such surface
and what must change with a tool.

## License

[MIT](./LICENSE) © 2026 Martins Erts

The site's self-hosted fonts are not covered by that licence. The files under
[`src/emendrix/site_/static/fonts/`](./src/emendrix/site_/static/fonts/) are subsets of IBM Plex
Sans and Source Serif 4, renamed "Emendrix Sans" and "Emendrix Serif" as a modified copy must be,
and ship under the SIL Open Font License 1.1, whose full text sits beside them.
