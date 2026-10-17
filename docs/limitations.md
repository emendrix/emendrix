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

**The metadata names some changes by a code that is not a unit, and those are counted, not
resolved.** Since 2026-10-08 the corpus metadata's location codes are read as the units the
Formex markup names before they are compared: a legacy annex number in Arabic (`AN 4`) is the
markup's Roman one (`AN IV`), by an explicit converter that refuses rather than guesses beyond
Annex L, and a dotted article (`AR 3.1`) is the article it sits in (`AR 3`). Until that date
REACH's `AN 4` and `AN 5` shipped as two textless units beside the `AN IV` and `AN V` the diff
found, all four `disputed`; that was a difference of notation, and the published entries written
before the date still carry it until they are repaired. A code naming a part, chapter, title,
section or recital (`PRT`, `CHA`, `TIT`, `TIS`, `SCT`, `SECTION`, `P`, `CONSID`, or a bare `AN`)
is not a unit of change at all. It is no longer appended as a textless change: the metadata
signal's note says how many annotations in the window named one. **The articles under such a
container are not resolved from it**, because that needs the provision tree the notice does not
carry, so a diff unit whose only annotation names its chapter still reads as one the metadata
did not name, and ships `disputed`. A dotted annex code (`AN I.7`) is not rewritten either and
still reads as its own unit.

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

**What the third signal claims alone is published in the report, not as a change.** An undated
instruction belongs to every window its act touches, so a staged act names units in
consolidations whose text does not yet, or no longer, show them changing. Since 2026-10-08 a unit
only the instruction parse names, which neither the structural diff nor the corpus metadata
names, is not appended as a textless change: it is listed by name in the entry's corroboration
report as `instruction_only_units`, where a reader can still see it, and the eval counts it. A
unit the metadata names and the diff does not still ships as a textless change, `disputed`. From
the same date an instruction parse that claims nothing in a window is `UNAVAILABLE` there, with a
note that keeps its coverage figure, rather than available and silent, so it no longer marks every
unit the diff found as one it failed to see. Neither rule makes the parse read more: the clauses
it cannot date or cannot read are exactly the gap they were, and an instruction-only unit may
still be a real amendment the other two signals missed, which is why it is published rather than
dropped.

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
one moving. The same holds for the 0.750 over the recording of 2026-09-19, where the judge
failed one re-recorded explanation whose prompt had gained an annex's subject in its heading
line. It holds again on 2026-10-08, when one explanation and its judgement were recorded again
because the prompt of a REACH annex no longer said its change was disputed: the new verdict is
faithful as the old one was, the rate still reads 15 of 20, and the sample digest moved, so the
hand review stays owed. [`./evaluation.md`](./evaluation.md) reads the whole sequence, and
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

## Substance tables

Eight acts print tables whose rows the record reads as **table entries**, each keyed by the column
the act numbers its rows by and carrying the CAS, EC and CLP Index numbers its cells print: REACH
`32006R1907`, CLP `32008R1272`, Cosmetics `32009R1223`, Biocides `32012R0528`, PIC `32012R0649`,
POPs `32019R1021`, plant protection products `32009R1107` and Batteries `32023R1542`. The 28 tables,
and which column keys each and which carry numbers, are the profiles in
[`../src/emendrix/eu/substances/profiles.py`](../src/emendrix/eu/substances/profiles.py), read off
the markup on 2026-10-16 over every English consolidated version the disk cache held. The lens says
where a number **appears**, in the act's own row, and nothing about what the law makes of a
substance; [`./site.md`](./site.md) §"Substance pages" and
[`./output-format.md`](./output-format.md) §"The register" say what is published. These are its
gaps.

**Only the profiled tables are read, and some tables that print numbers are left out on purpose.**
CLP Annex VIII, the cement and concrete standard formulas, prints EC numbers in 20 of its tables,
but no column keys an entry: the numbers name the components of a formula, and the sub-header rows
that name its columns are not marked as headers in the markup. REACH Annex XVII Appendices 9, 10, 11
and 15 hold fewer than three cells with a valid number, below the threshold at which the survey of
2026-10-16 calls a table a substance table, and were never measured as entries. POPs Annex I Part B
and Annex II, and PIC Annexes III and VI, are header rows with no body. The tables an amending act
prints are evidence and not the record: three amending acts the cache held (`32009R0790`,
`32018R0172`, `32019R0330`) print such tables, and none is read. No other of the 130 acts the cache
held has a table with three or more valid numbers in any cached version
(`scripts/validation/results/substance-tables-survey-2026-10-16.txt`).

**A profile fails closed, so a reshaped table is counted and not read.** A table is read only at
its profiled position (act, unit, the container the parser places it in, its ordinal there) and
only when its header cells hold the words the profile requires. A table at that position whose
header fails to match is `unrecognised`: counted per side, listed in the register, and never
read, because a renumbered or replaced table would otherwise be read under another table's keys.
The measured case is PIC Annex V Part 2, unrecognised in its four versions before 2019-05-01,
whose two-column table printed no "No" column (the profiles' docstring states it).

**Three kinds of row are not diffed like the rest.** A row whose key cell is empty, a dash, or
an Index number failing its check character is **unkeyed**: kept, with its numbers, so the
register and the substance pages still list it, but never compared, and counted per side. A key
a table prints more than once is **repeated**: REACH Annex XVII prints entry `68` twice in every
version since 2022-03-01. Repeated keys pair first with first while both versions print the key
equally often, and a key printed a different number of times on the two sides is listed in
`unpaired` and none of its rows is diffed. And PIC, POPs, Biocides and REACH Annex XVII
Appendix 12 number nothing, so their entries are keyed by **name**, the first line of the name
cell with footnote markers removed and case folded. A renaming therefore reads as one entry
removed and another added. Measured on 2026-10-16 over every cached version of each, every
removal of a name key was a first line the act rewrote (a formula joined to the name, a synonym
added): PIC 50 removals, POPs 3, Biocides 1, Appendix 12 none (the profiles' docstring holds the
counts).

**A number failing its check digit is never published as an identifier.** The row still prints it
verbatim, so it is visible on the event and substance pages, but it has no page, no search label
and no file, and each entry counts it in `failed_check_digits`. The survey of 2026-10-16 found,
in the identifier columns of the eight acts' consolidations: in REACH, CAS `5455-55-1` (Annex XVII
entry 8, four versions, then corrected), `27741-01-3`, `736665-18-6`, `6472-05-8`, `14110-84-6`
and EC `270-760-3`, `274-544-0`, `247-684-6`; in CLP, EC `250-366-9`; in Cosmetics, CAS
`542-56-2`, `148-24-2`, `2611-07-2`, `84930-17-4` and EC `202-499-6`, `415-480-1`, `604-708-8`;
in PIC, CAS `92-92-3`, `115-32-3` and EC `278-636-6`, `200-273-9`, `210-172-5`, `401-210-1`,
`205-239-0`. EC `239-793-2` is printed with the same digit in five tables of three acts (both CLP
Annex VI tables, REACH Annex XVII Appendices 1 and 6, Cosmetics Annex II), so a reader looking
that number up finds nothing. An EC number whose weighted sum leaves a remainder of 10 is read as
written with check digit `1`: 223 of the 224 such values in the cache end in `1`, and the one
that does not, `200-233-3` in REACH Annex IV, is counted as failing. The full list, with rows and
versions, is in `scripts/validation/results/substance-tables-survey-2026-10-16.txt`.

**Many entries print no number, which is why a substance page never claims absence.** An entry
can name a group of substances ("lead compounds") and print no CAS or EC number at all. In the
newest version the survey read, 20 of the 73 entries of REACH Annex XVII's main table print none,
125 of the 4 444 entries of CLP Annex VI's first table, and 111 of the 154 entries of Cosmetics
Annex IV, whose colours are identified by Colour Index number. A number no entry prints may still
be covered by one of those. Absence therefore has one wording on every surface, "no entry in the
record prints this number", and a test refuses the words that would say more.

**Whitespace is not a change, and other typography is labelled rather than dropped.** Two paired
entries equal once whitespace collapses are counted as `whitespace_only` and are not changes: a
re-typesetting moves thousands of rows that way (CLP 2019-07-26 to 2019-12-01, 1 594 of them,
[`./output-format.md`](./output-format.md) §"The JSON"). An entry that differs in anything else is
`amended`, and `typography_only` marks one equal once spacing, dash forms and accents are set
aside. The label never removes the change from a page, a payload or a register. It does decide
one thing: a `substance` watch item in the account service is not notified of a typography-only
amendment, by email or in its feed, while act and provision items are unaffected because they
match on the structural diff ([`./accounts.md`](./accounts.md) §"Matching").

**The entry diff is not held against the amending acts as a signal.** Measured on 2026-10-16 over
the record at `6c4fcdc` (`scripts/validation/results/substance-crosscheck-2026-10-16.txt`): of 7500
entry keys the row diff called added or amended in REACH, CLP, Cosmetics, Biocides, PIC and POPs,
6977 (0.930) are printed or named by an amending act the change names; 267 of the rest changed only
in spacing, dash forms or accents, 199 are printed by an act the consolidation lists but the change
does not name, 41 carry their number under another key in the amending act, and 16 are a corrigendum
or unclassified. Agreement is about keys, not row content, and the Cosmetics and REACH Annex XVII
figures are upper bounds because entry numbers repeat across annexes. It is a measurement, not a
signal: no entry is marked disputed by it. Plant protection products and Batteries were not
cross-checked. The same reading found that the amending acts a change names miss one the
consolidation's own list holds in 54 of the 211 changes checked, so a page calls the amending act
"the act this change names", never the act that made the change.

**Cosmetics numbers its new rows only in the consolidation.** The amending acts print a new row
of a Cosmetics annex with the reference number `x`, and the consolidation assigns the number. A
key-only comparison cannot pair the two: the cross-check counts 41 keys whose row it found under
another key in the amending act, 26 of them in Cosmetics.

**Table interiors still give the diff no coordinates.** Rows are read beside the provision tree,
never as nodes of it, so a change inside a table still localises to the enclosing provision
(`AN VI`, `AN XVII`) and `changed_within` gets no finer. The entry diff names the rows; the
structural diff, corroboration, the eval figures and the flagship are computed exactly as without
it.

**Lookup is by CAS, EC and CLP Index number only.** A REACH Annex XVII entry number or a Cosmetics
reference number is shown in its row but is not a search label, a name is searched only as the
row prints it (no synonyms), and an Index number has no page of its own: it leads to the page of
the first CAS, else EC, number its entry prints, and an Index entry printing neither leads nowhere.
