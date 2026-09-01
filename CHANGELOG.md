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
- **The CLI**: `diff`, `watch`, `explain`, `run`, `backfill`, `eval` and `site`, with the delay
  between network calls set by `--polite-delay` or `EMENDRIX_POLITE_DELAY_S`.

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

