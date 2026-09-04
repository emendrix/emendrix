# Evaluation: what is measured, and what each number does not mean

The three-way corroboration the deterministic figures are scored against, the labelled corpus that
supplies its own ground truth, and how the model layer is measured without blurring citation
validity into explanation quality. The published table itself lives in
[`../README.md`](../README.md), generated from a committed report; this file is the reading of it.

## Corroboration: three answers to the same question

The diff is not the only thing that knows which provisions changed, and that is the point.
`emendrix.corroborate` merges it with two signals derived completely independently of it:

- **The corpus's own modification metadata.** The Publications Office publishes, in each act's
  branch notice, provision-level coordinates for every amendment ever made to it: 88 annotations
  for the AI Act's Digital Omnibus amendment, 391 for REACH. `emendrix.eu.modmeta` reads them.
  Their role codes have **no published English labels**, so the readings (`R` = replace, `J` =
  insert, `DEL` = delete, and three rarer ones) are empirical and documented as such in
  `eu/mod_roles.py`, with the counts they were established from.
- **The amending act's own instructions.** *"in Article 1(2), point (g) is replaced by the
  following:"* is a machine-readable order, and `emendrix.eu.instructions` reads it out of the
  markup rather than out of flattened prose, which is what recovers the identifiers EU drafting
  omits when it writes *"the following Article is inserted:"* without a number.

Both are **capabilities of the EU adapter, not part of the seam**: they hand the corroborator plain
`core.SignalReport`s, so `emendrix.corroborate` contains no legal vocabulary at all and runs on the
toy corpus unchanged.

Three rules govern the merge, and the first two are the reason the numbers are worth anything:

- **A signal that could not be computed is `UNAVAILABLE`, not dissent.** A corpus that publishes no
  amendment metadata is not disagreeing with the diff, and neither is a corpus that published
  none *for this pair of versions*: a window nobody annotated carries no reference set, so there
  is nothing for the diff to contradict. The second half of that rule was true of the vocabulary
  from the start and false of the EU adapter until 2026-08-12, which is why the disputed rate
  published before that date answers a different question. Where the corpus did annotate the
  window, a unit missing from the annotations is a real disagreement and still ships `disputed`.
- **Disagreement ships.** A unit the metadata names and the diff missed is appended to the delta as
  a change with a location, a kind and *no text*, since the diff is the only signal that carries
  text, and marked `disputed`. Nothing is dropped and nothing is merged away.
- **The unit is where signals are compared.** The two location vocabularies agree on the article or
  annex and not always below it, so an annotation on `AR 5 PA 1 ALN 1 PTA (bb)` is a claim about
  `AR 5`; inserting a point *into* Article 5 is a modification of it, not an insertion of it.

On the AI Act's Digital Omnibus amendment all three signals name the same 45 units and classify
every one of them the same way: precision, recall and F1 of 1.000 on all three pairings, zero
disputes. On the MDR's one-year postponement, the same. On REACH 2008 → 2009 they disagree loudly,
the diff finds 40 changed units and the metadata names 9, and the disagreement is *correct*: the
CLP Regulation ordered one word replaced "throughout the text", and the corpus annotates such a
blanket amendment once without enumerating where it lands. That transition ships 33 disputed
changes rather than being quietly dropped from the corpus, which is the whole argument for
publishing the disagreements.

## Measured, on a corpus that supplies its own labels

The claim that the diff finds the right provisions is not a sentence in a README; it is a
number anybody can recompute. `emendrix.eval_` generates a labelled corpus from the four acts'
own CELLAR notices: **18 transitions**, all of the AI Act and the MDR, a documented ten-transition
sample of REACH, and the DSA as a member with nothing yet to compare. It commits every document it
scores and runs the shipped pipeline over them offline.

Every number in the published table is read out of the newest committed report by
`uv run emendrix eval publish-readme`, and a test regenerates the section and fails on any
difference, so a figure there cannot drift from the run that produced it, and cannot be quoted
without the sentence that says what it does not mean.

**The table itself is in [`../README.md`](../README.md)**, between the `emendrix:metrics` sentinel
comments. It is generated, and there is one of it: a second copy here would be a hand-typed number
with nothing regenerating it, which is the failure this project exists to avoid.

Corpus coverage is **18 of the 70 transitions the four acts offer**, and 101 changes ship, 13 of
them marked `disputed`.

What those numbers do *not* mean is written into the report itself, in fixed text that does not
soften when a result is flattering. The short version: precision is dragged down by two named
classes where the *reference set* is the silent one, a blanket amendment CELLAR annotates once
and one act whose annexes the notices number in Arabic and the markup in Roman. A third class,
the corrigendum consolidation, does not enter the pairing at all: nobody annotated its window,
so there is no reference set to score against and the transition contributes neither units nor a
score. Until 2026-08-12 it was scored as a reference set that contradicted every unit the diff
found, and **the localisation and disputed figures before and after that date are not
comparable**, because one is computed over a denominator the other does not have. The disputed
figure moved again on 2026-09-04, when an amending article's own heading stopped being read as
the provision its instruction points at, and the two readings are not comparable either: three of
the changes counted before that date existed only because a claim named the amending act's own
article number, so the denominator differs, and the third signal now reads the amended act's
article numbers where it read the amending act's. Those transitions all stay in the corpus, their
disagreements are printed verbatim, and the units only the diff found are counted as their own
class rather than as errors.

```bash
uv run emendrix eval run --fixture-dir tests/fixtures/eu   # offline, what CI runs on every push
uv run emendrix eval publish-readme                        # regenerate the published table
uv run emendrix eval sample-digest                         # identify the faithfulness sample
uv run emendrix eval build-corpus                          # re-select and re-pin (network)
uv run emendrix eval build-subset                          # then this
```

The last two are a pair and run in that order. `build-corpus` writes `explain_subset: null`, and
`build-subset` is what fills it back in; stopping after the first leaves the model layer with no
pinned subset to measure over. `build-corpus` also stamps `built_on` from the clock, so
reproducing the committed `corpus.json` byte for byte takes
`--no-fetch --built-on 2026-08-06`, the date already in the file.

[`../src/emendrix/eval_/thresholds.py`](../src/emendrix/eval_/thresholds.py) commits a floor under
each headline number and CI fails when one is breached. A measured number may rise silently; it may
never fall.

## Measuring the model layer: grounding first, faithfulness separately

The last three rows of the table are a different exercise, and the discipline that keeps them
worth anything is that they are three rows and not one. Blurring citation validity into
explanation quality would produce a single flattering number and destroy the meaning of both.

They are measured over a **pinned explanation subset**: every explainable change of the flagship
AI Act transition (45) plus ten more sampled evenly across the other transitions, 55 changes in
all, chosen by a rule in `eval_/subset.py` and committed into `corpus.json` as explicit unit
locations, so a change that stops appearing in a delta shows up as a *named missing unit* rather
than as a quietly smaller denominator. The subset is small because each change in it is one
recorded exchange with a provider, committed under `tests/cassettes-eval/` and replayed offline.

- **Citation grounding** is a property of the deterministic gate: the share of changes whose
  first explanation cited only keys it had been offered. It is computed by running the *shipped*
  path, explain → gate → revise → settle, through `graph.stages`, over the subset, so the
  retry policy being measured is the retry policy that ships.
- **Faithfulness** is judged, not computed. Twenty triples are sampled (evenly, seedlessly) and
  each is shown to a different and stronger model (`openrouter:openai/gpt-5.6-sol`, against the
  explainer's Sonnet 5) as three strings: the before text, the after text and the sentences that
  shipped, plus the enclosing provision when the prompt carried one. No signals, no metadata, no
  change type, so the judge is answering the question actually being asked. It is *not* an
  independent check: both models read the same public English, and shared blind spots survive a
  change of vendor. The committed judgements were taken under this cross-vendor pair, and
  the report names whichever pair produced the number it prints.
  The genuinely independent one is a person, so every run also writes
  `reports/faithfulness-review-<date>.md`, the same twenty triples as an unticked checklist,
  and the report says `human review: pending` until somebody does it. Nothing in emendrix ticks
  a box on its own behalf.

**Both are measured over one recording, made on 2026-08-12 against the pinned models**, and every
committed cassette says `"synthetic": false`. Grounding is a fact about the deterministic gate on
that recording: 55 of 55 first answers cited only keys they had been offered, so the gate never
asked for a revision and never had to quote a provision itself. Every change of the subset reaches
the model, because the character cap leaves each of them something to describe; the stage
still refuses a prompt whose two texts the cap has made identical, and the report counts that case
whether it fires or not.

The faithfulness rate is published as measured and it is the weakest number in the table twice
over. It is a judge's opinion rather than a computation, and it is an opinion at n = 20: the
judge marked 16 of the twenty sampled triples faithful, so the table reads 0.800. Read that as
what one model said about another model's sentences and not as a measurement of correctness.

**That 0.800 is not the 0.850 of the recording before it declining.** The two are different
recordings of different prompts. On 2026-08-12 stored verbatim text stopped running words together
where the markup opened a block, which changed every prompt the explainer was sent and every text
the judge was shown, so the whole set was recorded again. The deterministic layer did not move by
a byte across that fix. A model-layer figure that moves under it moves because the model was given
better-formed evidence, which is a change of input rather than an improvement or a regression of a
measurement, and at n = 20 one entry is worth 0.05. Both rates are published under their own
dates and neither is adjusted for the other.

### The hand reviews

Twenty triples were read by hand on 2026-08-09, and that number is worth more than the
rate. The reviewer marked **18 of 20 faithful, 0.900**, against the judge's 0.850 on the same
sample. Both are published, and neither is folded into the other: the human number is the one with
no model in it. `reports/faithfulness-review-2026-08-10.md` is the ticked sheet, with a
one-sentence reason on each of the two failures. A sheet is named for the run date it was
generated for rather than the day it was read, and the two dates differ there because the sheets of
the two readings before it already hold their own names and a ticked sheet is never overwritten. A
fourth reading on 2026-08-11 came out at the same 18 of 20 over a sample that had moved by one
triple (`reports/faithfulness-review-2026-08-11.md`, signed off in
`reports/faithfulness-signoff-2026-08-11.json`).

**The recording of 2026-08-12 was read by hand on 2026-08-13: 17 of 20 faithful, 0.850**, against
the judge's 0.800 on the same sample. The ticked sheet is
`reports/faithfulness-review-2026-08-12.md`, transcribed into
`reports/faithfulness-signoff-2026-08-12.json`, with a one-sentence reason on each of the three
failures. It asks the same question as the reading of 2026-08-11, over a sample that had moved
twice on 2026-08-12: first `32017R0745@20170505 AR 2`, entry 18 of it, lost a dispute note when
the definition of `disputed` was corrected; then stored text stopped running words together across
block boundaries, which moved every prompt in the subset. The sign-off's digest stopped matching
on its own each time and the published line reverted with it, so all twenty were owed again even
where some carried sentences that resembled ones already read: a verdict is written against a
sample rather than against a triple. All three failures were also flagged by the judge.

**That 0.850 is not the 0.900 of the reading before it declining.** They are two readings of two
recordings of different prompts, not one number moving, and at n = 20 a single entry is worth
0.05. Both are published under their own dates and neither is adjusted for the other. Nothing here
re-scores a verdict a reviewer wrote, and nothing here ticks a sheet.

**That 0.900 is not the 0.750 of the reading before it improved.** Two things moved between those
two readings, and neither of them is the model getting better at its job. The question widened on
2026-08-09 to ask whether every sentence follows from *the evidence the writer was given*, which
includes the deterministic-facts header the prompt opens with; and the character cap rose far
enough that all but one entry of the sample shows whole provisions on both sides. A comparison
against 0.750 is not like for like. The earlier verdicts stand exactly as recorded, against the
question they answered, and are never re-scored under this one.

The single most useful thing that reading produced is a measurement of the widening rather than a
verdict: **no entry on that sample rests a coordinate on the header alone.** At the raised cap
every coordinate a sentence names is also readable in the shown text, so every tick is one the
narrower question would have produced too, and widening the evidence base changed no verdict on
that sample.

The two readers disagree on exactly one entry, the AI Act's `AR 76`, and there the judge was
the stricter one: it failed a sentence the reviewer ticked, on a misreading of the pipeline's own
coordinate notation. The reading of 2026-08-13 came out the same way, one entry apart and again
on `AR 76`, with the judge again the stricter reader. That reverses the pattern of the two
earliest readings, where every disagreement went the other way and the judge was lenient in all of
them (`reports/faithfulness-review-2026-08-08.md` and `reports/faithfulness-review-2026-08-09.md`,
scored in `reports/judge-benchmark-2026-08-08.md` and `reports/judge-benchmark-2026-08-09.md`).
Five readings in, what this project can honestly say about a judge of its own choosing is that it
disagrees with a person on between one and five entries in twenty and that the direction of the
disagreement is not stable, which is why the human number is published beside the judged one
rather than instead of it.

Each review is published through `reports/faithfulness-signoff-<date>.json`, a committed file a
person writes: the summary line, and their verdict on each of the twenty triples. One file per
sheet, and they accumulate, because an older review is the label set the judge benchmark scores
against. A report publishes the newest of them, and only while a digest over the exact sample it
reviewed still matches: re-recording a cassette, re-pinning the subset or a change ceasing to reach
the model at all sends the published string back to `pending` on its own, which is what the most
recent re-record did to the review before this one, and what widening the evidence base did to the
one before that, since the header the worksheet quotes is part of the digest. There is no override.
That is where the published string stands as of the report of 2026-09-04: re-recording four of
the subset's prompts on 2026-09-01 moved the sample the sign-off of 2026-08-13 was written
against, so the review lapsed on its own and twenty triples are owed a reading before any
hand-reviewed rate is published again. That reading of 17 of 20 stands as a reading of the
sample it covered, the judged rate beside it is unchanged at 0.800, and no sheet was ticked, no
sign-off back-dated and no verdict re-scored to avoid the lapse.
`uv run emendrix eval sample-digest` prints the digest and the entries the next review has to
cover.

```bash
uv run emendrix eval run                             # both layers; model layer replays offline
uv run emendrix eval judge-benchmark                 # score the judges against the hand review
uv run pytest -m "record and live" tests/eval        # re-record the subset (needs a key + budget)
```

The failure modes these numbers do not catch are in [`./limitations.md`](./limitations.md).
