# Known failure modes

Honesty rule 4: a tool that documents its own holes is more trustworthy than one that appears to
have none. These are the ones that would bite a real user, and none of them is a tuning problem.
Start at [`../README.md`](../README.md) for what emendrix does.

**The release's own limitations are enumerated in [`../CHANGELOG.md`](../CHANGELOG.md) under
"Known limitations", with the measurement behind each one.** That list is the authority on what
`0.1.0` cannot do, and it names limitations this file does not repeat. This file explains the
mechanisms: what breaks, why it breaks, and what a reader should watch for. Where the two describe
the same thing, the changelog is the fuller record and this file points at it rather than
restating its numbers.

**Renumbering is entirely unvalidated.** No renumbering occurred in any of the seven end-to-end
traces, and no CELLAR role code plausibly meaning "renumbered" exists in 540 observed annotations.
`RENUMBERED` is a change type the diff can produce and nothing has ever exercised. The ambition is
capped on purpose: emendrix reports a renumbering, it does not attempt to rewrite the
cross-references that break because of one. **Whole-provision deletion is unexercised for the same
reason.**

**Annexes are where the two location vocabularies stop agreeing.** Legacy REACH notices number
some annexes in Arabic (`AN 4`, `AN 5`) where the Formex markup and the newer notices use Roman
(`AN IV`, `AN V`). The same annex then appears as two units neither signal shares. Measured
2026-08-06: 4 of REACH's 20 annotated annex units. They ship `disputed` rather than being
reconciled by a guess.

**Text extraction degrades on older Formex generations.** Structure is stable from the 2006 schema
to the 2016 one; whitespace at element boundaries is not, and uncorrected it once reported *every*
article of REACH as modified. The fix is that a verbatim form and a comparison form are extracted
separately and neither is derived from the other, but the risk is a quality risk that scales with
the age of the act, not a solved problem.

**Blanket amendments make the reference set the silent one.** "…shall be replaced by … throughout
the text" is one annotation and dozens of touched provisions. Precision against the metadata
collapses and the diff is the one that is right. Those units are counted as their own class, not
as false positives, and the transitions stay in the corpus.

**`applies_from` is `unknown` far more often than not.** The dates are machine-tagged but the
binding that says which provision they govern is prose. It is populated only when the change
itself moves a date in the act's own application article; otherwise the answer is `unknown`, with
the applicable prose quoted verbatim. It is never inferred by the model. Many unknowns is the
correct outcome, and the metrics count them. The site lists the machine-readable dates a change
added to and removed from a provision's text, per change and gathered per act, as facts about the
text and nothing more: which of them a provision applies from is this field's answer, and where
it is `unknown` the site says so rather than picking one of the dates it just printed.

**Every model-layer figure describes one recording of one subset by one pair of models.** All four
committed cassette sets were recorded on 2026-08-12 against
`openrouter:anthropic/claude-sonnet-5`, judged by `openrouter:openai/gpt-5.6-sol`. They
are not a claim about models in general, and at n = 20 the faithfulness rate is not a claim about
much at all: over the recording of 2026-08-09 a person reading the same twenty triples found 18
faithful where the judge found 17, and over the prose of 2026-08-08, under a narrower question,
the two were 15 against 16 and 13 against 18. Every reading is published, and the hand one is the
number with no model in it. The readings are not a trend line: the question and the character cap
both moved between them, so a rising hand-reviewed rate is not the model improving. Nor is the
judge's 0.800 over the recording of 2026-08-12 the 0.850 before it declining: every prompt changed
when stored text stopped running words together, so that is a new recording rather than the old
one moving. [`./evaluation.md`](./evaluation.md) reads the whole sequence, and
[`../CHANGELOG.md`](../CHANGELOG.md) states which of those figures may be compared with which.

**A change whose whole difference falls past the character cap would ship without sentences.** The
stage refuses a prompt whose two blocks the cap has made identical, rather than asking for a
description of a difference it showed none of, and a reader of such an entry gets the two verbatim
texts and nothing else. None of the 55 subset changes is in that state today: the cap is high
enough that every one of them reaches the model with something to describe, and exactly one of
them still carries a truncation marker. The refusal stays because the cliff moved rather than
disappeared, and the report counts the case at zero rather than dropping the row. The
measurements behind that, which unit the lower cap refused and how far the one truncated prompt
overruns, are in [`../CHANGELOG.md`](../CHANGELOG.md).

**Explanations can still outrun their evidence, and the shape of it has changed.** The failures
the hand reviews find now sit over text fully visible on both sides rather than past a truncation
marker: all three that failed the reading of 2026-08-13, over the recording that ships, overstate
what visible text says, and so did both failures of the reading before it. That is the failure
mode a bigger cap cannot touch, and no deterministic check in this project covers it. The reading
of 2026-08-08, under the narrower question that preceded 2026-08-09, marked 3 of its 20 entries
unfaithful at the truncation marker in three different ways; those verdicts stand as measured
against the question they answered, and [`../CHANGELOG.md`](../CHANGELOG.md) separates the three,
because the separation is the finding rather than the count.

**The deterministic coordinate check is a floor in both directions.** The gate counts the
coordinates a sentence names that neither the structural diff localised nor the capped evidence
contains: **0** over the committed subset recording, where the recording of 2026-08-09 produced 1
and the two recordings of 2026-08-12 produced none. It undercounts, because a coordinate readable
on either shown side counts as supported however wrong the sentence naming it is. The only hit it
has ever produced was on an entry the hand review ticked: a sentence naming "point (30) of Article
2(1)" of the MDR, which the corpus's own markup spells with no numbered paragraph in the path at
all, so the coordinate resolved to nothing while the text it pointed at was fully visible. That
sentence is gone: its prompt lost a dispute note on 2026-08-12 and the exchange was recorded
again, and recorded again the same day when the stored text changed, and neither replacement names
an article coordinate at all. So the zero is the check finding nothing to look at rather than the
check passing, which is exactly why it only counts and never drops a sentence.

**Consolidation lags publication by roughly ten days**, and it is not a fixed number (10 days for
the AI Act, 17 and counting for the MDR). "Amended, consolidation pending" is a persisted,
exactly-once-resolving state; seeing it is normal, seeing it for a month is a finding.
