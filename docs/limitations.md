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

**A missed line break is the quietest defect here, and correcting one costs money.** Two were
found by reading, on 2026-08-12 and 2026-09-01, and each ran a sentence into the block it
interrupts: `59Derogation`, `CouncilRegulation`, `the following point is added:(i)`. Such text is
not malformed, raises nothing and passes every schema and type check in this project. The join
rule is now an invariant asserted over every committed package, and a tag that reopens it is
counted as `ParserCoverage.undetached_blocks` rather than silently joined, but the invariant is
only as wide as the fixtures: a package fetched at run time can carry a tag no fixture holds, and
the count is what makes that visible. The reason this matters more than a rendering blemish is
that an explanation is the one thing this pipeline cannot recompute. It is a paid, non-repeatable
call written about a particular pair of verbatim texts, so a text that moves after the call leaves
prose describing evidence the page no longer shows. Entries written from 2026-09-05 carry an
evidence digest and can be asked directly; the 5 261 changes published before that carry none, and
`scripts/validation/evidence_staleness.py` answers for them by comparing stored text against
today's parse.

**Blanket amendments make the reference set the silent one.** "…shall be replaced by … throughout
the text" is one annotation and dozens of touched provisions. Precision against the metadata
collapses and the diff is the one that is right. Those units are counted as their own class, not
as false positives, and the transitions stay in the corpus.

**An amending article that states its instructions in prose contributes one claim.** The
instruction parser reads a list item at a time where the drafting uses a list, and where it does
not, the whole article is a single clause: every alinea and paragraph of it is flattened into one
string and one record is written from that, keyed on the first coordinate at each depth found
anywhere in the merged text. An article stating two or three amendments in prose therefore names
at most one of them. This is not measurable from the published record, because a collapsed
instruction leaves nothing behind to count: there is no second claim missing from a total anybody
can recompute. The third signal is a measured cross-check rather than ground truth, which is the
standing reason a gap in it is counted and stated rather than approximated.

**An amending act rarely dates its own instructions, and its notice cannot date the ones it
stages.** Every instruction record carries the date it takes effect where the act's own text
states one: in the clause itself (*"… is deleted with effect from 26 June 2026;"*), in the
final-provisions article where that article names the coordinates the clause was drafted at
(*"Article 1, point (1), and Article 2, point (1), shall apply from 10 January 2025"*, both of
them), or, failing both, from the act's own date of application. Where the text states none, the
day is read from the act's own CELLAR notice, which publishes the entry-into-force and
application dates the Publications Office computed from that same text. Measured 2026-09-05 with
[`../scripts/validation/instruction_effect_dates.py`](../scripts/validation/instruction_effect_dates.py)
over the 168 amending acts whose packages this installation has fetched and the 4 610
instructions they yield: one of those four answers is reached for 1 956 of them (0.424), of which
the notice supplies 1 346; 2 654 carry no date at all. It read 1 714 (0.372) over the same acts
and the same instructions before a statement that writes out every point it defers was read to
all of them, and 585 (0.127) before the notice was read at all. Each is a reading of a different
rule over one cache, published under its own date, and none is adjusted for another.

Three shapes account for the gap that remains, and each of them withdraws a date rather than
guessing one. A deferral whose points are listed somewhere else (*"The following points of
Article 1 … shall apply from 27 June 2019:"*, whose points are drafted in the sub-list below it,
half of them with ranges and other acts inside them) names nothing the reader can separate, so
that article carries no date. A deferral written as a range (*"Articles 95 to 98"*, and
*"points (11) to (14)"* one level down) names units it does not write; the first takes the act's
own date away from the whole act and the second from the article it names. And a value outside
the span an act's dates fall in is counted and never read; `1001-01-01`, which 17 of the 295
cached notices write for a day a later decision will fix, is the one this meets, on 8 acts.

An act whose notice publishes several staged application dates publishes no act-wide answer on
the notice's own account: the annotation on each names the provision that *states* the date and
never the provisions the date covers, so the notice cannot place its own staging. The act's final
provisions can, and where every dated statement of the act was read in full and the days they
attribute cover every day the notice staged, the staging is placed and the act's own entry into
force stands for the rest. 72 of the 168 acts stage, carrying 2 406 of the 4 610 instructions,
and reading their statements in full places the staging on 4 of them. All of it is counted
rather than approximated, and an instruction whose date could not be read is claimed exactly as
it was before the date existed.

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

**Correcting a stale explanation is the only thing this project pays for twice, and it is
bounded by what it can be sure of.** `emendrix repair evidence` re-parses both versions of a
published transition and asks the model again about the changes whose evidence moved. Three
limits are worth knowing. A change the model fails on a second time keeps the sentences it has
and the stored text they were written about, so a reader is never shown prose about one text
beside another, and the change stays selectable for a later pass; it is counted as remaining and
is never reported as repaired. A pass with a change budget starts an entry or it does not, and
never asks about half of one, because a corrected text under an un-re-explained sentence is the
one state nothing downstream can detect. And a transition whose versions today's parser cannot
produce, which is a package the cache lacks or a version with no readable English, is counted and
named and its entry is left exactly as it is: a correction that cannot see the corrected text is
not attempted.

**Consolidation lags publication by roughly ten days**, and it is not a fixed number (10 days for
the AI Act, 17 and counting for the MDR). "Amended, consolidation pending" is a persisted,
exactly-once-resolving state; seeing it is normal, seeing it for a month is a finding.
