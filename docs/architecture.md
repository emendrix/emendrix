# Architecture

How the code is layered, what the seam between the generic core and a body of law is, and why a
graph framework assembles a near-linear pipeline. Start at [`../README.md`](../README.md) for what
emendrix is and how to run it.

## The shape of the code

Eleven layers exist: the vocabulary, the EU adapter (retrieval *and* parsing), the structural
diff, reachable from a command line, the corroborator that holds it against two independent second
opinions, the eval harness that scores all three over a committed corpus, the watcher that notices
an amendment in the first place, the one stage where a model is allowed to speak, the
deterministic gate that decides whether what it said may ship, the graph that assembles all of it
into the loop, the changelog the loop exists to produce, and the static site that publishes a
rendering of it.

`emendrix.core` is the typed vocabulary of the whole system (provision locations, provision trees,
versions, changes, citations, the two clocks and the first-class states), and it is deliberately
sealed: pure Python and pydantic, with no I/O, no network, no clock read, no model call and no
knowledge of any particular body of law. Everything else imports it; it imports nothing back.

Two contracts in it are worth knowing before reading any other module:

- **A provision location is a string.** `AR 5 PA 1 ALN 1 PTA (bb)`, `AN III`: a path of
  `(code, value)` segments that parses and serialises round-trip, sorts deterministically, and
  answers containment (`AR 5` contains `AR 5 PA 1`). It is the identity a change is keyed by, and
  the top-level segment is the unit changes are counted at. Codes outside the known vocabulary are
  carried as `UNKNOWN(…)` and counted, never dropped and never raised on.
- **`CorpusAdapter` is the entire seam** to a body of documents: discover versions, fetch one, parse
  an amending document, render a citation. Four methods, nothing else. A second implementor keeps
  it honest: `tests/toy_corpus.py`, a flat's house rules, which is not law at all.

Provision text is stored **twice**: verbatim, which is what output quotes and is never normalised,
and a separate comparison form built during extraction. That is not redundancy: collapsing
whitespace after the fact cannot recover an element boundary that extraction never emitted, and on
one real version pair that mistake reported every article in the act as modified.

## The EU adapter

`emendrix.eu` implements that seam for EU legislation, and owns **all** the network access in the
project: `eu.http` is the only module that constructs an HTTP client, and every response it gets
passes through the disk cache in `eu.cache`. Retrieval is by identifier, CELEX or consolidated
CELEX, with the act's own *tree notice* as the routing table, because which URL answers depends on
the age of the document and no single scheme covers everything.

Three things it refuses to do:

- **It does not raise where the corpus gave an answer.** A consolidated version with no English
  text, a version with no structured text at all, a version that has not been consolidated yet:
  each is a value that flows to the output and gets counted, not an exception. Asking for the AI
  Act's first consolidation in English falls back to the act as published in the OJ, and the
  package it returns says so (`fell_back`, `served_version`), because a fallback that is not
  visible is a lie.
- **It does not guess a link.** Provision-level ELI URIs 404; citations render as EUR-Lex HTML
  anchors, whose vocabulary (`#art_5`, `#art_4a`, `#anx_III`) was read off the published rendition
  rather than assumed. Where the corpus publishes no anchor, a title or a recital, the citation
  points at the document and the label still says exactly where.
- **It does not read a clock.** The observation date stamped on every state is passed in from the
  CLI boundary. The one wall-clock read in the package records when a response was fetched, and
  `tests/test_architecture.py` fails the build if a second one appears anywhere.

`emendrix.eu.formex` turns the retrieved markup into provision trees. The structured format is
**Formex 4**; no AKN4EU manifestation exists for these acts. Its nesting maps onto the same
location vocabulary the corpus uses for its own amendment metadata, so `<ARTICLE IDENTIFIER="004A">`
becomes `AR 4a` and a lettered point inside a paragraph becomes `AR 5 PA 1 ALN 1 PTA (bb)`. The
parser also recovers what amending prose leaves out: EU drafting writes *"the following Article is
inserted:"* without the number, and the number is in the quoted `ARTICLE` element.

Every element the parser's vocabulary does not know is walked through, counted into a
`ParserCoverage` report, and its text still reaches the enclosing provision: a coverage gap is a
number, never a crash and never a silent drop. Those numbers are asserted per document, so
degradation on a 2006-generation act shows up as a failing test rather than as a worse changelog.

Test documents are pinned from the corpus by identifier and committed under `tests/fixtures/eu/`
with a manifest recording each one's URL, digest and how it was trimmed. They are refreshed by

```bash
uv run python -m emendrix.eu.fetch_fixtures --list   # what is pinned, and why
uv run python -m emendrix.eu.fetch_fixtures          # re-pin (network; a no-op when cached)
```

and nothing in them is hand-written, including the ground truth, which is why the test suite can
assert numbers that were measured independently by
[`../scripts/validation/`](../scripts/validation/).

Most of that set is not hand-listed either: the eval corpus writes the documents it needs into
`tests/fixtures/eu/eval_pins.json` and the fetch script pins the union. It comes to about 10 MB,
which is a deliberate choice: priming a cache in CI instead is smaller in the repository and
mysterious everywhere else, because the published numbers would then rest on documents nobody
could see.

## The structural diff

`emendrix.diff` is the `DELTA` stage: two provision trees in, one typed `Delta` out. It imports
`emendrix.core` and the standard library and nothing else, so it runs unchanged on the toy corpus,
which is what keeps the seam honest rather than merely declared. Three passes, all deterministic:

- **The unit pass** matches top-level provisions by location and compares their comparison forms:
  present only after is `INSERTED`, only before is `DELETED`, present in both and different is
  `MODIFIED`. This is the algorithm that agreed with the corpus's own amendment metadata on the AI
  Act at F1 = 1.000, and the numbers it produces are asserted in `tests/diff/`.
- **Localisation** descends a changed unit and reports the coordinates whose *own* text moved, so a
  change lands on the unit `AR 113`, with `AR 113 ALN 3 PTA (c) PTI (i)` as detail beside it.
- **The date reader** is the second clock. A unit whose only differences sit inside dates that
  moved, and which gained exactly one date, is `DEFERRED` with that date; anything else reports
  `unknown` with the dates recorded as detail. On the MDR's one-year postponement that reads six
  deferrals cleanly; on the AI Act's Article 113 it reports `unknown`, because four dates moved and
  the prose changed around them. **Many unknowns is the intended outcome**: what a date binds is
  natural language, and nothing here guesses at it.

Renumbering is detected between leftover insertions and deletions, and capped on purpose: a
provision that both moved and was rewritten stays a deletion plus an insertion, and no attempt is
made to rewrite the cross-references a renumbering breaks. No renumbering has been seen in any
traced transition, so that path is exercised on crafted toy trees and honestly labelled as
unvalidated against real law.

Output is byte-stable by construction, because changelogs are diffed in git: the emission order is
the new version's document order with deletions interleaved at their old anchor.

```bash
uv run emendrix diff 32024R1689 32024R1689 02024R1689-20260727        # the flagship transition
uv run emendrix diff 32017R0745 02017R0745-20170505 02017R0745-20200424 --json
uv run emendrix diff 32017R0745 02017R0745-20170505 02017R0745-20200424 \
    --fixture-dir tests/fixtures/eu                                   # offline, no network at all
```

A version is named the way the corpus names it: `32024R1689` is the act as published in the Official
Journal, `02024R1689-20260727` a consolidation. The command prints a plain structural dump, the
serialised `Delta` with `--json`, or the changelog entry with `--markdown`. The last of these is a
first-class product mode rather than a preview: the deterministic half of the loop is the half with
measured numbers behind it, and it calls no model and needs no API key.

The two second opinions the diff is held against are in
[`./evaluation.md`](./evaluation.md); the stages that run after it are in
[`./pipeline.md`](./pipeline.md).

## Why a graph framework on a near-linear pipeline

The loop is orchestrated by a LangGraph `StateGraph`
([`../src/emendrix/graph/`](../src/emendrix/graph/)). The honest position is that this is a
*near*-linear pipeline and a graph framework is not obviously required for one, so here is what it
buys and what it costs.

It buys three things. **A state with a shape:** every stage's half-result (the fetched trees, the
delta, the corroboration, the explanations and the gate verdicts) lives in one validated pydantic
model that LangGraph checks at every node boundary, instead of accumulating as a growing tuple
threaded through function signatures. A node that writes nonsense fails at that node rather than
three stages later. **A real cycle:** `gate → explain → gate` is a loop with a bound, and it is the
only branch in the graph; expressing "ask again, once, with this complaint attached" as an edge with
a counter is more legible than the same thing as a flag inside a straight-line function, and the
bound is one line (`after_gate`) that a reviewer can check. **Resumability:** a run's expensive part
is the fetch, and a checkpointer means a process that dies after it resumes without re-fetching,
exercised rather than asserted in
[`../tests/graph/test_resume_cycle.py`](../tests/graph/test_resume_cycle.py), which interrupts after
each stage in turn and requires the finished report to be byte-identical to an uninterrupted run's.

It costs a dependency and a vocabulary. A reader who knows Python but not LangGraph has to learn
what a compiled graph, a conditional edge and a checkpointer are before they can follow the control
flow, and that is a real tax on a project whose second goal is readability. Two things keep it
bounded. `langgraph` is imported in **exactly one module**, `graph/build.py`, grep-enforced by
[`../tests/test_architecture.py`](../tests/test_architecture.py), so everything else in the package
is ordinary Python the tests call directly, and dropping the framework would mean rewriting one
file. And only its stable core is used: `StateGraph`, conditional edges, a checkpointer. No `Send`
fan-out (per-change concurrency already exists inside the explain stage's semaphore, and two
concurrency models for one effect is one too many), no prebuilt agents, no tools, no interrupts
outside tests. If a feature cannot be justified in one sentence, it is not there.

What it emphatically does **not** buy is agency. Every node except `explain` is a deterministic
function, and every node is a ≤20-line adapter that reads a field, calls a function the package
provides independently of the graph, and writes the result back, a rule the architecture test
enforces by length, because logic arrives in a node as extra lines. The one decision the graph makes
is arithmetic: *is a revision still owed?* Nothing in `graph/` decides anything about a document.
