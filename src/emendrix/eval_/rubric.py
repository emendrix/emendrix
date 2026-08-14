"""The judge's whole instruction, and the prompt one triple becomes. Literal text, in git.

Separated from `judge.py` for the same reason `explain/prompt.py` is separated from the engine:
a prompt is the specification of a non-deterministic step, and a rubric that drifts between runs
makes the numbers it produced incomparable. Changing what the judge is *asked* should be a diff
nobody can mistake for a change to how the answers are counted. **The rubric enters the cassette
key** (`judgements.py`), so editing the text below invalidates every committed judgement instead
of silently replaying verdicts taken under an older instruction, which is what makes that claim
true rather than aspirational.

The judge rules on the evidence the writer was given: the pipeline header the writer's prompt
opened with, the before text, the after text, the sentences that shipped, and the surrounding
context block when the prompt carried one. The header joined that list on 2026-08-09. The explain
prompt prints the deterministic pipeline's own reading (change type, provision, dates, the
sub-provisions that differ) into every user message, so a judge shown only the two texts is asked
whether sentences follow from evidence it was never given, and any sentence resting on the header
is unfaithful by construction. Measured on 2026-08-08 across the 63 committed prompts: the shipped
sentences name 109 paragraph coordinates and 52 of them appear only in the header under a strict
reading of the visible text, so the exposure was systematic rather than one entry's accident. One
boundary keeps the wide reading contained: header facts ground claims about which provisions
changed, and only the two texts ground claims about what the words say. The citation keys reach
neither the judge nor the worksheet.

**Those strings arrive capped exactly as the explainer saw them**, carrying the explain stage's
own truncation marker, and this module deliberately has no cap of its own. A second, shorter cap
does not sample the evidence more coarsely, it asks a different question: on any provision longer
than it, the judge rules on a prefix of a text the model read more of. Two of the three failures
in the first real 20-triple sample were exactly that and said so in their own words. With one cap
in the project, a sentence describing text beyond the marker is a real defect again, because the
model could not see past it either.

**The surrounding context is evidence, not a third text.** The explain prompt can print an
enclosing provision under `SURROUNDING CONTEXT`, and the rubric takes the wide reading: the judge
rules on the evidence the writer had, so a sentence resting only on the context is faithful. That
is the reading the single cap already forces for the two main texts, and one project cannot hold
both. The block is latent throughout this corpus (0 of 55 eval prompts and 0 of 9 run prompts
carry it, because `ExplainContext.surrounding_text` is `None`) and is settled anyway, because the
moment it stops being latent it is a wrong number.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

__all__ = ["CONTEXT_LABEL", "HEADER_LABEL", "JUDGE_RUBRIC", "judge_prompt"]

JUDGE_RUBRIC = """\
You are auditing one entry of a machine-generated changelog of legal texts.

You are given the BEFORE text of a provision, the AFTER text of the same provision, and the
SENTENCES that were published about the difference between them. Entries may open with a
PIPELINE HEADER block, which is what a deterministic pipeline established about the change and
showed the writer alongside the texts. Some entries also carry a SURROUNDING CONTEXT block,
which is the enclosing provision the writer was shown for reference and is not itself the
change. Judge one thing only:

    Does every published sentence follow from the evidence the writer was given?

The header states what a structural diff established: which provision this is, what type of
change it is, and which sub-provisions differ. Treat it as true. It grounds a claim about which
provisions changed. It grounds no claim about what the words say: for that, only the two texts
count. A sentence that reports a coordinate from the header and declines to describe it is
faithful.

Take the sentences one at a time and check each against the evidence. One unfaithful sentence
makes the whole entry unfaithful, and `issue` must then say which sentence, by its number.

Mark it unfaithful if any sentence:
  - states a difference the two texts do not show, or misstates one they do;
  - adds content that is in none of the texts: a date, a number, an obligation, a party;
  - gives advice, an opinion, or a prediction about consequences;
  - describes the wrong direction of a change (says something was added that was removed);
  - says what the change legally accomplishes rather than what the words changed. A narrow
    textual change restated as a broader legal conclusion is unfaithful even when the conclusion
    sounds right: "shall not be considered as fulfilling the condition in paragraph 1, point (b)"
    is not "excludes from the category", because you cannot see from these texts what else leads
    into that category;
  - claims that entries were reordered, renumbered, added or counted a certain way, unless both
    texts make it explicit. Walk the two lists and compare them item by item; a summary that
    sounds like what a text of this kind usually does is not evidence;
  - names an actor the text does not name in that role, or widens, narrows or reassigns who does
    what;
  - describes content beyond a truncation marker. A text may be cut short and the cut is marked
    in it; nothing past that marker was shown to the writer or to you, so a claim about it cannot
    be verified and is unfaithful. This includes claiming that the rest of two texts agree.

Do not mark it unfaithful for being brief, dull, incomplete, or for quoting one of the texts
verbatim: a quotation of the provision is faithful by construction. Do not mark it unfaithful for
resting on the SURROUNDING CONTEXT block: that block is part of the evidence the writer had. You
are not assessing style, usefulness or legal significance, and you are not being asked whether the
change matters.

Answer with `faithful` and, when it is false, one sentence in `issue` naming the specific
problem. If you are not sure, answer `faithful: false` and say what you could not verify."""
"""The judge's whole instruction, as literal reviewable text — snapshot-tested, like the
explain stage's prompt. A rubric that drifts between runs would make the numbers it produces
incomparable, so it is a constant in git rather than a string built at call time."""


CONTEXT_LABEL: Final = "SURROUNDING CONTEXT (the enclosing provision, not itself the change)"
"""The heading the context block is printed under. Says what the block is, so the judge can tell
"the provision changed like this" from "here is the enclosing provision for reference"."""

HEADER_LABEL: Final = "PIPELINE HEADER (established by the deterministic pipeline, not a text)"
"""The heading the header block is printed under. Says the pipeline established these facts, so
the judge can tell "the pipeline concluded this" from "this is the text of the provision"."""


def _side(label: str, text: str) -> str:
    """One side of the change, as shown. Never shortened here: see the module docstring."""
    if not text:
        return f"{label}: (none — this side of the change does not exist)"
    return f"{label}:\n{text}"


def judge_prompt(
    before: str, after: str, sentences: Sequence[str], context: str = "", header: str = ""
) -> str:
    """The whole user message for one triple. Plain strings in, one prompt out.

    Takes plain strings rather than the `Triple` that holds them so this module imports nothing
    from the machinery that counts the answers — the rubric is text, and text has no
    dependencies. `before`, `after` and `context` are what the model was shown, truncation marker
    included, and it is the caller's job to hand over those strings rather than the verbatim
    provision. `header` is the deterministic-facts block the writer's prompt opened with, byte
    for byte, and it is printed first for the same reason: the judge rules on the evidence in
    the order the writer saw it.

    An empty `context` prints no block at all, rather than the "(none)" line an absent side of
    the change gets: a change with no enclosing provision to show is the ordinary case across
    this corpus, and saying so twenty times would read as a fact about the change. An empty
    `header` is omitted the same way, which keeps the prompts of triples recorded before the
    header entered the evidence base derivable unchanged.
    """
    published = "\n".join(f"{index + 1}. {text}" for index, text in enumerate(sentences))
    blocks = [f"{HEADER_LABEL}:\n{header}"] if header else []
    blocks.extend([_side("BEFORE", before), _side("AFTER", after)])
    if context:
        blocks.append(f"{CONTEXT_LABEL}:\n{context}")
    blocks.append(f"SENTENCES:\n{published}")
    return "\n\n".join(blocks)
