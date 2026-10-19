# scripts/validation

One-off validation code, outside the package and exempt from its rules. It exists so that the
numbers behind this project's data-source claims are reproducible artifacts rather than
assertions. It is **not** production code and nothing under `src/emendrix/` imports it:

- stdlib + `httpx` only, no package structure, no tests, exempt from the ~300-line module cap;
- it hits live Publications Office endpoints, which no other part of the repository does at test
  time, and CI never runs it;
- `src/emendrix/` reimplements all of it properly (typed, cached, fixture-driven).

`trace.py` fetches with a 3-second delay and caches every response under `.cache/` (gitignored), so
a second run of any command below is offline and free.

Seven scripts here do import the package, because what they measure *is* the package. All seven
read through the same client, the same composition root and the same disk cache the loop uses,
write nothing, call no model and are offline unless `--fetch` is passed.

`instruction_effect_dates.py` measures how often an amending act says when its instructions take
effect (`src/emendrix/eu/instructions/effect.py`, and the two readers beside it). Its figures are
quoted in [`../../docs/limitations.md`](../../docs/limitations.md):

```bash
uv run python scripts/validation/instruction_effect_dates.py            # every cached act
uv run python scripts/validation/instruction_effect_dates.py --fetch    # and the rest
uv run python scripts/validation/instruction_effect_dates.py --verbose 32019R2033
uv run python scripts/validation/instruction_effect_dates.py --markup 32021R2117
```

`--markup` prints an act's final-provisions articles as the package holds them and reads nothing
else. `tests/fixtures/eu/celex_32021R2117.article6.xml` is that command's output, redirected, so
the markup a test asserts against was never retyped.

`instruction_claim_scoping.py` measures the other end: how many of the claims already published
in the changelog corpus the consolidation window takes back. It wants a clone of that corpus,
which is a separate repository and is never committed here, so a reading is dated by the commit
of the clone it was taken over:

```bash
git clone https://github.com/emendrix/changelogs /tmp/changelogs
uv run python scripts/validation/instruction_claim_scoping.py /tmp/changelogs
uv run python scripts/validation/instruction_claim_scoping.py /tmp/changelogs --verbose
```

`evidence_staleness.py` measures the one correction in this project that costs money. An
explanation is written about a particular pair of verbatim texts and cannot be recomputed, so a
parser fix that moves stored text leaves prose describing evidence the page no longer shows. It
re-derives both versions of every committed event through today's parser and reports, per change,
whether the evidence matches, differs, or cannot be derived, plus the transitions affected and how
many characters the differing changes carry. It wants the same corpus clone:

```bash
uv run python scripts/validation/evidence_staleness.py /tmp/changelogs
uv run python scripts/validation/evidence_staleness.py /tmp/changelogs --verbose
```

An entry written from 2026-09-05 carries an evidence digest and answers this by arithmetic. One
written before that carries none, and the script compares its stored text instead, counting the
two bases separately: what the model was shown is a fact only the run that made the call can
record, and nothing here writes a digest onto anything.

The rule for reading those two bases in that order lives in `emendrix.repair.staleness` and is
imported here rather than repeated, because `emendrix repair evidence --dry-run` selects and
prices the changes it would ask about with the same comparison. This script measures the reach
of a correction over a whole corpus in one parse per version; the command decides, per entry,
what a correction would cost and then carries it out.

`substance_tables.py` measures what the parser deliberately does not read: the rows of the
tables inside annexes. The provision tree takes a `TBL` as prose, joining cells by a space and
rows by a line break, so a stored annex text cannot be split back into the rows the act prints;
the markup still holds them. Over every consolidated English Formex package the disk cache
holds, it asks which annex tables carry CAS numbers, EC numbers or CLP Index numbers and in
which columns, which column tells a table's rows apart, how those keyed rows move between
consecutive versions, and how much a full list of one version's rows would weigh:

```bash
uv run python scripts/validation/substance_tables.py survey             # every cached act
uv run python scripts/validation/substance_tables.py survey --act 32008R1272 --verbose
uv run python scripts/validation/substance_tables.py survey --fetch     # fill gaps first
uv run python scripts/validation/substance_tables.py transitions --act 32008R1272 \
  --record /tmp/changelogs
uv run python scripts/validation/substance_tables.py excerpt 32008R1272 \
  02008R1272-20260701 "AN VI" --rows 40
```

A table's container is named by the parser's own placement function, its grid is built from
each cell's `COL`, `ROWSPAN` and `COLSPAN` rather than from position, and a cell's text is
`verbatim_text` of the `CELL` element. An identifier counts only with a valid check digit; a
value of the right shape with a wrong one is counted and printed with its row, because it is a
fact about the act. `--record` holds each published change against the row diff of its unit,
over a clone of the changelog corpus dated by its commit. `excerpt` prints one table as a
well-formed fragment, its ancestors reduced to their tags, attributes and the headings a
location is read from, with its header rows and its first `--rows` body rows; the same input
gives the same bytes, so a table fixture is cut by a command rather than retyped.

What its figures do not mean. A "substance table" holds at least three cells with a valid CAS
or EC number or an Index-shaped value: a statement about markup, not about what an act
regulates. A row naming no identifier is not a row about no substance, since a group entry
names a family rather than a number. The key column is chosen from the cells alone, per table
and version, and the row diff it drives is a naive keyed comparison of cell texts, not the
change an amending act made. Register and diff sizes are of a hypothetical JSON shape, written
to size a decision rather than to describe a file anything publishes.

`substance_crosscheck.py` holds the keyed row diff of every published change to a substance
table against the amending acts the change names: does the act print the entry the
consolidation says it added or amended? It imports `substance_tables.py` for the row reader,
keys each table by the profile read off the markup on 2026-10-16, reads every table of every
named amending act through the project client, and gives each disagreement the first
deterministic cause that applies (typography only, an identifier under another key, an act the
consolidation lists but the change does not name, a corrigendum). It wants the same corpus
clone as the scripts above; the reading of 2026-10-16 is
`results/substance-crosscheck-2026-10-16.txt`.

```bash
uv run python scripts/validation/substance_crosscheck.py /tmp/changelogs
uv run python scripts/validation/substance_crosscheck.py /tmp/changelogs --act 32008R1272 --verbose
uv run python scripts/validation/substance_crosscheck.py /tmp/changelogs --fetch
```

What its figures do not mean. Agreement is about keys, not row content: a printed key whose row
the consolidation transcribed differently still agrees. An entry or reference number printed for
one annex matches the same number in another annex of the same act, so the Cosmetics and REACH
Annex XVII figures are upper bounds. It is a measurement of the entry diff taken once, not a
signal: nothing in the pipeline reads it and no change is marked disputed by it.

`text_store_survey.py` measures what a store of every provision of every consolidated version
would weigh before anything is built to hold one. Over every consolidated English package the
disk cache holds, read through the adapter the way a build reads it, it serialises each version
with its own small writer (one header line, then one compact JSON line per node in pre-order
carrying the location, the parent's location, the heading, the verbatim text, the comparison
text and its sha256, the whole gzip at level 9 with `mtime=0`) and reports raw and gzip bytes per
act, beside a units-only layout and a pooled one that writes each act's distinct comparison
texts once. `tokens` reports the length of every distinct comparison text by depth against a
2,048-token cap, and `coverage` sets the versions the record has diffed and the versions each
tree notice lists against the packages the cache holds:

```bash
uv run python scripts/validation/text_store_survey.py size [--act 32017R0745] [--verbose]
uv run python scripts/validation/text_store_survey.py tokens [--act 32017R0745]
uv run python scripts/validation/text_store_survey.py coverage --record /tmp/changelogs [--fetch]
```

What its figures do not mean. The token figure is a proxy, `ceil(chars / 4)`, because no
tokenizer for the embedder is installed: it overstates plain English and understates numbers,
identifiers and tables read as prose. A node's text is its whole subtree, so the store's layout
repeats text at every depth by design, and the pooled figure says what deduplication would save,
not what anything writes. Every figure is over the cache on the day of the run; scaling it to
every listed version is a projection.

`twin_provisions.py` measures which provisions of the Medical Devices Regulation and the IVDR
are textual twins, meaning textually similar and nothing more. Every article is scored against
every article and every annex against every annex by the word ratio
(`SequenceMatcher(None, a_words, b_words, autojunk=False).ratio()` over the comparison texts'
words, with `real_quick_ratio` and `quick_ratio` as bounds), and a pair is a twin when each is
the other's best match at or above a floor. The floor is read off the corpus: the lowest candidate
from 0.50 up, in steps of 0.05, at which at least 95% of the mutual-best pairs above it share a
normalised heading, else 0.90. `floor` also aligns the children below each pair, places the
record's changed coordinates on them, and counts how many pairs a page of differing passages
would withhold as too different to excerpt; `divergence` lists the changes of one act's record,
made by an amending act that also made an event of the other, which left the twin untouched,
against a bar of five such changes from two amending acts; `screen` runs a shingle screen and
then the word ratio over every pair of acts the cache holds:

```bash
uv run python scripts/validation/twin_provisions.py pairs [--fetch]
uv run python scripts/validation/twin_provisions.py floor --record /tmp/changelogs [--fetch]
uv run python scripts/validation/twin_provisions.py divergence --record /tmp/changelogs [--fetch]
uv run python scripts/validation/twin_provisions.py screen [--floor 0.60]
```

What its figures do not mean. Heading agreement is a proxy for the precision of a pairing: two
articles can share a heading and differ in substance. The twins are paired on the newest texts
while the record's changes were made to older ones. A one-sided change says the record holds no
change to the twin from the same amending act, not that one was due; no figure here says a
provision is equivalent to another or should change with it.

## Commands behind the committed reports

Each command writes `results/<name>.txt`; those files are committed and are the measured record.

```bash
uv run python scripts/validation/trace.py --write versions     32017R0745
uv run python scripts/validation/trace.py --write versions     32006R1907
uv run python scripts/validation/trace.py --write annotations  32017R0745
uv run python scripts/validation/trace.py --write annotations  32006R1907
uv run python scripts/validation/trace.py --write annotations  32024R1689

uv run python scripts/validation/trace.py --write trace 32024R1689 original 20260727
uv run python scripts/validation/trace.py --write trace 32017R0745 20170505 20200424
uv run python scripts/validation/trace.py --write trace 32017R0745 20230311 20230320
uv run python scripts/validation/trace.py --write trace 32017R0745 20230320 20240709
uv run python scripts/validation/trace.py --write trace 32017R0745 20240709 20250110
uv run python scripts/validation/trace.py --write trace 32006R1907 20220501 20221014
uv run python scripts/validation/trace.py --write trace 32006R1907 20081012 20090120 \
  --substitution preparation:mixture
```

The substance-table readings are redirected rather than written, and carry their date in the
name. They were read on 2026-10-16, after `survey --fetch` had filled the six table-bearing
acts' gaps, against a clone of the changelog corpus at `6c4fcdc` (2026-10-08):

```bash
uv run python scripts/validation/substance_tables.py survey \
  > scripts/validation/results/substance-tables-survey-2026-10-16.txt
for act in 32006R1907 32008R1272 32009R1223 32012R0528 32012R0649 32019R1021 \
           32009R1107 32023R1542; do
  uv run python scripts/validation/substance_tables.py transitions --act $act \
    --record /tmp/changelogs \
    > scripts/validation/results/substance-tables-transitions-$act-2026-10-16.txt
done
uv run python scripts/validation/substance_crosscheck.py /tmp/changelogs \
  > scripts/validation/results/substance-crosscheck-2026-10-16.txt
```

The text-store and twin readings are redirected the same way. They were read on 2026-10-19
against a clone of the changelog corpus at `1db1143` (2026-10-17), offline first and then once
with `--fetch` for the coverage, the pairs and what depends on them, because the cache lacked the
Medical Devices Regulation's newest consolidation (20260719); each file's header says which:

```bash
d=2026-10-19; r=scripts/validation/results
uv run python scripts/validation/text_store_survey.py size > $r/text-store-size-$d.txt
uv run python scripts/validation/text_store_survey.py tokens > $r/text-store-tokens-$d.txt
uv run python scripts/validation/text_store_survey.py coverage --record /tmp/changelogs \
  > $r/text-store-coverage-$d.txt
uv run python scripts/validation/twin_provisions.py pairs > $r/twin-pairs-mdr-ivdr-$d.txt
uv run python scripts/validation/twin_provisions.py floor --record /tmp/changelogs \
  > $r/twin-floor-$d.txt
uv run python scripts/validation/twin_provisions.py divergence --record /tmp/changelogs \
  > $r/twin-divergence-$d.txt
uv run python scripts/validation/twin_provisions.py screen > $r/twin-screen-$d.txt
uv run python scripts/validation/text_store_survey.py coverage --record /tmp/changelogs --fetch \
  > $r/text-store-coverage-fetch-$d.txt
uv run python scripts/validation/twin_provisions.py pairs --fetch \
  > $r/twin-pairs-mdr-ivdr-fetch-$d.txt
uv run python scripts/validation/twin_provisions.py floor --fetch --record /tmp/changelogs \
  > $r/twin-floor-fetch-$d.txt
uv run python scripts/validation/twin_provisions.py divergence --fetch --record /tmp/changelogs \
  > $r/twin-divergence-fetch-$d.txt
```

`versions` inventories an act's consolidated versions and their English manifestations.
`annotations` inventories its CELLAR modification annotations (the observed role and location
vocabulary corroboration needs). `trace` runs the three-way comparison for one version pair:

1. structural Formex diff of the two consolidated texts;
2. CELLAR modification annotations whose `START_OF_VALIDITY` falls in `(date(A), date(B)]`;
3. a deliberately naive parse of the amending acts' instruction prose;

and prints per-signal provision sets, P/R/F1 of (1) against (2), and the disagreements.

`--substitution OLD:NEW` answers "how many diff-only units does one blanket word substitution
explain?" Used for the REACH 2008→2009 trace, where the amending act orders one such substitution
"throughout the text" and CELLAR annotates it once.

## Reading the output

- `original` as a version tag means the act as published in the OJ, used when the first consolidated
  version is not available in English.
- Units are keyed as `AR 5`, `AR 10a`, `AN VI`: the top-level provision, which is the unit of change.
- `P n/a` means both compared sets were empty; it is not a score of zero.

Nothing here interprets law. Every claim it makes is either a count, a set comparison, or a
verbatim quotation from a fetched document.
