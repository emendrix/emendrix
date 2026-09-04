# The pipeline, stage by stage

What each stage of `WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → GATE → EMIT` does, in loop
order, and how to run the whole thing. Start at [`../README.md`](../README.md) for what emendrix is
and how to install it; the layering behind these stages is in
[`./architecture.md`](./architecture.md).

The `DELTA` stage is described with the rest of the deterministic core in
[`./architecture.md`](./architecture.md), and `CORROBORATE` in
[`./evaluation.md`](./evaluation.md), because both are best read beside the numbers measured over
them.

## Watching: boring, stateful, resumable

`emendrix.watch` is the `WATCH` stage, the least glamorous part of the system and the one most
likely to be where a production bug lives, so it is the one with the most paranoid tests.

You name the acts you care about in a TOML file
([`../watchlist.example.toml`](../watchlist.example.toml)), and the poller reads the Publications
Office's own notification feed over a date window, filters it to those acts, and emits typed
events.

```bash
cp watchlist.example.toml watchlist.toml
uv run emendrix watch --once                          # since the last successful poll
uv run emendrix watch --once --since 2026-08-05       # or from an explicit date
uv run emendrix watch --loop --interval 86400         # a while/sleep; use cron instead
```

Four facts about that feed shape the code, and all four were verified against the live endpoint:

- **The channel segment is mandatory**: `/webapi/notification/` alone is a `404`. Consolidations
  of watched acts arrive on the `ingestion` channel; the AI Act's Digital Omnibus consolidation
  appeared there on 2026-08-05, twelve days after the amending act was published.
- **The Atom is a decoy.** Every entry's `<title>` is the literal string `$item.title` and every
  `<link href>` is `$item.cellarUri`, unrendered Velocity template variables. A generic feed
  library reads those as a title and a link and is confidently wrong, so `emendrix.eu.feed_atom`
  reads the `notifEntry:` extension namespace by hand and `feedparser` is banned package-wide by
  `tests/test_architecture.py`.
- **It is a firehose with a rare signal**: ~3,000 notifications a day, of which a watchlist hit is
  a handful, and the *same* consolidation is re-notified every few minutes for hours. So there are
  two dedupe layers: by entry identity, which makes overlapping windows free, and by what an entry
  resolved to, which is what turns 46 notifications of one amendment into one event.
- **Consolidation lags publication by ≈10 days.** "Amended, but there is no text yet" is therefore
  a first-class state: `ConsolidationPending` is emitted once, written into the state file,
  re-checked on every later poll, and emitted once more, as an ordinary version event, when the
  text appears. Never a retry loop, never an exception.

The state file (seen entries on a rolling 60 days, the window cursor, the pending list) is written
by write-tmp-and-rename, so a process killed mid-write leaves the previous state intact; a corrupt
or foreign-schema file is moved aside and the poll starts from `--since` rather than dying. The
cursor advances even when a window holds nothing, because a window that re-scans forever is one way
this kind of program fails, and it stops short when the feed was not read to the window's end,
because stepping over notifications nobody fetched is the other. `poll_once` itself reads no clock
at all, the window is a value handed in at the CLI boundary, which is what lets the tests assert
idempotency honestly:

```bash
uv run emendrix watch --once --since 2026-08-05T10:00:00 --until 2026-08-05T10:05:00 \
    --watchlist watchlist.toml --fixture-dir tests/fixtures/eu    # offline, no network at all
```

Those five minutes are a pinned fixture: a real, unedited feed page, Velocity garbage and all,
holding 46 notifications of which 4 are the AI Act. `emendrix watch` prints those events;
`emendrix run` feeds them into the rest of the loop.

## Explaining: the one place a model is allowed to speak

`emendrix.explain` is the `EXPLAIN` stage, and it is the only module in the package that calls a
model. `pydantic_ai` may be imported there and nowhere else, grep-enforced, like everything else on
that list.

What the model gets is deliberately narrow: two verbatim texts already known to differ, the change
type as an established fact, the two clocks, and a list of citation keys. What it may return is a
type:

```python
class CitedSentence(BaseModel):
    text: str
    citations: tuple[str, ...]  # at least one, always


class Explanation(BaseModel):
    sentences: tuple[CitedSentence, ...]  # one to three
    applicability_note: CitedSentence | None  # a verbatim quote, or nothing
```

Three consequences follow from that shape, and they are the reason for it:

- **It cannot invent a link,** because there is no field to put one in. A citation is an opaque key
  the caller minted (`AR 4@02024R1689-20260727`), so the gate's check (did every key it cited come
  from the set it was offered?) is a set operation on strings rather than a judgement about
  content. That is the anti-hallucination invariant, and making it structural is what makes it
  cheap.
- **It cannot decide anything.** No field carries a change type, a location, a date or a
  classification; all four arrive as typed input and leave untouched. A model that hallucinates
  here can only produce a *worse sentence*, never a wrong changelog.
- **It cannot pad.** Three sentences is a schema constraint, not a request in prose.

The prompt is a literal string in
[`../src/emendrix/explain/prompt.py`](../src/emendrix/explain/prompt.py), reviewable in git and
snapshot-tested in full, because a prompt is the specification of the only non-deterministic step
in the loop. Long provisions are capped by character count and the cap is *visible*: a marker in
the text the model sees and a count in the run statistics.

Failure is a value, as everywhere else: a provider error yields `ExplanationUnavailable` on that one
change and the other forty-four still ship. The same applies to a change with nothing *to* explain.
Corroboration appends one per unit that another signal named and the diff did not, and since the
diff is the only signal carrying text (33 of REACH's 41 changes are disputed, one of them
textless), those reach this stage with no quotable text at all. They keep their slot, carry the
reason, and never raise. Token usage is a field, not a log line, because cost control is a stated
goal of the project: at the pinned model's published rates the whole 55-change explanation subset,
of which the AI Act's flagship delta is 45 changes, cost **$1.0197** to explain end to end over
404 846 input and 20 998 output tokens, measured over the recording of 2026-08-12 and printed in
[`../reports/eval/2026-08-12-4f9a9c0.md`](../reports/eval/2026-08-12-4f9a9c0.md).

**Cassettes.** Every exchange is recorded as JSON on disk under `tests/cassettes/`, keyed by
`sha256(model_id + system + user + schema_version)`, with the prompt stored beside the answer so a
reviewer can re-derive the key by hand. There is no VCR and no HTTP interception: the wrapper sits
at the explain-call boundary, so a cassette is a readable record rather than a replay of a wire
format nobody will open. CI runs replay-only: a prompt nobody recorded fails loudly naming the file
it wanted, and no provider client is ever constructed, so the stage genuinely reads no API key.

```bash
# regenerate the pinned cassettes (offline → synthetic; with a key → the pinned model)
uv run pytest -m "record and live" tests/explain    # reads OPENROUTER_API_KEY if set
```

The model is pinned to `openrouter:anthropic/claude-sonnet-5`, reached through OpenRouter so that
one key and one account cover every provider a reviewer might want to compare against, and is
configurable with `EMENDRIX_MODEL`. The identifier and its pricing were read off OpenRouter's own
`/api/v1/models` on 2026-08-08 ($2.00 / $10.00 per 1M tokens) and the check is written down in
[`../src/emendrix/explain/settings.py`](../src/emendrix/explain/settings.py).

That is a mid-tier model and not the cheapest one on offer, and the argument for the cheapest one
is worth stating because it is the argument this project measured and rejected: localisation,
classification and citation validity are all decided by deterministic Python on either side of
this call, so capability buys phrasing and nothing else. A hand review of twenty shipped
explanations on 2026-08-08 found that wrong. Five of the seven failures it found were failures of
the explainer's reading rather than of its phrasing, three of them stating a legal conclusion the
text does not carry and one describing text past the truncation marker. Those are capability
failures, which is why the tier sits where it does, and the whole check is written down in the
settings module linked above.

**All four cassette sets were recorded against that pin on 2026-08-12**, at a character cap high
enough to show whole provisions and over stored text that does not run words together across block
boundaries, so every model-layer figure describes Sonnet 5 reading whole provisions as the source
document lays them out.

Credentials come from the environment. `.envrc` is committed and holds no secret; it sources
`.envrc.local`, which is gitignored and is where `OPENROUTER_API_KEY` goes:

```bash
cp .envrc.example .envrc.local   # then put your key in it
direnv allow
```

Nothing in CI reads any of this: the pipeline replays committed cassettes and never constructs a
provider client, so it has no key to read.

> **The committed cassettes were recorded against the pinned model on 2026-08-12**, and each one
> says `"synthetic": false` in its own JSON. Run the command above without a key and it records
> from pydantic-ai's `TestModel` instead, marks every file `"synthetic": true`, and that flag
> rides into `RunStats.synthetic` and withholds the faithfulness rate outright. The same command
> either way, so it is impossible to think you recorded against a real model and be wrong.

## Gating: a claim without a resolvable citation does not ship

`emendrix.gate` is the second half of the sentence this project is built on. The model may phrase
a difference; nothing it phrases reaches a reader until deterministic Python has confirmed that
every citation it carries points at a provision that was actually in front of it.

The check is three questions and no judgement. Does the citation key **parse**; does it **resolve**
to a real provision in the version it names; and is it **contained in** the set that was offered to
the model for this change. In this implementation the first two collapse into one lookup, and that
is a strengthening rather than a shortcut: a citation is not a syntax the model composes, it is an
opaque token the caller minted, and the model has no field to put a URL in. So "does it parse" is
exactly "is it one of the tokens offered", and behind every offered token is an already-parsed
`ProvisionRef`. Resolution runs against the two trees the run already fetched: no network, no
clock, no second construction of the offered set to drift from the first.

Failure is bounded and never silent:

1. **One retry**, carrying the specific complaint (which sentence, which key, and why it was
   rejected) with the offered keys still in front of the model. Not a second opinion: a correction.
2. **Then a verbatim quotation** of the provision's own text, which is correct by construction
   because it *is* the provision. The substitution is flagged `fallback=True` and counted.
3. **Never a third attempt**, and never a dropped change.

Both halves of that promise are tested as *properties* rather than examples
([`../tests/gate/test_fallback.py`](../tests/gate/test_fallback.py)): over a grid of explanation
shapes and model behaviours, the number of changes coming out equals the number going in, and every
sentence in the output either passed the check or was written by the gate.

The `fallback` flag lives on the gate's own value type and deliberately **not** on the model's
output schema. A provenance field the model could set would let an invented sentence claim to be a
verbatim quotation.

**One further check, on the applicability note.** The note is optional prose the model may add,
and the prompt requires it to be a verbatim quotation of a statement in the after text. It is the
one piece of model prose that reaches a reader under a label the pipeline supplies
(`*Applicability:*`), printed beside a date the pipeline computed, so the gate tests it: the note
has to appear in the after text *as the model was shown it*, under the same whitespace
normalisation the diff uses, or it is dropped and counted (`GateStats.notes_dropped`). This is a
string containment test, not an opinion about the statement. It runs after the citation check, so
no citation count and no grounding rate moves with it, and it never spends the retry: a paraphrase
is prose the reader is better off without rather than a claim pointing at nothing, and the entry's
headline already carries `applies from:`. The check was measured on 2026-08-08 over a recording in
which two of the three notes the MDR postponement shipped were paraphrases; both happened to agree
with the computed date, which is luck rather than a check. What it has to show for itself in the
recording that ships is nothing: the run of 2026-08-12 writes no applicability note on any change,
the third recording in a row to write none, so `notes_dropped` is 0 because none was written rather
than because every one passed. That is in the known limitations of
[`../CHANGELOG.md`](../CHANGELOG.md) rather than softened here.

**One place resolves against an entry's own texts rather than against two trees.**
`emendrix repair explanations` rebuilds a prompt from a committed payload, which carries the
verbatim texts and no provision tree, so the gate is handed a resolver built from the provisions
that entry ships text for. Every key the model could legitimately cite is minted from those same
provisions, so an offered key resolves and a key from anywhere else is still rejected as unknown,
which is the check's whole strengthening and is unchanged. What the narrower resolver cannot do
is notice an offered key naming a provision the version does not actually contain, and it answers
"I was not given that" rather than "present" for anything else. The coordinate check does not run
there at all: the two support sets are computed from the trees, so the context carries
`coordinates_checked=False`, the gate counts nothing rather than counting every mention as
unsupported, and the repaired entry records that the check did not run.

**The gate has no opinion about whether a sentence is true.** A factually wrong sentence with a
valid citation passes, and it is supposed to. Whether what a sentence says follows from the texts
is *faithfulness*, measured separately against a different reference
([`./evaluation.md`](./evaluation.md)). Blurring citation grounding into explanation quality would
make the grounding number mean nothing, and a flattering metric in a project whose premise is
measurement is the one failure nothing recovers from.

## Running the whole loop

```bash
uv run emendrix run --once                  # poll the watchlist, then diff, explain, gate, emit
uv run emendrix explain 32024R1689 32024R1689 02024R1689-20260727   # one named transition

# offline, end to end: pinned fixtures for the documents, committed cassettes for the model
uv run emendrix explain 32017R0745 02017R0745-20170505 02017R0745-20200424 \
    --fixture-dir tests/fixtures/eu --json-out report.json
```

`run` enters the graph at `WATCH`; `explain` skips that node and supplies the event itself. Both are
the same graph after that, so the manual path cannot drift from the scheduled one. Output is the
typed `RunReport` as JSON: every change with its verbatim before/after, the sentences that survived
the gate, a rendered EUR-Lex citation per key, both stages' counts and the disclaimer as a field.
With an output repository configured, it is also a git commit
([`./output-format.md`](./output-format.md)).

A one-line summary of the counts goes to stderr, so the report on stdout stays parseable.
`--summary json` makes that line machine-readable, which is what an unattended deployment wants:
the report is too large to log (nine changes is roughly 200 kB, which a log collector either
splits into unparseable fragments or drops whole for exceeding its line cap), while the summary
is bounded by how many acts were amended rather than by how much changed in them.

```bash
uv run emendrix run --once --summary json     # counts on stderr as one JSON object, for logs
```

A new installation starts with an empty changelog and a watcher that looks fourteen days back,
which is the right window every day after the first and the wrong one on the first. `emendrix
backfill` is the other question: every consecutive pair of readable versions each watched act has
published, through the same graph, into the same repository.

```bash
uv run emendrix backfill --dry-run                            # what it would run; spends nothing
uv run emendrix backfill --output-repo ~/regulatory-changelog
uv run emendrix backfill --since 2023-01-01 --act 32017R0745  # narrower, and cheaper
uv run emendrix backfill --limit 20 --polite-delay 3          # one tranche, fetched gently
```

Start with `--dry-run`. It reads each act's version list, prints the transitions it would run and
the counts behind them, and builds no explain engine, so it needs no API key: a backfill of a large
watchlist is hundreds of model calls, and the count is worth seeing before any of them is made. A
version with no readable text does not end the chain; the pair steps over it and says which
versions it bridged, because "what changed since the last text a reader could see" is the question
worth asking. `--since` drops transitions whose later version predates the date, and one the corpus
does not date at all, because a cutoff is a promise about how far back a run reaches and an undated
version cannot honour it; with no cutoff set every pair is kept. `--act` filters the watchlist
rather than extending it: a CELEX that is not watched selects nothing and the total reads zero.
`--limit` takes the first N of what is left, oldest first, so history can be read in tranches; how
many the limit held back is printed rather than implied, because a cap nobody mentions reads as
"that was all of it".

**Nothing is paid for twice.** A transition whose entry is already in the output repository is
skipped, and that is decided by the file being there
(`<corpus>/<act>/changes/<version>.json`), not by any record the run keeps of itself. It is what
makes a backfill resumable with no resume mechanism, and it holds where a state file would not:
in a container that starts empty every time, or after the poller has already emitted the newest
transition of an act whose history you are now filling in.

Progress is *also* recorded in a ledger (`backfill-ledger.json`, `--ledger` elsewhere) after
**every** transition, and each finished transition prints a line carrying `[n/total pct%]` so an
operator can see how far along a long run is. The ledger answers what the repository cannot: what
failed and how often, and which transitions legitimately produced nothing to diff, neither of
which leaves a file behind. A run killed at 200 of 300 resumes at 201. The resume unit is one
whole transition: number 201 starts again from its first fetch rather than from wherever it died.
Its fetches come back from the disk cache and cost nothing, its model calls are paid again, and
nothing smaller than a transition is ever half-done.

A transition that produced an answer is settled. One that failed is retried on the next run,
because a failure here is usually a socket that closed rather than a verdict about a document, and
after `--retry-limit` tries (3 by default, `0` to keep trying forever) the run gives up on it and
says so on its own line.

Backfill is also the workload that most wants to be gentle with a public endpoint, so the delay
between network calls is reachable from outside the code: `--polite-delay`, or
`EMENDRIX_POLITE_DELAY_S` for every command (1 second by default; cache hits never sleep at all).
A value that is not a non-negative number is refused by name rather than quietly read as the
default.

Ctrl-C is an ordinary way to end a long backfill: the run prints the totals it earned and exits
`130`, and the transition that was in flight stays out of the ledger so the next run redoes it.

A run holds `backfill-ledger.json.lock` for its length, because two backfills sharing one ledger
quietly drop each other's finished transitions and pay for them twice. A second run is refused with
the path to delete if a killed process left the lock behind; nothing decides on its own that a lock
has gone stale. `--dry-run` takes no lock and writes nothing at all, so it can check on a run in
progress.

Unlike `run`, backfill **requires** an output repository. Three hundred typed reports on a terminal
are not an artifact anybody wants, and the absence is refused before the first fetch.
