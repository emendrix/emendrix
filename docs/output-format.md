# The output format

What a run writes: the layout of the output git repository, the shape of the Markdown, the versioned
JSON beside it, the index over that JSON, and every cap that can truncate a quote. Start at
[`../README.md`](../README.md) for how to run it, and [`./pipeline.md`](./pipeline.md) for what
produces these events.

## A regulatory dependency with a review workflow

The product claim of this project is that your regulatory dependencies get the same review workflow
as your code dependencies, and `emendrix.output` is where that claim is cashed. A run ends as a
**commit in a local git repository you own**: one directory per act, a Markdown `CHANGELOG.md`
with the newest version first, and the same events as versioned JSON beside it:

```bash
uv run emendrix run --once --output-repo ~/regulatory-changelog     # or [output] in watchlist.toml
uv run emendrix diff 32017R0745 02017R0745-20170505 02017R0745-20200424 \
    --fixture-dir tests/fixtures/eu --markdown                      # diff-only: no model, no key
```

```
~/regulatory-changelog/index.json
~/regulatory-changelog/eu/32017R0745/CHANGELOG.md
~/regulatory-changelog/eu/32017R0745/changes/02017R0745-20200424.json
~/regulatory-changelog/eu/32017R0745/index.json
```

The format is chosen for what it *forces*: every sentence carries a citation that links to a
provision in a version; `before`/`after` are verbatim quotes rather than paraphrase, so the model
cannot be wrong about them; applicability is on its own line, separate from the text change,
because "in force" and "applies to you" are different questions; and the change type comes from
the structural diff, never from the model's opinion. A `disputed` change is rendered and marked
with *what* disagreed, its reason in words and then the verdicts, "no text, named by corpus
metadata alone: seen by corpus metadata, not by the structural diff", because a disagreement
hidden is a disagreement lied about. A sentence the citation gate wrote in place of
ungrounded prose says so in the text. Both quote caps are printed with the number of characters
they dropped: a silently truncated "verbatim" quote is worse than a long one. The committed golden
file [`../tests/output/golden/mdr-changelog.md`](../tests/output/golden/mdr-changelog.md) is a real
example, byte-asserted against what the command writes.

## Three decisions about the repository

**It is yours.** emendrix creates it if it is absent and commits into it, and never pushes;
pushing, hosting and ownership are not this tool's business.

**It must be a repository emendrix made.** A path that resolves inside an existing git repository
is refused before a byte is written, and so is a path that *is* one and does not carry emendrix's
own marker file. Together those are the general form of the embarrassing bug where a mis-scoped
`git add` commits emendrix's source into your changelog or the reverse.

**Re-emitting an event is a no-op.** Identical bytes are not rewritten, nothing is committed when
nothing was staged, and an entry that *has* changed is replaced in place rather than duplicated at
the top, so a cron entry running hourly produces one commit per amendment.

**A correction is a new commit on top, and history is never rewritten.** `emendrix repair` is the
one command that reaches into entries already committed. It reads a payload, replaces one part of
it and writes it back through the same writer, so the entry is replaced in place and every other
entry in that act's `CHANGELOG.md` keeps its bytes. It is always invoked explicitly and is never
reached from a resume, it writes only the entries it actually changes, and each one is its own
commit whose subject says the entry was repaired rather than emitted. What a repair did is
recorded on the entry as a `repairs` entry beside the `explain` and `gate` blocks, which keep
recording the run that produced it: no repair retracts a call that was made. Re-serialising an
entry written under an older schema adds the fields the schema has gained since, so a repaired
entry's diff carries those additions beside the correction; entries the repair had nothing to say
about are not touched at all, which is what keeps that drift on the corrected set and nowhere
else.

**A repaired explanation was written later than the entry it sits in, and the entry says so.**
`emendrix repair explanations` asks the model again for a change that shipped with no
explanation, so that change's prose is newer than every sentence beside it and than the
`detected_on` date, which does not move: a repair is not a detection. The `repairs` entry carries
the date the pass ran, how many changes it addressed, how many it repaired, how many it could not,
and what the calls cost. It also carries `coordinates_checked: false`, because a repair works from
the entry's own stored texts and holds neither provision tree, so the gate's coordinate check did
not run; recording it is how an unrun check is kept from reading as one that passed. A change the
model failed on again keeps the reason it was committed with, word for word.

**A rebuilt entry carries today's parse of the same two versions, and says which explanations
survived it.** `emendrix repair evidence` is the one repair that re-fetches: it parses both
versions again, re-derives the delta, and holds every change against what the entry states its
evidence was. A change whose evidence still reads as published keeps its sentences, its gate
decision and its citations exactly as they are; one whose evidence moved is asked about again,
about the corrected text; a change today's delta no longer holds is withdrawn; and one it holds
that the entry does not is asked about and counted apart, because the two answer different
questions. The `repairs` entry carries `coordinates_checked: true`, which no other repair can:
this one holds both provision trees, so the gate's coordinate check actually ran. The act, both
version identifiers and `detected_on` do not move, so no permalink and no feed id can, and the
commit subject says the verbatim texts were re-derived rather than promising they did not move.
A change the model fails on again keeps both its sentences and the stored text they were written
about, which is one pair rather than two halves of two.

**A change to a profiled table gains its entry diff and keeps everything else.** `emendrix repair
tables` re-parses both versions of each published entry with a change to a unit holding a
profiled table, sets `table_entries` on those changes exactly as the loop computes it today, and
moves the document to `1.3`; every verbatim text, explanation, citation, signal and date is
carried over byte-identical, and no model is asked anything. An entry with no such change is left
at the version it was written under, where `null` already means what it says. A version the
cache cannot produce leaves its entry as it is, counted and named. After the entries it writes
each profiled act's register from the act's newest published version, one commit per act.
`--dry-run` prints per act what would move, typography-only amendments and whitespace-only pairs
apart, and writes nothing.

**A note that quoted a library is restated, and one that names an unreachable provider is not.**
`emendrix repair unexplained` replaces a reason written before the curated ones existed, which
could be the provider library's own error text, with the sentence the code writes today, and
stamps the counted kind beside it. The change keeps everything else it had: no sentence gains or
loses a citation, no verbatim text moves, and every reason this project curated stands, including
the ones a change written before the kind existed carries with no kind at all. A note naming a
provider that never answered is counted in the `repairs` entry as remaining and left exactly as it
is, because neither kind is true of one and `unexplained_kind: "provider_unavailable"` is what
tells a later run the entry is unfinished.

"Newest first" means the newest **version**, not the newest emission. The poller runs forward and a
backfill fills history in underneath it weeks later, so a new entry is inserted at its place in the
order rather than at the top; every entry already in the file keeps its bytes and its neighbours.
Backfilling after a poll therefore produces the file a poll after a backfill would, and which
happened first stops being visible in the artifact.

There is deliberately **no default path**. Every other location the project picks by itself is
disposable, a response cache or a watch state file, and a git repository the tool commits into is
neither. With nothing configured, `run` prints its report and writes nothing.

## The JSON

The JSON carries `schema_version` from its first byte because other tools read it.

Two things in it are there for a reader who wants to render the events differently later. Each
change names the acts that amended it (`amending_acts`), as corpus-scoped identifiers rather than
a string to parse, so grouping a changelog by amending act needs no second pass over the corpus. No
title is fetched for one, so the identifier is what ships. And each signal publishes the claims
behind its verdict (`corroboration.signals[].claims`), at the depth the corpus made them, so an
annotation on `AR 5 PA 1 ALN 1 PTA (bb)` survives into the artifact instead of being flattened to
`AR 5`. The structural diff publishes none: it produces the changes themselves, so a copy there
would be a second delta. Neither field is a schema bump: both have defaults.

**Every disputed change says which signal disagreed and how**, in `dispute_reason`, a code read
off the change's own `signals` and `null` exactly when `disputed` is false. It is computed, never
stored apart from the signals: a document whose `dispute_reason` contradicts its own signals is
refused on read, as one whose `disputed` does is, and a document written before the field existed
reads back with it filled. The codes are evaluated in this order and the first that applies wins:

| Code | When |
|---|---|
| `kind_mismatch` | no applicable signal is absent, and the kinds the observing signals name share nothing |
| `textless_both_others` | the structural diff is absent; the metadata and the instruction parse both observed the unit |
| `textless_metadata_only` | the structural diff is absent; the metadata observed it; the instruction parse is absent or unavailable |
| `textless_instruction_only` | the structural diff is absent; only the instruction parse observed it |
| `both_others_silent` | the structural diff observed it; the metadata and the instruction parse are both absent |
| `metadata_silent` | the metadata is absent; the instruction parse observed it or is unavailable |
| `instruction_silent` | the instruction parse is absent; the metadata observed it or is unavailable |

An `unavailable` signal never makes a reason, as it never makes a dispute. The three `textless_`
codes are the changes with no text on either side, since the structural diff is the only signal
that carries any. `textless_instruction_only` is not produced by a current run, which publishes a
unit only the instruction parse names in `corroboration.instruction_only_units` rather than as a
change, and it is kept so that an older document read again still gets a code. A reason is a
reading of stored verdicts and says nothing about the law. **Adding it is not a schema bump**:
the field has a default reading, derived from data every document already carries, and its
absence from an older document means nothing a consumer has to interpret, so `schema_version`
did not move for it.

`schema_version` is `1.3`. It moved there on 2026-10-16, when a change gained `table_entries`:
the keyed diff of the rows of the unit's profiled tables, computed by the structural diff beside
the text comparison and carried through corroboration, explanation and the gate untouched.
**`null` means the entries were not read**, because no profiled table sits in the unit on either
side or because the document was written before this version; a delta with no `changes` means
they were read and no keyed entry moved. That reading of absence is the bump, as it was for
`evidence`: a consumer taking a missing delta for "no row changed" would be wrong about every
document published earlier and about every unit nobody profiled.

| `table_entries` field | Meaning |
|---|---|
| `tables[]` | the unit's profiled tables, the newer version's where both have one, then any only the older had; each with `unit`, `container`, `table` (1-based ordinal within the container), `key_label` (`null` when the key is the entry's name) and `header`, its header rows |
| `changes[]` | one row per keyed entry that differs: `kind` (`added`, `removed`, `amended`), `container`, `table`, `key`, `occurrence`, `typography_only`, and the entry `before` and `after` (`null` on the side the entry does not exist on) |
| `changes[].before`, `changes[].after` | the entry as read: `key`, `occurrence`, `group` (the verbatim heading of the block the rows sit in), `rows`, `identifiers` (`scheme` and canonical `value`, check-digit valid only), `failed_check_digits` and `name` |
| `unchanged` | paired entries equal verbatim |
| `whitespace_only` | paired entries equal once every cell passes the comparison normaliser: counted, and **not changes**, for the reason the comparison text exists at all |
| `unpaired[]` | keys printed a different number of times on the two sides, as `container`, `table`, `key`; none of their rows is diffed |
| `gaps_before`, `gaps_after` | per side: `unrecognised_tables` (profiled positions whose header did not match, never read), `unkeyed_rows` (entries with no key, never paired), `failed_check_digits`, and `repeated_keys[]` (every key one table prints more than once) |

**Cells are verbatim and uncapped.** A `rows` entry is one table row as the markup holds it, one
value per grid column: the cell's text exactly as stored, or `null` where the row has no cell of
its own at that position because a span from another cell covers it. Nothing is joined, trimmed
or normalised, and no cap applies: the evidence is the whole row. Two entries are **amended**
when their `group` or `rows` differ; equal once whitespace collapses is `whitespace_only`; and an
amendment that is equal once spacing, dash forms and accents are set aside (NFKD, combining marks
dropped, every hyphen and dash form and the minus sign read as `-`, all whitespace removed) is
labelled `typography_only: true`. The label never removes a change: a character swap in legal
text is a difference, and only whitespace is exempt from being one.

**Pairing is by key, and by occurrence where a table prints a key twice.** Entries pair on the
table and the key, where a table is told by its container's path below the unit and its
ordinal, so a renumbered unit still pairs its tables with the ones it had under its old number;
when both versions print the key the same number of times, the first pairs with the first and so
on, and a key printed more often on one side than the other goes to `unpaired`. Unkeyed rows are never paired. `changes` are sorted by the table's position in
`tables`, then by the key in natural order (digit runs compare as numbers, so `5` before `46a`
before `68`), then by occurrence, and two runs over the same versions produce identical bytes.
A unit inserted whole lists every keyed entry as `added`; one deleted whole lists each as
`removed`.

**The model never sees it.** The delta is not in the explain prompt and not in any cassette key,
so no explanation changed when the field arrived, and the citation gate reads none of it. It is
deterministic detail beside the verbatim texts, like `changed_within`.

**In the Markdown it is one line** under the change, counting and naming the moved entries:
`Table entries: 38 added, 4 amended (1 only in spacing, dash forms or accents), 0 removed: Index
No 603-148-00-X, ...`, the first ten keys in the delta's own order, each with its table's key
label or, where the key is the entry's name, the name in quotes, then `and N more`. The
parenthesis appears only when it counts something; a delta with no changes reads
`Table entries: none changed.`, and a change whose field is `null` has no line at all.

**Size.** Measured on 2026-10-16 over every consecutive pair of cached versions of the eight
profiled acts, the largest `table_entries` a single change carries is 4 700 505 bytes at the
payload's indentation: CLP `32008R1272`, the original text to the consolidation of 2010-12-01,
Annex VI, 1 527 entries added and 1 152 amended (3 of them typography alone). The next is the
re-typesetting of 2019-07-26 to 2019-12-01, 3 353 231 bytes, where 1 594 rows moved in
whitespace alone and are counted rather than carried; the same transition measured 5.77 MB
before that rule. Outside CLP the largest is REACH Annex XVII at 2 142 840 bytes, where the
consolidations of 2015-05-13 and 2015-06-01 carry no annex at all, so the structural diff
deletes and re-inserts the annex and the entry diff lists its 1 698 entries as removed and then
as added, exactly as the tree diff reads the same two packages; then PIC Annex I at 635 927
bytes. Every other unit of every other act stays under 0.6 MB.

`schema_version` moved to `1.2` on 2026-09-05, when a document gained `evidence`: one
record per change saying what its explanation was written about, as
`sha256` over the change's canonical location and its two verbatim texts, in that order,
NUL-separated and UTF-8 encoded, with an absent side tagged apart from an empty one. **A missing
record means the provenance is unknown, never that the evidence is unchanged**, and that reading
is the bump: adding a field with a default would not have been one.

The field exists because of the one asymmetry in this pipeline. Every stage except the model call
is a pure function of stored inputs and can be rebuilt at will; an explanation cannot, being a
paid, non-repeatable call written *about* a particular pair of verbatim texts. Two extractor fixes
(2026-08-12 and 2026-09-01) moved stored text after most of the corpus was written, and with no
record of what the writer was shown, the only way to ask which explanations went stale was to
re-parse the whole corpus and diff it against every payload. The digest turns that into
arithmetic: derive it again today and compare.

**No entry is ever retro-fitted with one.** The digest records what one call was shown, so it is
written by the run that made the call and carried over untouched by any repair that does not
re-ask; a repair that does re-ask about one change records that one and leaves every sibling
exactly as it found it. The 5 261 changes published before 2026-09-05 carry none and never will,
because deriving one from a payload's stored texts would assert that a call nobody witnessed was
shown them. `scripts/validation/evidence_staleness.py` answers the staleness question for those by
comparing their stored text against today's parse, and counts the two bases apart.

**A digest that survives a correction is what makes the next one cheap.** Where an entry's own
record proves its sentences were written about the text today's parser produces, a stored text
that has since drifted from it is a stale document rather than a stale explanation: the text is
corrected and nothing is asked or paid for. That case is counted apart from the re-asked, and it
exists only for entries written from 2026-09-05, the ones that carry a digest at all.

The digest is over the evidence and not over the prompt: a reworded instruction, a moved date in
the header or a renamed citation key does not make a shipped sentence describe text that is no
longer there, and a changed verbatim text does. It is over the uncapped texts, because how much of
them a prompt shows is a setting of the run rather than a property of the change.

`schema_version` moved to `1.1` earlier the same day, when `counts.substantive` stopped
covering a touched unit that carries no text on either side. Such a unit was named by the corpus
metadata or by an amending act's instructions and never seen by the text comparison, which is the
only signal carrying any text, and it now has a bucket of its own: `counts.textless`. The three
buckets `substantive`, `date_only` and `textless` sum to `touched`. Adding the field would not
have been a bump, since it has a default; re-meaning `substantive` is one, because a consumer
summing it with `date_only` to get `touched` was right before that date and is wrong after it.

Documents written before any of these moves say `1.0` and stay valid, so a reader of the corpus
meets all four versions. One read under the newest schema reports `textless` as 0, the wider
`substantive` its own run computed, no evidence and no table entries at all, which is the older
question answered under the older name; the counts are corrected when something rewrites the
entry, by the same rule the rest of this page states and never in bulk, and the missing
provenance is never corrected at all.

## The index

Every commit the writer makes also carries a current index, two files that let a program see what
a changelogs repository holds without downloading every payload:

```
<repo>/index.json                    one row per act holding at least one entry
<repo>/eu/32017R0745/index.json      every event of that act, and every row of every provision
```

Both are rebuilt in the same commit as the entry they describe, so any commit of the repository is
self-consistent: the index it holds is the one its payloads produce. Only the act being written is
rebuilt from its payloads; every other act's index is read as it stands, and is built from its
payloads only when it has none, so the first write into a repository that predates the index
indexes every act in it. Both files are indented JSON ending in a newline, every list
in an explicit order, and two builds over one tree are byte-identical.

**The index carries no provision text, no timestamp and no licence.** The text is what the payload
is for; a generation timestamp would make two builds of one record differ, and a file cannot hold
the hash of the commit that contains it, so freshness is `updated_on`, a date the payloads already
hold. Both files carry `index_schema` and the not-legal-advice `disclaimer`. Every value is read
off a payload validated through the same model the writer uses, never off its raw keys, so a field
the model computes is filled for every row whether or not the file stores it.

The root, `index.json`:

| Field | Meaning |
|---|---|
| `index_schema` | the index format's version, `1.0` |
| `disclaimer` | not legal advice |
| `acts[]` | one row per act, sorted by `(corpus, key)` |
| `acts[].corpus`, `acts[].key` | the act's identity |
| `acts[].title` | the newest entry's title for the act |
| `acts[].index` | the act index's path relative to the repository root |
| `acts[].index_sha256` | hex sha256 of that file's bytes, so a consumer can tell it moved without fetching it |
| `acts[].events` | how many entries the act index lists |
| `acts[].changes` | how many provision rows it lists |
| `acts[].provisions` | how many distinct top-level provisions those rows name |
| `acts[].disputed` | how many of those rows are `disputed` |
| `acts[].newest_version` | the newest entry's `to_version` |
| `acts[].newest_in_force` | the latest in-force date the newest entry reports, or `null` |
| `acts[].first_detected_on` | the earliest `detected_on` over the act's entries |
| `acts[].updated_on` | the latest `updated_on` over them |

An act index, `<corpus>/<act>/index.json`, has `index_schema`, `disclaimer`, `corpus`, `key` and
`title` as above, `events[]`, one row per payload with the newest first, and `provisions`, keyed by
the canonical top-level location (`AR 5`, `AN III`) with the keys sorted. "Newest" is the entry
key, the slug of `to_version`, compared descending, the order `CHANGELOG.md` is kept in.

| Event field | Meaning |
|---|---|
| `to_version`, `from_version` | the transition; `to_version` is the event's identity |
| `detected_on` | the date the run observed the event |
| `in_force` | the in-force dates its changes report, sorted |
| `updated_on` | the latest of `detected_on` and every repair's `repaired_on` |
| `schema_version` | the payload's own schema version, which is independent of the index's |
| `path` | the payload's path relative to the repository root |
| `sha256` | hex sha256 of the payload's committed bytes |
| `diff_only` | whether the payload was written with no model stage |
| `counts` | the payload's own `counts`, as stored |
| `repairs[]` | each repair the payload records, as `kind` and `repaired_on`, in its order |
| `evidence` | whether the payload carries any evidence digest |
| `metadata_only_units` | units only the corpus metadata names, copied from the payload's `corroboration`; empty when it has none |
| `instruction_only_units` | units only the instruction parse names, copied the same way; these are published by name and are not changes |

Each provision maps to its rows, newest event first, then by `occurrence`:

| Row field | Meaning |
|---|---|
| `version` | the `to_version` of the event the change belongs to |
| `change_type` | the change's type as the structural diff named it |
| `previous_location` | the location a renumbered provision had before, else `null` |
| `disputed` | whether the three signals disagree about the change |
| `dispute_reason` | the code from the table above, filled for every disputed row whether or not the payload stores the key, `null` exactly when `disputed` is false |
| `signals` | `structural_diff`, `corpus_metadata`, `instruction_parse`: each `observed`, `absent` or `unavailable` |
| `text` | which verbatim sides the payload carries: `both`, `before`, `after` or `none` |
| `in_force` | the change's in-force date, or `null` |
| `applies_from` | an ISO date when the payload holds one, else `unknown` or `unchanged` |
| `dates_added`, `dates_removed` | dates the provision carries after only, and before only |
| `outcome` | how the change left the citation gate |
| `unexplained_kind` | the counted kind of a missing explanation, or `""` |
| `amending_acts` | keys of the acts a signal names as amending the provision |
| `changed_within` | canonical sub-provision coordinates whose text differs |
| `occurrence` | which repeat of this location within its event, counted from 1 as the site counts it for the change's anchor |

**Corrections.** A repair goes through the same writer, so the index moves in the repair's own
commit. A repaired event gets a new `sha256`, a later `updated_on` and one more `repairs` row, and
its act's root row moves with it. A change a repair withdraws disappears from `provisions`, and its
event's `sha256` and `updated_on` move: the index is a function of the tree as it stands, so it
cannot say "withdrawn", and the git history of the repository is the record of what was there. A
consumer that caches rows keys them on `(act, version, location, occurrence)` and re-reads an event
whenever its `sha256` moves. That is the whole correction protocol.

**Versioning.** `index_schema` follows the payload rule: a field added with a default is a minor
bump and stays at `index.json`; a field removed, renamed or re-meant is a breaking change, and one
writes `index.v2.json` beside the old file for an announced period, because a consumer pins a path
and cannot be told to move.

**`emendrix index rebuild [--output-repo PATH] [--dry-run]`** rebuilds every index file from the
committed payloads and commits the ones whose bytes moved, in one commit with the subject `index the
repository`. It indexes a repository written before the index existed without waiting for its next
entry, and it is how an act index that was edited by hand or left stale is put right: the writer
reads other acts' indexes as they stand and would carry a wrong one into the root, and it never
re-verifies them, since that would rebuild the whole repository on every write. The repository is
`--output-repo`, else `EMENDRIX_OUTPUT_REPO`, opened with the same two refusals as the writer. It
reads no network and no clock and needs no date; a second run commits nothing, and `--dry-run`
prints which files would change and their sizes and writes nothing. History-level work on a
changelogs repository, such as a re-root or a fast-forward, must run `emendrix index rebuild` inside
the same window in which the poller is suspended.

## The register

A payload holds only what changed, so it cannot say where an identifier appears today: an entry
nobody amended since the first version the record holds is in no payload at all. For an act whose
tables are read as entries, the repository therefore also holds the act's **register**, the
newest version's whole reading, cells verbatim:

```
<repo>/eu/32008R1272/register.json   every table entry of the newest version the record holds
```

It is written in the same commit as the act's newest entry, and only when the entry is the
newest: an older entry written later, as a backfill writes them, leaves a newer register where it
is, and re-emitting identical bytes commits nothing. `emendrix backfill` writes entries without
one; `emendrix repair tables` writes each profiled act's register from its newest published
version, one commit per act, after bringing the act's entries up to `1.3`. It is the newest
version's list and never a diff or a history: the history of an entry is in the payloads'
`table_entries`, and the register's own history is the repository's.

| Field | Meaning |
|---|---|
| `register_schema` | the register format's version, `1.0` |
| `disclaimer` | not legal advice |
| `corpus`, `key` | the act's identity |
| `version` | the version the entries were read from, the `to_version` of the act's newest entry |
| `tables[]` | every table read as entries, in document order, as in `table_entries.tables` |
| `entries[]` | every entry, in document order (table position, then row order), with the fields of `table_entries.changes[].before`, plus `unit`, `container` and `table`; unkeyed rows are kept with `key: null`, so their identifiers are still listed |
| `unrecognised[]` | profiled table positions whose header did not match, as `unit`, `container`, `table`; never read |
| `coverage` | over the whole reading: `unrecognised_tables`, `unkeyed_rows`, `failed_check_digits`, and `repeated_keys[]` (each key one table prints more than once, listed once, where its second print stands) |

Like every derived file of the record it is indented JSON ending in a newline, with no timestamp,
and two builds over one version are byte-identical. **Cells are kept**, because without them a
reader cannot show the row an identifier appears in. Measured on 2026-10-16 over the newest
version each profiled act had published by 2026-10-08, read from the local cache: CLP 8 196 241
bytes (8 642 entries), REACH 2 043 737 (2 086), Cosmetics 1 896 414 (2 425), PIC 469 190 (731),
plant protection products 103 723 (156), POPs 80 613 (63), Biocides 20 327 (31). A size says
how many rows an act prints, nothing about how much of the law changed. The register's schema is
committed as [`./schema/register.schema.json`](./schema/register.schema.json).

**A register says where an identifier appears, never whether a substance is regulated.** A
group entry names no identifier, so an identifier no entry carries is not thereby outside the
act.

A rendering of these artifacts as a browsable site is in [`./site.md`](./site.md).
