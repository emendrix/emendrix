# Changelog

All notable changes to **emendrix itself** are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This is the changelog of the *tool*. The changelogs the tool *produces* live in an output git
repository of your own; `docs/output-format.md` describes the layout and the JSON schema.

Released versions link to their tag, and a first release has nothing to compare against:
[0.1.0](https://github.com/emendrix/emendrix/releases/tag/v0.1.0).

> Not legal advice: this output is machine-computed from published texts, carries no lawyer's
> review, and is engineering assistance only.

## 0.1.0 - 2026-08-13

The first release. emendrix watches EU legislation for amendments, computes what changed between
two consolidated versions, and emits a reviewable changelog into an output git repository you own.

### Added

- **The loop**: `WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → GATE → EMIT`, wired as a
  LangGraph `StateGraph` with a checkpointer. Every stage except `EXPLAIN` is deterministic Python:
  the model never decides whether something changed, which provisions are involved, or how it is
  classified.
- **`emendrix.core`**: the typed vocabulary, and the four-method `CorpusAdapter` protocol that is
  the whole seam to a body of documents.
- **The EU adapter**: a CELLAR client with a disk cache and the mandatory English fallback chain,
  a Formex 4 parser, modification metadata, instructions, the notification feed and citation URLs.
- **The structural diff and classification** into `core.Delta`, generic enough to run on a toy
  corpus that is not law at all.
- **Three-way corroboration**: structural diff × modification metadata × instruction parse.
  Signals disagree and the change ships marked `disputed`, never dropped and never merged away.
- **The explain stage**: pydantic-ai against a typed schema, at most 40 000 characters of each
  text with any cut visibly marked, and a cassette store so CI replays with no key and no socket.
- **The citation gate**: parse, resolve, containment; one retry; then a verbatim quotation of the
  provision, visibly marked as the gate's own words. An unquoted applicability note is dropped,
  and unsupported coordinates are counted.
- **The watcher**: a watchlist with an optional `domain` per act, a notification poller, and a
  seen-state cursor that survives a crash and re-runs a window safely.
- **`emendrix backfill`**: every consecutive pair of readable versions a watched act published,
  through the same graph. `--dry-run` prints the bill and spends nothing; `--limit`, `--since` and
  `--act` narrow it; an emitted transition is skipped.
- **`emendrix repair`**: the one command that reaches into entries already committed, to correct
  one part of one entry while every other entry in that act's changelog keeps its bytes. It is
  explicitly invoked and is never reached from a resume, because `holds_finished` treats a settled
  change as settled on purpose and a repair a backfill could trigger would re-address the same
  entries for ever. Four properties hold for every repair it carries and each is a test: an entry
  taken apart and put back unchanged re-serialises to the bytes it came from; repairing one change
  leaves every sibling's prose, citations and gate outcome byte-identical; an entry it does not
  actually change is not written, compared against the re-serialised original so that schema drift
  alone never counts as a change; and running it twice produces one commit. `corroboration` is the
  first repair on it: it recomputes the third signal from the amending act's own package, which is
  a cache read, calls no model and spends nothing, and it carries every committed explanation over
  rather than re-asking for it. `--dry-run` prints what would move, disputed flags flipped among
  it, and writes nothing at all. What a repair did is recorded on the entry as a `repairs` entry
  with the date it ran, beside an `explain` block that keeps recording the run that produced the
  entry: no repair retracts a call that was made, and summing the two would turn a record of one
  run into a lifetime total. The field has a default and `schema_version` stays `1.0`.
- **`emendrix repair explanations`**: the second repair, and the one that spends money. A change
  that shipped with no explanation because the model answered and the answer was unusable is asked
  again, gated, and spliced into the entry that already exists; every sibling explanation keeps
  its bytes, and a change that fails again keeps the reason it was committed with and is counted
  as still failed rather than reported as repaired. The whole prompt is rebuilt from the committed
  payload, so nothing is fetched and nothing is re-diffed: a change carries both verbatim texts,
  and running today's parser over a document whose stored text predates a parser fix would produce
  an explanation of text no reader can see. Two decisions are stated rather than defaulted into.
  The gate resolves citations against the provisions the entry itself carries text for, which is
  narrower than the loop's resolution against two whole provision trees: an offered key still
  resolves and an unknown one is still rejected, but a key naming a provision the version does not
  contain cannot be caught there. And no coordinate check runs, because the support sets are
  computed from the trees, so the contexts carry `coordinates_checked=False`, the gate counts
  nothing rather than counting every mention as unsupported, and the repair record on the entry
  says the check did not run. The unsupported-coordinate figure this project publishes is computed
  by the eval harness over the committed corpus and never over a changelog repository, so no
  published number moves either way. `--limit` counts changes rather than entries, because a
  change is what a call is paid for, and `--dry-run` names every change it would ask about, prints
  the characters it would send and prices them at the published rate with the model named beside
  the figure, building no engine and reading no API key. The price is a floor: one call per change,
  counting neither the gate's one retry nor a schema repair. A repaired explanation was produced by
  a call the entry's own `explain` block does not count, and the repair record beside it is where
  that call's tokens are.
- **The output repository**: Markdown and versioned JSON (`schema_version` 1.0) committed into a
  local git repository you own, ordered by the version each entry describes; each change names the
  acts that amended it and what each signal claimed.
- **The evaluation harness**: a labelled corpus of four acts by pinned identifier, the
  deterministic layers scored in CI, the model layer replayed from cassettes, a dated report under
  `reports/eval/` that every published number comes from, a judge benchmark, and a hand-review
  sign-off published only while its digest matches the sample it describes.
- **The static site** (`emendrix site build`): a search-first home page, an act index, a page per
  act whose every change opens onto its before and after text as a word diff, a methodology page
  carrying the metrics with their caveats, Atom feeds, and a discovery layer. It renders committed
  artifacts and nothing else: no network, no clock below the command line, no model, no cookies, no
  analytics, and two builds of one set of artifacts produce identical bytes.
- **The site counts events naming no amending act apart from amendments.** A version pair whose
  corroboration window names no amending act ships with both non-diff signals unavailable, no
  per-change attribution and no in-force date; the commonest shape is the act as published set
  against its own first consolidation, where no amending act can exist yet. The site derives the
  class at build time from the committed document's own fields, with no pipeline, schema or
  output-repository change: the front page excludes such events from "Latest amendments" and
  states how many, the acts index counts them apart and never answers its date fact with one, the
  act page keeps and labels every one, and the feeds keep every one with the fact leading the
  summary. The label says only what was established, that no amending act is named, never a cause
  such as a corrigendum.
- **Deployment**: a two-stage `Dockerfile` with a non-root runtime and a reference `compose.yaml`.
- **The CLI**: `diff`, `watch`, `explain`, `run`, `backfill`, `repair`, `eval` and `site`, with the
  delay between network calls set by `--polite-delay` or `EMENDRIX_POLITE_DELAY_S`.

### Known limitations

Named rather than discovered later; the eval report's disagreement list is the long version.

- **Renumbering is unexercised.** No renumbering occurred in any of the seven validation traces
  and no corpus role code plausibly meaning "renumbered" exists in 540 observed annotations. It is
  a change type the diff can report and a case nothing has proven.
- **Whole-provision deletion is unexercised** for the same reason.
- **Annex structure is flattened** where the corpus's two location vocabularies spell an annex
  differently (Arabic in some legacy notices, Roman in the markup). Measured: 4 of REACH's 20
  annotated annex units.
- **Text extraction degrades on older Formex generations.** The structure is stable from the 2006
  schema to the 2016 one; whitespace at element boundaries is not, and uncorrected it once
  reported every article of REACH as modified.
- **`applies_from` is `unknown` far more often than not.** The dates are machine-tagged but the
  binding that says which provision they govern is prose, and it is never inferred by the model.
  Many unknowns is the correct outcome.
- **A change whose whole difference falls beyond the character cap would be counted, not
  explained.** The prompt shows at most 40 000 characters a side, cut from the front with the cut
  visibly marked. When the difference lies entirely past that point the two blocks are identical,
  and the stage refuses the prompt rather than asking a model to describe a difference it has been
  shown none of. The change keeps its slot and ships with both verbatim texts, but it ships with
  no sentences at all. Measured over the pinned 55-change subset on 2026-08-09: **0 changes**,
  where the same subset at the 8 000-character cap produced 1, the MDR's `Annex I`. The refusal
  stays in the code and the report keeps printing the row at zero, because raising a cap moves the
  cliff rather than removing it: `Annex I` is roughly 51 000 characters a side and is now
  truncated rather than refused, and a difference that fell past 40 000 characters would be
  refused exactly as before. A zero here says this corpus stopped exercising the case, not that
  the case is gone. Still 0 over the recording of 2026-08-12, with one prompt trimmed as before:
  the boundary separator lengthened `Annex I`, whose dropped characters went from 23 115 to 24
  066, and it is the only unit in the subset whose set of shown coordinates moved at all.
- **A footnote and a quoted act ran into the sentence they interrupt, and no longer do.** The
  2026-08-12 pass gave the verbatim form a line break wherever the markup opens a block, and it
  did not cover two tags, both read as inline because both sit *inside* a run of text: `NOTE`, a
  footnote, and `QUOT.S`, the quoted text of another act. Their content is a block all the same,
  and it was joined to the interrupted sentence with nothing, producing `CouncilRegulation (EU)
  2017/745` and `the following point is added:(i)` in MDR Article 118, and the same two shapes on
  the ESPR pair `32024R1781` to `02024R1781-20240628` that exposed it. The published Formex was
  read on both sides first and says neither: the citation appears once, inside a `NOTE` the
  extraction was inlining. Since 2026-09-01 the line breaks before such content and not after it,
  a second break there stranding the resumed sentence's closing full stop on a line of its own.
  Measured over the 44 committed packages: 2025 of 69 223 nodes moved, 509 of them top-level
  units, across 34 of the 44, and `NOTE` (1904) with `QUOT.S` (346) are the only tags outside the
  block set that hold a block child inside a unit subtree, so this is the whole class and not two
  instances of it. **The deterministic layer does not move at all**: the whole `EvalRun` over the
  committed corpus serialises to identical bytes on either side of the fix, verified rather than
  assumed, because the diff reads `comparison_text`, which separates at every boundary already.
  The flagship numbers are untouched. What moved is stored text, so 4 of the 55 pinned subset
  prompts changed key and were re-recorded, with 1 of the 20 judgements and the run set's
  Article 118 exchange; the 6 superseded recordings were deleted, nothing asking for them again.
  The published model-layer figures are unchanged over the new recording: citation grounding
  1.000, quote fallback 0.000, citation validity 1.000 over 179 keys, judged faithfulness 16 of 20
  (0.800). The one subset entry carrying a truncation marker is still `32017R0745@20260101
  Annex I` and still the only one, its dropped characters moving from 11 631 to 11 635 on the
  before side and 12 435 to 12 440 on the after, which is the inserted breaks and nothing else.
  `human review` reverted to `pending` on its own, the sample digest having moved with the prompt.
  Changelogs already published keep the text they were written with and are corrected forward, not
  rewritten: measured 2026-09-01 over 369 committed change files of an output repository, 246
  carry a run of this class.
- **An amending article's own heading was read as the provision it points at, and no longer is.**
  Where an amending act states an instruction in prose instead of in a list, the instruction parser
  built the clause from the whole `ARTICLE` element, heading included, so the reference grammar met
  the amending act's own article number before the provision the sentence pointed at and read the
  first as the second. Since 2026-09-04 `TI.ART` and `STI.ART` are excluded from a clause beside
  the enumerator and the quoted text that were already there, and the clause is the instruction's
  own words. `source_ref` is untouched: it names the amending article the claim came from, which is
  provenance and was always right. Measured 2026-09-04 over the public changelog, every one of the
  82 claims that path has ever produced carried the amending act's article number, 81 of them
  naming a unit no other signal saw, 8 of them naming an article number larger than the amended act
  has articles; they land in 79 committed changelogs across 44 acts. Changelogs already published
  keep the text they were written with and are corrected forward, not rewritten, which is the
  posture the 2026-09-01 fix above took, so a page served today may still show a phantom unit. Over
  the committed corpus, scored offline from the fixtures, the disputed rate reads 13 of 101 changes
  (0.129) where it read 17 of 104 (0.163), `metadata_only_units` reads 3 where it read 6, the
  structural diff against the instruction parse reads P 0.917 / R 0.985 / F1 0.950 and macro F1
  0.531 over 13 transitions where it read P 0.875 / R 0.940 / F1 0.906 and macro F1 0.378, and the
  metadata against the instruction parse reads P 0.889 / R 0.955 / F1 0.921 and macro F1 0.455
  where it read the same four figures as the pairing above it. **Neither set is the other
  improved.** Three of the 104 were phantom units and were never changes at all, so the denominator
  differs, and the third signal now reads the amended act's article numbers where it read the
  amending act's, so the right-hand side of every pairing it enters is a different set of claims;
  the question each figure asks is unchanged. Both sets are published under their own dates, in
  `reports/eval/2026-08-13-ea13042.md` and `reports/eval/2026-09-04-984347f.md`, and neither is
  adjusted for the other. Localisation does not move in any component, pairing the structural diff
  against the metadata and never consulting the instruction parse; classification, the case count,
  `instruction_unread` and both parser counters do not move, and neither does the flagship, so no
  committed floor moved and only the two `source` strings did. What this does not fix is that an
  article on that path still yields one claim for the whole article: every alinea and paragraph is
  flattened into one string and one record is written from it, so an article stating two or three
  amendments in prose names at most one of them, and a collapsed instruction leaves nothing behind
  to count. `docs/limitations.md` carries that as the named gap it is.
- **An amending act's instructions were claimed in every window that act touched, and are
  scoped to one since 2026-09-05.** The third signal was read out of an amending act's own
  package whole, so an act amending a regulation over several consolidations had its entire
  instruction set attributed to each of them, however the act itself dated the orders in it. The
  consolidation window `(after, until]` now goes down to that signal as well as to the
  annotations: a record whose effect date the act's own text yields and which falls outside the
  window is out of scope for that transition and is not claimed there. Only the act's own text
  dates a record, never an annotation, because the metadata may say which document the third
  signal reads and must never say what it finds in it; intersecting the two would delete the
  cases where the instruction parse is the only signal corroborating the structural diff against
  silent metadata, and it is not done. A record the act dated nowhere is claimed exactly as it
  was before any date was read, which is the safe direction of every failure here and the reason
  the change is small. The signal's note now carries both counts, how many records the window
  excluded and how many carried no readable date, so an empty signal and a scoped one are told
  apart in the payload itself. Over the committed corpus, scored offline from the fixtures, the
  disputed rate reads 12 of 100 changes (0.120) where it read 13 of 101 (0.129),
  `metadata_only_units` reads 2 where it read 3, the structural diff against the instruction
  parse reads P 0.917 / R 1.000 / F1 0.957 and macro F1 0.538 over 13 transitions where it read
  P 0.917 / R 0.985 / F1 0.950 and macro F1 0.531, and the metadata against the instruction
  parse reads P 0.889 / R 0.970 / F1 0.928 and macro F1 0.462 where it read P 0.889 / R 0.955 /
  F1 0.921 and macro F1 0.455. **Neither set is the other improved.** One of the 101 was never a
  change in the window it shipped in, so the denominator differs, and the right-hand side of both
  pairings the third signal enters is a different set of claims; the question each figure asks is
  unchanged. Both sets are published under their own dates, in
  `reports/eval/2026-09-04-984347f.md` and `reports/eval/2026-09-05-6097989.md`, and neither is
  adjusted for the other. Localisation does not move in any component, pairing the structural
  diff against the metadata and never consulting the instruction parse; classification, the case
  count, `instruction_unread` and both parser counters do not move, and neither does the
  flagship, so no committed floor moved. The transition that moved is `32017R0745@20240709`, its
  amending act ordering an article into existence from a day six months past the far end of that
  window. What this does not fix is how rarely an act says when its own instructions apply.
  Measured on 2026-09-05 over a clone of the published corpus as it stood on 2026-08-14, 369
  events and 4,588 changes carrying 1,309 claims no other signal named, the window excludes 85 of
  them, 0.065, across 13 events: changes with no text on either side fall from 1,580 to 1,495,
  0.344 to 0.326, where removing the whole class would have taken them to 271. Only 0.183 of
  instruction records carry a date at all and four fifths of those come from the act's single
  date of application, so an act that states one date for everything is scoped exactly once and
  an act that states none is not scoped at all. That is a counted coverage gap and not a
  disappointment to be widened away: a rule that dropped a claim on a date nobody read would lose
  a finding to gain a smaller number. Where the act does date an instruction the scoping bites
  hard and correctly: `32019R2033` dates a deletion into one window in its own words, and that
  claim stays there, ships `disputed` against a structural diff that found nothing, and is the
  kind of disagreement this project exists to publish, while the same act's other orders stop
  appearing in two windows seven years apart. Changelogs already published keep the text they
  were written with and are corrected forward, not rewritten, so a page served today may still
  show a claim in a window its act dates elsewhere; the note on every committed payload is stale
  by its new counts as well, so the pass that corrects them will rewrite entries whose claims did
  not move.
- **An amending act's own dates are read from its notice as well as from its text, since
  2026-09-05.** Most amending acts enter into force *"on the twentieth day following that of its
  publication"* and never write that day, so the four tiers that read the act's own words had
  nothing to read and the whole instruction set of such an act carried no date at all. The day is
  published: the act's own CELLAR notice carries `RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE`, one
  element per date, each annotated with a type of date and a comment saying how the Publications
  Office arrived at it. On `32024R1860` the entry-into-force annotation reads `DATPUB V ART 3`,
  which is that office recording that it applied the act's own Article 3 to the publication date.
  That is the twentieth-day arithmetic, already done, by the authority that publishes the act, and
  reading it is not inference. It is checked against the one thing that can check it: on the same
  act the notice's application date is 10 January 2025, which is exactly the day the markup reader
  takes out of `<DATE ISO="20250110">` in that act's Article 3 and attaches to `AR 1 PO 1`. Two
  independent readings, one answer, and the agreement is asserted in the suite. The tier sits
  below the act's own words and above nothing, the notice is fetched in the composition root and
  reaches the parse as a value, and a default the markup reader withdrew stays withdrawn, because
  a second source cannot say which instructions an unattributable statement was about either.
  **What the annotation does not say is what the date covers**, and the whole safety of the read
  turns on that. Measured 2026-09-05 over the 295 tree notices in the disk cache and the 742 dated
  entries in them, every comment names the provision that *states* the date: on `32021R2117` all
  five name Article 6, that act's entry-into-force article, while the parts they stage sit in
  Articles 1, 2 and 3. So an entry marked as partial cannot be resolved onto an instruction
  coordinate, and an act carrying one publishes no act-wide answer at all rather than a date
  picked from several. 29 entries carry that mark in the type of date and a disjoint 262 in the
  comment; the `1001-01-01` that 17 of the notices write for a day a later decision will fix is
  outside the span an act's dates fall in and is counted rather than read. Of the 168 cached
  amending acts, 72 carry an entry the notice cannot place, and with them 2 406 of the 4 610
  instructions; 8 carry an implausible value. Every ambiguity resolves to unread and is counted,
  exactly as the tiers below it decided: under-scoping leaves a true claim in place, over-scoping
  deletes one.
  **The coverage figure moves and it is not the earlier one improving.** Over the disk cache as it
  stood on 2026-09-05, 168 amending acts and the 4 610 instructions they yield, the five tiers
  date 1 714 (0.372) where the four that read the act's own words date 585 (0.127) over the same
  acts and the same instructions; 113 acts are dated in full and 38 yield no date anywhere. The
  0.183 of 317 over 1 734 published earlier the same day was measured over a smaller cache, 84
  amending acts against 168, so it is a different denominator and not this figure before it moved.
  Both are published under their own dates and neither is adjusted for the other.
  **No published evaluation figure moves at all.** Scored offline from the fixtures, the disputed
  rate, `metadata_only_units`, both pairings the third signal enters, localisation,
  classification, `instruction_unread`, the parser counters, the model layer and the flagship all
  read exactly what they read before, and no floor was touched. What moved is six signal notes:
  `32008R0987`, `32020R0561`, `32023R0502`, `32023R0607`, `32025R2457` and `32026R1744` now report
  0 records undated where they reported 2, 26, 1, 6, 4 and 84, because each of those acts has a
  day and none of the 123 records falls outside the window that folded its act in. A re-score on
  the same date supersedes the earlier one, so `reports/eval/2026-09-05-8cb6d5f.md` is replaced by
  `reports/eval/2026-09-05-6097989.md` rather than joined by it, and the two carry the same
  figures.
  **Over the published corpus the tier withdraws nothing, and that is the measurement.** Measured
  2026-09-05 over the same clone of the corpus as it stood on 2026-08-14, 369 events and 4 588
  changes carrying 1 309 claims no other signal named: 963 of those claims, across 54 amending
  acts, gain a date they did not have, and every single one of them falls inside the window it was
  already claimed in. Not one claim is withdrawn that the act's own text had not already
  withdrawn. That is what should be expected of a corpus of consolidations, since a consolidation
  is dated at the day the amendment it folds in took effect, and it is worth publishing as a zero:
  the replay this scoping exists to stop is caused by acts that stage their orders across later
  windows, and a staged act is exactly the act whose notice cannot place its dates. The six acts
  whose thin coverage prompted the tier, `32019R0876`, `32021R2117`, `32024R2809`, `32023R2845`,
  `32019R0834` and `32019R2033`, read 0.023, 0.078, 0.091, 0.106, 0.000 and 0.776 after it,
  exactly what they read before. Their notices do carry their dates and every one of them is
  staged, and a second rule blocks them independently: their final provisions name the instruction
  article as an exception, so the markup reader guards it and no act-wide date of any provenance
  may reach the instructions drafted there. Widening either rule to reach them would date
  instructions the act deliberately took out of its own default, which loses a true claim to gain
  a number.
  **The blast radius of the scoping was re-measured while this was counted, and reads larger than
  it was published at.** Over the same clone, deriving each window from the payload's own version
  identifiers and each amending act from the payload's own instruction claims, so that all 369
  events resolve, the window excludes 151 of the 1 309 claims (0.115) across 76 events, where the
  reading published beside the scoping rule earlier the same day read 85 across 13 events. Nothing
  in the code differs between the two readings, which are the same question measured over
  different numbers of resolvable events, and neither is adjusted for the other. Changelogs
  already published keep the text they were written with and are corrected forward, not rewritten,
  so the note on every committed payload is stale by its undated count as well, and the pass that
  corrects them will rewrite entries whose claims did not move.
- **A deferral that writes out every point it defers is read to all of them, since 2026-09-05.**
  An amending act's final provisions state which of its own instructions take effect later, and
  `32021R2117` Article 6 states four such sentences that between them name twenty coordinates, each
  one written out: *"Article 1, points (8)(d)(i), (8)(d)(iii), (10)(a)(ii) and (38), shall apply
  from 1 January 2021"*. The reference grammar keeps the first coordinate at each nesting depth,
  which is right for an instruction clause pointing at one provision and wrong for a sentence
  listing several, so that statement resolved to `AR 1 PO 8` and the nineteen others were
  discarded. The reader then had to guard the whole of Article 1 against its own default, because
  it could no longer say which part of that article the date covered. **The defect was never the
  twenty points; it was the blast radius of the doubt.** Article 1 of that act drafts 200
  instructions and defers 19 of them, and guarding the article took the date away from all 200. A
  new grammar reads the subject of such a statement as the list it is, strictly: every fragment
  must parse, nothing may be left over, and a range (*"points (11) to (14)"*), a second act
  (*"as regards Article 104a of Regulation (EU) No 575/2013"*), a description
  (*"containing the provisions on own funds"*) or a list written in the sub-list below
  (*"The following points of Article 1 … :"*) is refused entirely and read exactly as it was
  before. Nothing is resolved optimistically: this removes an ambiguity rather than starting to
  guess at one, and every refusal that refused before still refuses, each with a test.
  **The staged notice is the second half of it.** An act whose notice dates part of it separately
  publishes no act-wide answer on the notice's own account, because the notice never says which
  part; that rule was published on 2026-09-05 and stands. It is not the only document that can
  say. Where every dated statement of the act was read in full and the days those statements
  attribute to coordinates cover every day the notice staged, the staging is placed and the act's
  own entry into force stands for the rest. Only a statement read in full may place a day: one
  read to its first coordinate has left the reader with the same not-knowing the notice has, and
  two of those do not make an answer. Over the disk cache as it stood on 2026-09-05, 4 of the 72
  staged acts are placed this way, `32021R2117` among them at 7 December 2021.
  **The coverage figure moves and it is not the earlier one improving.** Measured 2026-09-05 with
  `scripts/validation/instruction_effect_dates.py` over the same 168 amending acts and the same
  4 610 instructions the notice tier was measured over that morning, the tiers date 1 956 (0.424)
  where they dated 1 714 (0.372), the notice supplying 1 346 where it supplied 1 129. That is one
  cache read under two rules, not one number improving; both are published under their own dates
  and neither is adjusted for the other. Of the six acts whose claims repeat across windows,
  `32021R2117` reads 1.000 where it read 0.078 and `32019R2033` reads 1.000 where it read 0.776;
  `32019R0876` (0.023), `32023R2845` (0.106), `32024R2809` (0.091) and `32019R0834` (0.000) do not
  move at all, each of them stating a deferral this grammar refuses, and that is published as
  measured rather than widened away.
  **No published evaluation figure moves.** Scored offline from the fixtures, the disputed rate,
  `metadata_only_units`, both pairings the third signal enters, localisation, classification,
  `instruction_unread`, the parser counters, the model layer and the flagship all read exactly
  what they read before, and no floor was touched. What moved is one signal note: `32024R1860`
  now reports 0 records undated where it reported 13, its Article 3 deferring both the points it
  names instead of the first, and the day its notice publishes reaching the other 13. A re-score
  on the same date supersedes the earlier one, so `reports/eval/2026-09-05-73d375c.md` is replaced
  by `reports/eval/2026-09-05-6097989.md` rather than joined by it, and the two carry the same
  figures.
  **The corpus blast radius was re-measured, and the script that measures it is now committed.**
  `scripts/validation/instruction_claim_scoping.py` takes each event's window from the payload's
  own version identifiers and each amending act from the payload's own instruction claims, counts
  the top-level units the third signal alone claimed, and asks which of them the window would
  exclude today. Run against a clone of the published corpus at `efd21ab`, the corpus as it stood
  on 2026-08-14, it reproduces **151 of 1 309 (0.115) across 76 events** on the code as it stood
  before this change, which is the second of the two readings published on 2026-09-05 and not the
  first. The first, 85 across 13 events, was the same question over a much smaller set of events
  the measurement of the day could resolve; it stands under its own date and is not corrected
  here. With the deferral read in full the same script reads **164 of 1 309 (0.125) across 80
  events**, published under its own date beside both. Changelogs already published keep the text
  they were written with and are corrected forward, not rewritten, so a page served today may
  still show a claim in a window its act dates elsewhere.
- **A touched unit carrying no text was counted substantive, and is counted in its own bucket
  since 2026-09-05.** The corroborator appends one change for every unit another signal named and
  the structural diff never saw, and the diff is the only signal carrying text, so such a change
  has a location, a kind, `disputed: true` and nothing quotable at all. `substantive` was computed
  as every touched unit that was not date-only, so it covered them. It is now every touched unit
  that is neither date-only nor textless, and the units it no longer covers are counted as
  `textless` and printed on the count line, in the Markdown header and in the Atom summary as
  `with no text`. Measured 2026-09-05 over the 446 committed events of the public changelog and
  their 5 259 touched units: `substantive` reads 3 414 where it read 5 218, and `textless` is
  published for the first time at 1 804, 34.3% of the 5 261 changes. **This is not the corpus
  having shrunk and no row was dropped**: `touched` reads 5 259, `date_only` 41 and `disputed`
  2 865, each unchanged, and the three buckets sum to the touched count. The question the word
  answers changed, from "not date-only" to "not date-only and carrying text", so the two readings
  are two definitions rather than one number improving, both are published under their own dates
  and neither is adjusted for the other. 148 events change their count line and 26, every unit of
  which is of this kind, state that in a clause in place of the three-way split, in their first
  line, their title, their meta description and their feed entry's title; no permalink and no Atom
  entry id moves, so nothing renotifies. No published evaluation figure moves with any of it,
  nothing in `eval_` reading these counts, no cassette moves and no faithfulness sign-off is
  affected; the flagship AI Act event and the MDR postponement the goldens are built on carry no
  such unit, so their numbers are identical either side. `schema_version` is `1.1` for documents
  written from this date, because a consumer summing `substantive` and `date_only` to get
  `touched` was right before it and is wrong after, which is exactly what a version is for; the
  446 already published say `1.0`, still validate, and read back with `textless` at 0 and the
  `substantive` their own run computed. The site reads these counts off the committed document and
  is forbidden from recomputing them, so a page served today still shows the older split until the
  document behind it is rewritten, which is the corrected-forward posture the two fixes above take.
  The curated reason those changes ship with lost the one backtick pair in it on the same date: it
  is stored on a published document and is read into Markdown, into JSON and into an HTML page
  that escapes what it is given, so only one of the three surfaces would have read a fence as
  anything but two stray characters. The 1 804 stored copies are corrected forward with the counts.
- **An explanation records what it was shown, from 2026-09-05, and no earlier one is given a
  record it cannot have earned.** Every stage of this loop is deterministic and free to recompute
  except the model call, which is paid, non-repeatable and written *about* a particular pair of
  verbatim texts. The two extractor fixes above moved stored text, so prose written before them
  describes evidence the pages no longer show, and nothing in a payload said what the writer had
  been shown: the only way to ask which explanations went stale was to re-parse the whole corpus
  and diff it against every committed document. A change written from this date carries an
  `evidence` digest, `sha256` over its canonical location and its two verbatim texts in that
  order, NUL-separated and UTF-8 encoded, with an absent side tagged apart from an empty one. It
  digests the **evidence and not the prompt**: a reworded instruction, a moved header date or a
  renamed citation key does not make a shipped sentence describe text that is no longer there,
  and a changed verbatim text does. `schema_version` is `1.2` for documents written from this
  date, because a consumer reading a missing digest as "unchanged" would be wrong about every
  document published before it; adding the field alone would not have been a bump. **Nothing is
  retro-fitted.** The digest states what one call was shown, so it is written by the run that made
  the call and carried over untouched by any repair that does not re-ask, exactly as `detected_on`
  is; a repair that does re-ask records the one change it asked about and leaves every sibling as
  it found it. The 5 261 changes already published carry none and read as provenance unknown,
  which is a counted state in the register of `ApplicabilityUnknown` and not a gap to fill in:
  deriving one from a payload's own stored texts would assert a fact about a call nobody
  witnessed.
- **The join rule the verbatim form rests on is asserted over every committed package, since
  2026-09-05.** The 2026-09-01 fix rested on a claim measured that day, that `NOTE` and `QUOT.S`
  were the only tags outside the block set holding a block child inside a unit subtree. Nothing
  held that true afterwards, and a run-on is not malformed, raises nothing and passes every schema
  and type check here, so a fixture or a fetched package could reopen the class in silence. The
  parser now counts, on every parse, any element outside both sets that holds a child either set
  would break the line before, as `ParserCoverage.undetached_blocks`: a counted coverage gap
  naming the tag, never an exception, with the text still shipping joined the conservative way an
  unrecognised tag always is. Both sets count on the inside, not just the block one: a wrapper
  outside them gets no break of its own, so a `NOTE` sitting first inside it opens on a line
  nothing has opened and runs into the sentence before it, which is the 2026-09-01 defect wearing
  one more layer. The invariant reads empty over all 44 committed packages, every parent of a
  `NOTE` or a `QUOT.S` in them being a block element itself. **The symptom scan beside it ships two
  rules of the three proposed, and says why.** A bracketed enumerator welded to the full stop,
  colon or semicolon before it (`added:(i)`) reads 0 over those packages, and two word halves
  welded at a case change (`CouncilRegulation`, two letters required on each side) reads 0 with an
  empty allowlist. The wider forms are not shipped and the measurements are the reason: any word
  character butting against an opening bracket fires 18 673 times, all of it ordinary drafting
  (`Article 114(3)`, `test(s)`), and any lower-to-upper transition inside a word fires 3 074 times
  over 34 distinct words, every one of them chemical nomenclature or a unit (`vPvB`, `pH`, `kPa`,
  `decaBDE`, `mL`), an allowlist that would grow with every re-pinned REACH annex. A guard nobody
  trusts is worse than no guard.
- **The stale set is measurable, and the script that measures it is committed.**
  `scripts/validation/evidence_staleness.py` re-derives both versions of every committed event
  through today's parser off the shared disk cache, and reports per change whether the evidence
  matches, differs, or cannot be derived. It calls no model, writes nothing and is offline unless
  `--fetch` is passed. Run against a clone of the published corpus at `e007d1e`, the corpus as it
  stood on 2026-09-05: **5 261 changes, of which 4 602 match, 539 differ and 120 cannot be
  derived**, the last being 17 consolidations the disk cache does not hold. 1 804 of the matches
  are textless changes, which carry no evidence on either side and so cannot go stale. **240 of
  the 446 transitions carry at least one differing change**, and those changes hold 137 627 136
  characters of stored evidence between them, of which 17 616 892 fall inside the 40 000-character
  prompt cap and would actually be sent. Every change in that reading has unknown provenance, so
  the left-hand side is the payload's stored text rather than a witnessed digest, and the script
  counts the two bases apart. This reading answers a different question from the two blast-radius
  readings published on 2026-09-05 for the instruction scoping (85 and 151, then 164, of 1 309):
  those count claims a window withdraws, this counts explanations whose evidence moved. All of
  them are published under their own dates and none is adjusted for another.
- **The published corpus was rewritten on 2026-09-05, so the entries say what the code produces
  today.** The corroboration repair walked all 446 committed events and rebuilt the 337 whose
  third signal can be recomputed from the payload alone, an event qualifying when its committed
  instruction signal was available and its claims name exactly one amending act. The window that
  signal is scoped to is read off the event's own version pair, a consolidated identifier being
  `<celex>-<YYYYMMDD>`, so the pass scopes exactly the window that was published and reads
  neither a clock nor a version inventory to find out which one that is. **313 claims were
  withdrawn across 27 events**, every one of them a unit only the unscoped instruction parse
  ever named, and **6 changes stopped being disputed**. Nothing was added anywhere: no event, no
  unit, no claim, and no file changed its name, so no permalink and no feed entry id moves. Of
  the 337, **225 had a claim move and 112 changed only in what the signal's note reports**, that
  note now carrying the two window counts, so an event whose claims stood still is rewritten by
  the suffix alone. 1 394 changes with no text had their stated reason restated from the
  constant rather than carried from the document: nothing was ever asked about such a change, so
  the only sentence it holds is this project's own, and the wording corrected the same day
  reaches the events already published instead of standing in them. Every rebuilt event is
  written at `schema_version` 1.2 with its counts recomputed, `textless` among them. **No model
  was called and nothing was spent.** The pass reads the amending acts' packages through the
  shared disk cache and never touches `ExplainSettings`, and the repair record it wrote on each
  event records zero requests, zero tokens and zero schema repairs. Measured over the whole
  corpus either side of it:
  5 261 changes before and 4 948 after, of which 1 804 and 1 491 carry no text (0.343 and 0.301)
  and 2 865 and 2 558 ship disputed (0.545 and 0.517). **Neither pair is one rate improving.**
  The right-hand side of each is a different set of claims, the question each figure asks is
  unchanged, and neither reading is adjusted for the other. The site reads its counts off these
  documents and is forbidden from recomputing them, so it shows none of this until it is rebuilt
  from them. The dated entries above are left as they were written, each being true of the day
  it describes.
- **An explanation written about text a parser fix has since corrected can be asked again, and
  only that explanation.** `emendrix repair evidence` re-fetches, which its two siblings must
  never do: `repair explanations` rebuilds its prompt from the committed payload precisely so
  that it never describes a document the page does not show, and `repair corroboration` never
  touches stored text at all, so pointed at this defect the first would ask again about the same
  corrupted text and the second would carry it over. The defect is in the stored evidence, so the
  verb parses both versions again through the shared disk cache, re-derives the delta, merges it
  with the two signals the payload already carries, and then decides per change. Evidence that
  still reads as it was published keeps its sentences, its gate decision and its citations
  untouched and costs nothing; evidence that moved is asked about again, about the corrected
  text, and gated against both trees, so this is the one repair whose record can say
  `coordinates_checked: true`; a change today's delta no longer holds is withdrawn; and one it
  holds that the entry does not is asked about and counted apart, because the two answer
  different questions. Which of those a change is, is decided by the comparison
  `scripts/validation/evidence_staleness.py` already measures the corpus with, lifted into
  `emendrix.repair.staleness` and imported by the script, because two notions of "differs" would
  drift within a month. **Three rules bound what a pass will do.** A change the model fails on
  again keeps its sentences *and* the stored text they were written about, since correcting one
  without the other would leave a reader prose about one text beside another and would leave the
  next pass unable to see the change is still stale; it is counted as remaining and never
  reported as repaired. `--limit` counts changes, and an entry is asked about in full or not
  started, for the same reason. And a transition today's parse cannot produce is counted, named
  and left exactly as it is. A digest is written only for a change the pass itself watched a call
  for, so every sibling keeps the provenance it arrived with, which for the corpus published
  before 2026-09-05 is none. Where an entry's own digest proves its sentences were written about
  the text today's parser produces, a stored text that has drifted from it is corrected with no
  call at all and counted apart from the re-asked.
  **Priced before it ran, on 2026-09-05**, against a clone at `351bf4c`, the corpus as the
  corroboration pass of the same day left it. All 446 entries re-derived: none of the 17
  consolidations the disk cache had been missing refused, so no transition was left unread. Of
  the 4 948 changes, **557 differed, across 247 of the 446 transitions**; every other change with
  text still read as the evidence it was published with. **No unit was added and none was
  withdrawn anywhere**, and no change newly carried no text. The prompts held **20 029 173
  characters**, about 8 901 855 input and 195 507 output tokens at one call per change, which the
  USD 2.00 and USD 10.00 per million tokens this repository has on file for
  `openrouter:anthropic/claude-sonnet-5`, checked 2026-08-08, priced at **about USD 19.76**, a
  floor counting neither the gate's one retry nor a schema repair. **That reading is not the one
  of 539 of 5 261 published earlier the same day**, which the validation script took before the
  corroboration pass withdrew 313 claims and rewrote 337 entries, and which counted 120 changes
  it could not derive at all; the denominator differs, the underivable are now derived, and
  neither figure is adjusted for the other. The zeroes for added and withdrawn are not a re-parse
  finding today's delta unchanged in every respect: the merge holds today's diff against the
  signals the payload already carries, so a unit only a signal ever named is re-created exactly as
  it was published, and what the zeroes say is that the diff itself now finds the same units the
  published entries hold.
- **The pass ran on 2026-09-05 and cost about USD 18 against an estimate of USD 19.76.** It went
  in three tranches, priced against the provider between each, and **472 of the 557 changes were
  re-explained across 206 rewritten entries**. Every one of the 557 was asked about at least once.
  **85 changes across 66 entries still differ and were deliberately left exactly as published**,
  text and prose together: the model failed on them again, which is counted and is never reported
  as repaired, and keeping the pair intact is what lets a later pass still see them as stale. The
  identifiers held: **no entry's act, version pair or `detected_on` moved, and no file was added,
  removed or renamed**, so nothing a permalink or a feed id is derived from can have changed; 240
  files moved, being 206 payloads and the 34 act changelogs they sit in. **3 054 changes inside
  the rewritten entries kept every byte**, prose, citations and gate outcome included, verified
  against the versions they replaced rather than counted, and **not one explanation moved on a
  change whose text did not**. 472 evidence digests were written, one per change this pass
  watched a call for, each verified to be the digest of the change it names; every other change
  carries the provenance it arrived with, which for this corpus is none.
  **On the estimate.** The provider billed **USD 16.25** for the second and third tranches, read
  from its own credit meter; the first was not metered there and its repair records price it at
  **USD 1.43**, so the pass cost **about USD 18**, under a floor of USD 19.76 and well inside the
  USD 40 ceiling it was authorised against. The floor held despite counting neither of the two
  things that did happen: the written entries record **574 requests for 500 changes addressed,
  102 of them schema repairs**. What made up the difference is the character-to-token assumption:
  the estimate reads 2.25 prompt characters per input token, measured 2026-09-04 over 71
  exchanges, and this pass recorded 7 624 638 input tokens where that ratio predicted 8 901 855
  for fewer requests. **The estimator undershot by a factor of two on the recorded run of
  2026-09-04 and overshot by a tenth here**, so it is a floor with a real spread rather than a
  reliable multiple, and the spread is what a reader should carry rather than either number.
  Nothing was pushed, no site was rebuilt and no feed was reissued: the corrected entries sit in
  the output repository until the hostname move, so that the feeds reissue exactly once.
- **A model failure ships as a stated reason, and the verbatim fallback deliberately does not
  cover it.** A live call can fail in ways the pipeline does not control: a timeout, a refusal, a
  rate limit, pydantic-ai's schema-repair budget exhausted. Since 2026-08-31 every such failure
  is one first-class state, kind `model_failed`, shipping one curated sentence in the register of
  the rest of the output and counted in the report's reason breakdown beside the cap's refusal;
  the exception's class and message go to the operator's log and never to a stored field. Before
  that date the exception's own text shipped in the `unexplained` field, and the published
  changelog carries the two measured instances, `Art. 25` and `Art. 57` of the AI Act event
  `02024R1689-20260727`, until that repository is amended; no committed document in this
  repository carries one, verified 2026-08-31 by searching every golden, report and cassette for
  library exception names. The gate's verbatim quotation was considered for this case and
  rejected: the fallback replaces a claim the gate rejected, a change that never got an
  explanation made no claim, the texts a quotation would repeat already ship with the entry, and
  counting a failed call into `fallback` would fold provider availability into the quote-fallback
  rate, which measures citation failures. Whether the same two provisions fail again on a
  re-record is unknown and left unanswered on purpose: a failed exchange is never recorded, a
  cassette holds only a well-formed answer, and answering would cost a recording about a question
  no published figure depends on.
- **A provider that never answered leaves the entry unfinished, since 2026-09-04.** The kind
  above settles a change: the model answered and the answer was unusable, which is a fact about
  that change. A refused or unreachable provider is not, and until this date it was counted the
  same way. That mattered because `backfill.emitted` resumes on the payload file existing, so an
  installation whose provider credit ran out mid-run published the gap once and then skipped past
  it on every later run. `provider_unavailable` is now its own counted kind, reaching the payload
  as `unexplained_kind`, and `OutputRepo.holds_finished` reads the file rather than only looking
  for it, so a later backfill completes what an interrupted one left. An unrecognised HTTP status
  settles the change rather than marking it unfinished, because settling one wrongly costs a
  thinner entry once while the other way costs a re-run on every backfill for ever; an unreadable
  payload settles for the same reason. Entries written before this date carry no such field and
  read as finished, which is correct: nothing structural separates them from older entries whose
  reasons predate any counter, so clearing them is a one-off rather than something this can infer.
  Measured 2026-09-04 over the public changelog: 43 entries, 176 changes across four chemicals
  acts, carry a provider refusal that no later run would ever have revisited.
- **The schema-repair budget is two attempts since 2026-09-04, and was one before.** Measured the
  same day over the 5 336 changes the public changelog then held, 90 shipped with no explanation
  because the budget ran out, 2.8% of the 3 213 that reached the model. The character counts of
  the failed and the explained changes overlap heavily and the largest act sits on the base rate,
  so the failure reads as stochastic rather than as a property of a change, and a second attempt
  is cheaper than the gap it prevents: a repair costs one request, a failure costs the whole call
  and returns nothing. Re-running those 90 was considered and rejected. The unit a re-run replaces
  is a whole transition, so recovering them would re-explain 1 979 changes to fix 90, and because
  the model is not deterministic it would rewrite 1 889 explanations that are already correct.
  `emendrix repair explanations` is what replaces the change instead of the transition, so those
  1 889 keep their bytes; the 90 stay in the published record until a pass is run against it, and
  the failure being stochastic means a pass is expected to leave a few of them still unexplained.
- **All ninety were asked again on 2026-09-04, in two passes, and eighty-nine of them now carry
  prose.** The first pass reached fifteen: 14 changes across 11 entries got sentences and 1 failed
  a second time. The other seventy-five were unreachable, because the repair selects on the counted
  kind `model_failed` or on the curated sentence above and that sentence has existed only since
  2026-08-31; those seventy-five predate it and carried the provider library's own error text in
  `unexplained`, which a reader saw on the page. `emendrix repair unexplained` restated them in the
  register the rest of the output is written in and stamped the kind beside them, matching one
  exact string and an empty kind rather than a prefix, since the same field carries the ordinary
  reason of every other unexplained change. That pass calls no model and opens no adapter: 75 notes
  across 40 entries in 19 acts, after which no published page renders a library exception name at
  all. A second explanation pass then repaired 75 of the 76 changes that had become selectable,
  the seventy-sixth being the one the first pass had already failed on and which is free to try
  again.
  **No explanation that already existed was rewritten in any of it.** Across the 40 entries the
  second pass wrote there are 2 345 changes, of which 75 gained sentences and 0 that already had
  them moved by a byte; in the densest, a Capital Requirements Regulation entry of 293 rendered
  change blocks, exactly the 3 repaired blocks moved. `detected_on` is carried over everywhere,
  because a repair is not a detection. **A repaired explanation was produced by a call the entry's
  own `explain` block does not count**: that block records the run that first wrote the entry, so
  the repair records itself beside it with its own usage and a `coordinates_checked` flag that
  reads false, this repair holding neither provision tree and an unrun check never being allowed
  to read as a passed one. Measured cost was USD 2.66 against a floor estimate of USD 1.41, the
  difference being 52 schema repairs across 127 requests for 75 changes, which the estimate states
  it cannot count.
  **One change still has no explanation and three notes are deliberately left as they are.**
  `AR 14` exhausted the repair budget twice and keeps the sentence it shipped with, which is one in
  seventy-six and in line with the measured rate of this failure. Separately, three changes in
  `32014R0600`, `32014R0806` and `32017R0745` carry a note naming a second library shape, a
  connection error, and the restatement counts them and refuses to write them: that is a provider
  that could not be reached rather than a model that answered badly, so `model_failed` would claim
  an answer that never came and `provider_unavailable` would make `holds_finished` reopen those
  entries and re-run three whole transitions whose explanations are already correct. Naming them
  wrongly is worse than leaving them named as they are, so they stay, counted and stated, until
  something establishes what they should say.

- **Explanations can still outrun their evidence, and the shape of it has changed.** The hand
  review of 2026-08-08 over the prose that shipped then marked 3 of 20 entries unfaithful at the
  truncation marker. That count was published as one class and it was three different things, and
  separating them is the finding rather than the count:
  - The AI Act's `Art. 57` wrote "the text is truncated before further differences in paragraphs
    12 and 14 can be described". Paragraph 14 was in that prompt's own `SUB-PROVISIONS THAT
    DIFFER` line; paragraph 12 was in neither that line nor anything the diff localised, its
    after-side text lay past the marker, and its before-side text was fully visible. Nothing the
    model was shown could establish that paragraph 12 differed, and the difference was asserted
    anyway. That is the real one. At the raised cap the same provision ships whole and the reading
    of 2026-08-09 ticked it.
  - The MDR's `Art. 78` named `Art. 78(14)(1)` and `(2)`, both listed verbatim in that prompt's
    `SUB-PROVISIONS THAT DIFFER` line, and explicitly declined to describe them. It described
    nothing past the marker: the sentence rested on the pipeline header rather than on the two
    texts, and the reviewer, who was shown the two texts alone, marked it unfaithful. They
    answered the question they were asked and answered it correctly. The defect was in the
    question. The prompt prints the header precisely so the model relies on it, while the two
    auditors were shown less than the writer had, so the setup was measuring the pipeline twice
    and reporting the second reading as a model failure. Widening the evidence base is what
    settled it, and the verdict stands as recorded against the question it answered: no verdict a
    reviewer wrote is ever re-scored under a later question.
  - REACH's `Annex XIV` claimed the entry list otherwise appeared unchanged when both texts were
    truncated at different points. That one is its own limitation, below. So one of the three was
    a defect in the prose, one was a defect in the measurement, and one was a defect in the prose
    of a kind nothing checks. The reviewer's verdicts stand exactly as recorded and the
    hand-reviewed rate for that reading stays 15 of 20. What replaced them is not an improvement
    of the same thing: read on 2026-08-09, no entry of the sample describes anything past a
    marker, and the two entries that failed failed over text fully visible on both sides, one
    compressing a list of delegated powers into a broader one and one opening by asserting the
    opposite of what its own second half says. That is the failure mode a bigger cap cannot touch,
    and no deterministic check in this project covers it. The reading of 2026-08-13, over the
    recording that ships, found three failures and none of them describes anything past a marker
    either: all three overstate what text fully visible on both sides says.
- **An exhaustiveness claim over unshown text is checked by nothing.** A sentence saying that the
  rest of two texts agree, "otherwise unchanged", "and beyond", "the remainder", is unverifiable
  from evidence that was cut, and REACH's `Annex XIV` on the recording of 2026-08-08 is the
  measured instance: both sides truncated at different points and the entry list asserted
  otherwise unchanged. The obvious check was considered on 2026-08-08 and **rejected**: it reduces
  to a hand-authored phrase list over an open-ended semantic class, and a heuristic wearing a
  deterministic costume is worse for this project than a gap it admits to. Diff-anchored windowing
  in place of the prefix cap was rejected the same day and for a concrete reason: on `Annex XIV`
  the structural diff localised nothing finer than the annex itself, so there was no window to
  anchor to. The raised cap reduces the exposure and does not close the gap. The shape is still
  present on the reading of 2026-08-09, in four of the twenty entries, and what changed is that
  all four now stand over untruncated text, so each is a claim a reader can walk end to end; two
  were walked and survived. A claim a reader can check is not a claim a machine checks.
- **The unsupported-coordinate count is a floor, and a low one proves little.** The gate counts
  the paragraph coordinates a shipped sentence names that neither the structural diff localised
  nor the capped evidence contains: 0 over the recording of 2026-08-08, 1 over the recording of
  2026-08-09, and **0 again over the tree as it ships**, over two further recordings of
  2026-08-12. The one sentence that ever produced the 1 was on `32017R0745@20170505` `AR 2`, and
  neither replacement names an article coordinate at all, so the check has nothing to catch rather
  than nothing to complain about, and the count is back to proving less than the 1 did. It
  undercounts by construction. The recogniser is deliberately conservative and a mention it misses
  is never counted; a coordinate whose own text is visible on one shown side counts as supported
  however wrong the sentence naming it is. And a low number after the cap raise is substantially a
  fact about the corpus rather than about the check: at a cap the texts rarely overrun, nearly
  every coordinate is visible, so the prompts have largely stopped exercising it and synthetic
  tests are what keep it able to fire. The one instance it has ever produced was a notation
  mismatch, a sentence citing "point (30) of Article 2(1)" of a path the markup spells `AR 2 ALN 1
  PO 30`, on an entry the reviewer ticked. That is why the check counts and never drops, and why a
  zero here is never read as the check having passed.
- **The shipped changelog carries no applicability note at all.** The gate drops a note that is
  not a verbatim quotation of the after text as the model was shown it, and the count reaches the
  output. That check is not what emptied the field: the recording that ships writes no note on any
  of the nine changes of the MDR postponement, so `notes_dropped` is 0 across both the run set and
  the subset because none was written rather than because every one passed. An earlier recording
  wrote three, of which `Art. 59` was a verbatim quotation and would have survived the check, and
  the committed golden (`tests/output/golden/mdr-changelog.md`) has carried none since. Prompt
  rule 7 calls the note optional and usually omitted, so this sits inside what was asked for; it
  is still a reader-visible loss, and it is named here rather than left to be noticed. Three
  recordings in a row have written none, the third over prompts carrying the repaired verbatim
  text, so this is the expected behaviour of the pinned model on this prompt rather than one run's
  accident.
- **Every model-layer figure describes one recording of one subset by one pair of models.** The
  committed cassettes are recorded against `openrouter:anthropic/claude-sonnet-5` as the explainer
  and `openrouter:openai/gpt-5.6-sol` as the judge, and each file declares `"synthetic": false`.
  The set of 2026-08-09 was superseded on 2026-08-12: the boundary-separator fix moved every
  stored text, so all 55 pinned subset prompts, the 9 of the MDR postponement, the 4 pinned prompt
  shapes and all 20 judgements were recorded again that day, and the superseded files were
  deleted, because a recording nothing will ask for again is a number about a prompt the project
  no longer sends. Two earlier dated exceptions inside the 2026-08-09 set are now history rather
  than live: one exchange and its judgement on 2026-08-11 for the instruction-scope fix, and three
  exchanges plus one judgement earlier on 2026-08-12 for the `disputed` correction. None of it is
  a claim about models in general. The explanation-faithfulness rate is the weakest number
  published: 16 of 20 (0.800), which is one model's opinion of another's sentences at n = 20,
  where a single entry moves the rate by 0.05.
- **The published faithfulness rate has been 0.800, 0.850 and 0.800 in turn, and no two of those
  are comparable.** Nothing in the sequence is evidence that the model improved or declined, and
  it must never be published as though it were. Three things have moved under it, and each changes
  what the number means rather than what the prose is worth. The question widened on 2026-08-09 to
  ask whether every sentence follows from *the evidence the writer was given*, header included,
  where it had asked about the two texts alone; the character cap rose from 8 000 to 40 000 the
  same day, so all but one entry of the sample now shows whole provisions on both sides; and on
  2026-08-12 the stored verbatim text stopped running words together across block boundaries, so
  every prompt and every judged text is a different string. A rate answering a narrower question
  over shorter evidence is not the same measurement, and a rate over new prose about repaired
  evidence is not the previous one moving. The hand-reviewed rate moved with the question too, 15
  of 20 (0.750) on 2026-08-08 against 18 of 20 (0.900) on 2026-08-09, over samples that share 10
  of their 20 units, and it is not a trend line either. Two readings under the widened question
  have followed, 18 of 20 (0.900) on 2026-08-11 and 17 of 20 (0.850) on 2026-08-13, and that 0.850
  is not the 0.900 declining: they read two recordings of different prompts, at n = 20 where a
  single entry is worth 0.05, and neither is adjusted for the other. The reading of 2026-08-09
  concluded that the widened question moved nothing on its own sample: no entry there rests a
  coordinate on the header alone, so every tick is one the narrower question would have produced
  too. Every number is published as measured, under its own date, none is adjusted for another,
  and every verdict stands against the question it answered.

