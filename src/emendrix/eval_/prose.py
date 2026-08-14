"""The fixed text of every report: the rigour table, the caveats, the known holes.

Prose, not numbers, and deliberately in code rather than in a template somebody edits next to a
result they are pleased with. Two rules it keeps: every number is labelled with what it measures
and what it does not, and the known failure modes get a named section of their own.

Split from `report.py` so that changing what the project *claims* is a diff nobody can mistake
for a change to how it *measures*; reviewing a shift in either is the point.
"""

from __future__ import annotations

__all__ = ["DISCLAIMER", "KNOWN_CLASSES", "MEANING", "RIGOUR", "count"]


def count(number: int, singular: str, plural: str | None = None) -> str:
    """`0 changes`, `1 change`, `3 changes`; `1 entry`, `20 entries` when `plural` is given.

    Every `n` column of every eval report is a number and a noun, and a report that says
    `1 changes` reads as a rendering accident rather than as a measurement. These rows go into
    the methodology page and into `README.md` from the same committed report, so the phrasing
    is agreed once, here, beside the rest of the fixed report text.

    `plural` is explicit rather than derived because `eval_` counts entries as well as changes,
    transitions and units. `site_/markup.py` has a helper of the same shape whose contract is
    noun-plus-`s` and which says in as many words that an irregular does not belong in it. The
    two are duplicated knowingly rather than merged: `eval_` may not import a page-rendering
    module, and widening that one to carry irregulars would break the rule it is written around.
    """
    return f"{number} {singular}" if number == 1 else f"{number} {plural or singular + 's'}"


DISCLAIMER = (
    "**Not legal advice.** These figures describe agreement between machine-computed readings of "
    "published legal texts. They say nothing about whether any change matters to anyone, and "
    "nothing here is a substitute for reading the official consolidated text on EUR-Lex or for "
    "professional legal counsel."
)

RIGOUR: tuple[tuple[str, str, str, str], ...] = (
    (
        "**Localisation**",
        "Did the diff find exactly the provisions the amendment says it changed?",
        "The corpus's own modification metadata, published per amendment by the "
        "Publications Office",
        "**Free and objective.** Precision, recall and F1 on a set of provision "
        "identifiers. The headline number.",
    ),
    (
        "**Classification**",
        "Did it label the change insert / modify / delete correctly?",
        "The metadata's role codes, whose semantics are empirical and undocumented",
        "**Nearly free.** `DEFERRED` and `RENUMBERED` compare as `MODIFIED` by a stated "
        "convention, because they are refinements only the diff can make.",
    ),
    (
        "**Grounding**",
        "Did every generated sentence cite a provision that resolves?",
        "The citation gate itself",
        "**Free and objective**, over the pinned explanation subset — but it measures "
        "*citation validity*, not explanation quality.",
    ),
    (
        "Explanation quality",
        "Is the plain-English summary a faithful account of the difference?",
        "None — a sampled LLM judge and a human spot review, both weak",
        "**Never free.** Reported separately, at n = 20, and withheld outright when the "
        "judgements behind it came from a stub.",
    ),
)
"""The four-layer rigour table: what each layer measures, and against what reference."""

MEANING = "\n".join(
    (
        "## What these numbers do and do not mean",
        "",
        "| Layer | Question | Ground truth | Rigour |",
        "|---|---|---|---|",
        *(f"| {' | '.join(row)} |" for row in RIGOUR),
        "",
        """\
Five things this report is careful about, and a reader should be too:

1. **The unit is the top-level provision** — the article or the annex. Sub-provision
   coordinates ride along as detail and are not what these numbers score.
2. **The metadata is a reference set, not an oracle.** It annotates a blanket amendment once and
   does not enumerate the provisions it lands in, so a unit only the diff names is not
   automatically a false positive. Those units are counted as their own class below.
3. **Precision and recall are directional.** Precision is of the structural diff against the
   metadata: of the units the diff named, the share the metadata also named.
4. **Micro pools units, macro averages transitions.** Both are given; neither alone is the answer.
5. **Coverage is a fraction.** The corpus is a documented sample, and every version it could not
   read is listed with the state that made it unreadable.
6. **The layers are separate on purpose.** Localisation and classification are scored over every
   transition; grounding and faithfulness over a small pinned subset of changes, because each of
   those costs a recorded call to a model. Rows 3 and 4 never share a number: the third is a
   deterministic property of the gate, the fourth is a judgement, and merging them would make
   the honest number worthless.
""",
    )
)


KNOWN_CLASSES = """\
## Known systematic disagreements

Honesty rule 4: a tool that documents its own holes is more trustworthy than one that appears to
have none. Four classes below account for most of the disagreement in this report, and each is a
property of the sources rather than a tuning problem. None of the transitions they affect was
removed from the corpus.

1. **Blanket amendments are annotated once.** *"…shall be replaced by … throughout the text"* is
   one annotation and dozens of touched provisions. The diff finds them all; precision against the
   metadata collapses; the diff is the one that is right.
2. **Corrigenda are not amendments, and a window nobody annotated is not a disagreement.** A
   consolidation that carries only a corrigendum has *no* modification annotations in its window,
   because no amending act put it there. There is then no reference set to score against, so the
   metadata signal for that pair is `UNAVAILABLE` and the transition is left out of the
   localisation pairing entirely rather than counted as a perfect miss. It is still scored, still
   listed per transition, and its changes still ship; what it no longer does is report every unit
   the diff found as contradicted by a source that never spoke. Until 2026-08-12 the signal was
   reported as available with zero claims, which scored the pairing at zero precision and marked
   every such change `disputed`. The MDR's first consolidation is this case, and it is why the
   `n transitions` column of the localisation row can be lower than the number of transitions
   scored.
3. **The two location vocabularies do not always spell an annex the same way.** Legacy notices
   number some REACH annexes in Arabic (`AN 4`, `AN 5`, `AN 11`, `AN 17`) where the Formex markup
   and the newer notices use Roman (`AN IV`, `AN V`, …). The same annex then appears as two units
   that neither signal shares. Measured 2026-08-06: 4 of REACH's 20 annotated annex units.
4. **The instruction parse has two named blind spots.** It cannot read an instruction that
   delegates to the amending act's own annex, or one that expresses a range (*"Annexes VI to X"*),
   and it names an annex section without its annex when the prose does. These are counted as
   unread instructions, never approximated.
"""
