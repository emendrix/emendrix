# Judge benchmark — 2026-08-09

- **Labels** — reports/faithfulness-review-2026-08-08.md, reviewed by Martins Erts on 2026-08-08, transcribed verdict by verdict into `faithfulness-signoff-2026-08-08.json` beside it.
- **Entries** — 20, joined to each judge by `sha256` of the judge prompt, so a judge is scored on the exact strings the reviewer read.
- **Recorded judgements no entry claims** — 0 for the labelled judge, 0 for the challenger; counted here rather than dropped.

**What this is.** Twenty entries, one reviewer, one afternoon, one sample of one corpus. It is a
benchmark in the sense of "the only evidence this project has about how far a judge can be
trusted", not in the sense of "a benchmark". Nothing here generalises to other prose, other
corpora or other reviewers, and at n = 20 a single entry moves the rate by 0.05, so no confidence
interval is printed: an interval would be wider than the number is useful.

**What this is not.** It is not the faithfulness rate. Faithfulness asks whether the shipped
sentences follow from the two texts; this asks whether a judge agrees with a person about that.
The two are reported in separate artifacts on purpose and neither is folded into the other. The
prose these twenty entries rule on was recorded on 2026-08-08 and superseded the same day, so this
is not a measurement of what ships now either: it is a measurement of the instrument.

**Which comparison this is.** The challenger answered under the rubric currently in git and the labelled judge answered under the rubric of 2026-08-08, before rubric digests were recorded and before four failure classes were spelled out in it. This therefore measures the **pair** (this model under this rubric) against the pair that produced the labels, and not the model on its own.

## Judges

| Judge | Rubric | Agreement | Misses | Lenient | Strict |
|---|---|---|---|---|---|
| `openrouter:anthropic/claude-sonnet-5` | not recorded (taken before the rubric entered the cassette key on 2026-08-08) | 15 / 20 (0.750) | 5 | 5 | 0 |
| `openrouter:openai/gpt-5.6-sol` | `85dc3b14eec8` (the rubric in git) | 15 / 20 (0.750) | 5 | 1 | 4 |

**Lenient** means the judge called an entry faithful where the reviewer did not. It is the
direction that matters, because a lenient judge inflates every faithfulness rate it ever produces,
always upward and never visibly. **Strict** is the reverse and costs the project nothing but a
worse-looking number.

**How to read the result**, stated before it is given so that it cannot be chosen after the fact.
If the challenger beats the labelled judge's agreement *and* its misses are not systematically
lenient, the change of model did what it was chosen to do. If it does not, the rubric changes made
since the labels were taken mattered more than the model did, and that is the honest finding: the
project keeps whichever judge the evidence favours, in a separate deliberate change, and never
tries a third judge until one scores well.

**The result.** The challenger agreed with the reviewer on 15 of 20 where the labelled judge agreed on 15 of 20, so the two are **indistinguishable** on this set (1 lenient, 4 strict against the labelled judge's 5 and 0). At n = 20 an equal count is not evidence that the two judges are alike, only that this sample did not separate them.

## Where each judge disagreed with the reviewer

`openrouter:anthropic/claude-sonnet-5` disagreed with the reviewer on 5:

- **2. 32024R1689@20260727 AR 4** — lenient; the judge said `faithful=true`. The reviewer said `faithful=false`: AI Act AR 4. Sentence 3 attributes the adoption of recommendations jointly to the Commission, Member States and the Board, but paragraph 3 gives that task to the Board alone; it also says the recommendations are "based on European competence frameworks" where the text says only "taking into account".
- **3. 32024R1689@20260727 AR 6** — lenient; the judge said `faithful=true`. The reviewer said `faithful=false`: AI Act AR 6. Sentence 3 says paragraph 1c "excludes from the high-risk category", but the text says only that such a product "shall not be considered as fulfilling the condition in paragraph 1, point (b)"; that defeats the paragraph-1 route while the Annex III route in paragraph 2 is untouched, so the stated exclusion is a conclusion the texts do not show.
- **5. 32024R1689@20260727 AR 27** — lenient; the judge said `faithful=true`. The reviewer said `faithful=false`: AI Act AR 27. Sentence 1 says deployers may "satisfy the fundamental rights impact assessment requirement by cross-referencing", but the text only permits the deployer, when conducting that assessment, to include cross-references to or relevant parts of the data protection impact assessment; the assessment itself must still be performed, so the sentence states an effect the texts do not show.
- **17. 32006R1907@20081012 AN IV** — lenient; the judge said `faithful=true`. The reviewer said `faithful=false`: REACH AN IV. Sentence 3 claims "some existing entries were reordered", but walking both tables shows every surviving entry keeps its relative order; the versions differ only by removals, insertions placed at their sorted positions, and wording tweaks, so the reordering is a difference the texts do not show. The additions and removals in sentences 2 and 3, and the wording examples, all check out.
- **18. 32017R0745@20170505 AR 2** — lenient; the judge said `faithful=true`. The reviewer said `faithful=false`: MDR AR 2. The visible text stops mid-sentence at the opening words of point (27) in both versions, so "and beyond" asserts sameness over text not shown; the truncation markers differ (10 599 vs 10 600 characters omitted), meaning the actual modification lies entirely in the omitted part and nothing in the sentence is verifiable from the texts as given.

`openrouter:openai/gpt-5.6-sol` disagreed with the reviewer on 5:

- **2. 32024R1689@20260727 AR 4** — lenient; the judge said `faithful=true`. The reviewer said `faithful=false`: AI Act AR 4. Sentence 3 attributes the adoption of recommendations jointly to the Commission, Member States and the Board, but paragraph 3 gives that task to the Board alone; it also says the recommendations are "based on European competence frameworks" where the text says only "taking into account".
- **6. 32024R1689@20260727 AR 30** — strict; the judge said `faithful=false` (Sentence 2 overstates the delegated power by saying categories may be moved; the text permits moving only a code or type of AI system from one category to another.). The reviewer said `faithful=true`.
- **8. 32024R1689@20260727 AR 57** — strict; the judge said `faithful=false` (Sentence 3 misstates paragraph 5 by saying it requires appropriate safeguards “in sandbox plans”; the amended text requires that appropriate safeguards be in place, while separately requiring the sandbox plan to incorporate the real-world testing plan where applicable.). The reviewer said `faithful=true`.
- **10. 32024R1689@20260727 AR 69** — strict; the judge said `faithful=false` (Sentence 1 incorrectly states that Member States pay at the specified rate, whereas the text says they may be required to pay fees at that rate.). The reviewer said `faithful=true`.
- **19. 32017R0745@20200424 AR 59** — strict; the judge said `faithful=false` (Sentence 3 mischaracterizes the textual change as a power to “recognise” authorisations; paragraph 3 instead adds that the Commission may extend to the Union, for a limited period, the validity of specified authorisations granted under the earlier directives before 24 April 2020.). The reviewer said `faithful=true`.

## Entry by entry

| # | Change | Reviewer | `openrouter:anthropic/claude-sonnet-5` | `openrouter:openai/gpt-5.6-sol` | Reviewer's note |
|---|---|---|---|---|---|
| 1 | `32024R1689@20260727 AR 1` | faithful | faithful | faithful | — |
| 2 | `32024R1689@20260727 AR 4` | **not faithful** | faithful | faithful | AI Act AR 4. Sentence 3 attributes the adoption of recommendations jointly to the Commission, Member States and the Board, but paragraph 3 gives that task to the Board alone; it also says the recommendations are "based on European competence frameworks" where the text says only "taking into account". |
| 3 | `32024R1689@20260727 AR 6` | **not faithful** | faithful | **not faithful** | AI Act AR 6. Sentence 3 says paragraph 1c "excludes from the high-risk category", but the text says only that such a product "shall not be considered as fulfilling the condition in paragraph 1, point (b)"; that defeats the paragraph-1 route while the Annex III route in paragraph 2 is untouched, so the stated exclusion is a conclusion the texts do not show. |
| 4 | `32024R1689@20260727 AR 17` | faithful | faithful | faithful | — |
| 5 | `32024R1689@20260727 AR 27` | **not faithful** | faithful | **not faithful** | AI Act AR 27. Sentence 1 says deployers may "satisfy the fundamental rights impact assessment requirement by cross-referencing", but the text only permits the deployer, when conducting that assessment, to include cross-references to or relevant parts of the data protection impact assessment; the assessment itself must still be performed, so the sentence states an effect the texts do not show. |
| 6 | `32024R1689@20260727 AR 30` | faithful | faithful | **not faithful** | — |
| 7 | `32024R1689@20260727 AR 43` | faithful | faithful | faithful | — |
| 8 | `32024R1689@20260727 AR 57` | faithful | faithful | **not faithful** | — |
| 9 | `32024R1689@20260727 AR 60a` | faithful | faithful | faithful | — |
| 10 | `32024R1689@20260727 AR 69` | faithful | faithful | **not faithful** | — |
| 11 | `32024R1689@20260727 AR 72` | faithful | faithful | faithful | — |
| 12 | `32024R1689@20260727 AR 75b` | faithful | faithful | faithful | — |
| 13 | `32024R1689@20260727 AR 76` | faithful | faithful | faithful | — |
| 14 | `32024R1689@20260727 AR 96` | faithful | faithful | faithful | — |
| 15 | `32024R1689@20260727 AR 111` | faithful | faithful | faithful | — |
| 16 | `32024R1689@20260727 AN VIII` | **not faithful** | **not faithful** | **not faithful** | AI Act AN VIII. The shipped sentence has the direction of the change reversed. In the Before text, Section B item 8 ends …recalled); and in the After it ends …recalled). — so a semicolon became a period, while the sentence claims item 8 "now ends with a semicolon instead of a period". It also claims item 9 "has been renumbered", but item 9 is item 9 in both texts. |
| 17 | `32006R1907@20081012 AN IV` | **not faithful** | faithful | **not faithful** | REACH AN IV. Sentence 3 claims "some existing entries were reordered", but walking both tables shows every surviving entry keeps its relative order; the versions differ only by removals, insertions placed at their sorted positions, and wording tweaks, so the reordering is a difference the texts do not show. The additions and removals in sentences 2 and 3, and the wording examples, all check out. |
| 18 | `32017R0745@20170505 AR 2` | **not faithful** | faithful | **not faithful** | MDR AR 2. The visible text stops mid-sentence at the opening words of point (27) in both versions, so "and beyond" asserts sameness over text not shown; the truncation markers differ (10 599 vs 10 600 characters omitted), meaning the actual modification lies entirely in the omitted part and nothing in the sentence is verifiable from the texts as given. |
| 19 | `32017R0745@20200424 AR 59` | faithful | faithful | **not faithful** | — |
| 20 | `32017R0745@20260101 AN I` | **not faithful** | **not faithful** | **not faithful** | #20 — MDR AN I. Sentence 1 claims the "where justified pursuant to Section 10.4.2" qualification is new, but that exact phrase is already present in the Before excerpt (both visible portions are identical, ending at the same spot in 10.4.1). Sentences 2 and 3 describe changes to 10.4.2(d), 10.4.3 and 10.4.4, none of which appear in either excerpt — the real change is inside the ~43k truncated characters, so nothing in these sentences is verifiable from the texts as given. |

---

**Not legal advice.** These figures describe agreement between machine-computed readings of published legal texts. They say nothing about whether any change matters to anyone, and nothing here is a substitute for reading the official consolidated text on EUR-Lex or for professional legal counsel.
