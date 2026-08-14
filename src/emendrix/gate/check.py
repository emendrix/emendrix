"""The GATE stage: parse → resolve → containment, deterministically, on every sentence.

No model call, no network, no clock, no randomness. Given the same explanation, the same
context and the same trees, this module returns the same `GateResult` byte for byte — which
is what lets a changelog be diffed in git and a grounding rate be a number rather than a mood.

## Where "parse" went

A citation check has three questions in it: does the citation parse, does it resolve to a real
provision, and is it within the set offered to the model. Here the first two collapse into one
lookup, and that is a strengthening rather than a shortcut. A citation is not a syntax the model
composes, it is an **opaque token minted by the caller** (`explain/context.py`), and the model
has no field to put a URL in (`explain/schema.py`). So "does it parse" is exactly "is it one of
the tokens this side offered", and what is behind an offered token is an already-parsed
`ProvisionRef`. A malformed citation is therefore not a distinct outcome: it is an unknown key,
and it is rejected as one.

## One offered set, used twice

`ExplainContext` is the single source of truth: `explain/prompt.py` prints `context.offered` to
the model, and this module checks against the same object. There is no second construction of
the offered set to drift from the first, which is the classic silent hole in a gate like this
one.

## The gate does not judge content

A factually wrong sentence with a valid citation passes here, and is *supposed* to. Whether
what it says follows from the texts is faithfulness, measured separately against a different
reference. Blurring the two would make the grounding number mean nothing, which is the one
failure this project does not recover from.

## The one exception, and why it is not one

`note_is_verbatim` looks at the words of an applicability note rather than at its citations,
which sounds like the judgement this module just refused to make. It is not: the prompt asks
for the note to be a *verbatim quotation* of the AFTER text, so checking it is string
containment against a text the pipeline already holds, with no opinion about whether the
statement is right. The note is the one piece of model prose that reaches a reader under a
label the project supplies (`*Applicability:*`, beside a date computed deterministically), so
a paraphrase there reads as though the pipeline vouched for it. Measured 2026-08-08 over the
committed run cassettes, two of the three notes that shipped were paraphrases.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from emendrix.core import ProvisionLocation, ProvisionRef, ProvisionTree, normalize_for_comparison
from emendrix.explain import (
    CitedSentence,
    ExplainContext,
    Explanation,
    cap_text,
    mentioned_locations,
)
from emendrix.gate.results import (
    APPLICABILITY_NOTE,
    CitationFailure,
    FailureReason,
    GatedExplanation,
    GateResult,
    Resolution,
    SentenceFailure,
)

__all__ = [
    "ProvisionResolver",
    "TreeResolver",
    "check_explanation",
    "note_is_verbatim",
    "unsupported_coordinates",
]


class ProvisionResolver(Protocol):
    """Whether a provision exists in the version a citation names.

    Deliberately not "give me the provision": the gate needs a yes, a no, or an honest *I was
    not given that version's text*, and nothing else. Anything richer would invite the gate to
    start reading provisions, which is how a deterministic check grows an opinion.
    """

    def resolves(self, ref: ProvisionRef) -> Resolution: ...


class TreeResolver:
    """Resolution against the trees the pipeline already fetched. Never a network call.

    Keyed by `(act, version)` because one run holds two versions of the same act and, in the
    watch loop, several acts at once. A version nobody fetched answers `UNCHECKABLE` rather
    than `ABSENT`: "I have no text for that version" and "that version has no such provision"
    are different findings and only one of them is the model's fault.
    """

    def __init__(self, trees: Iterable[ProvisionTree]) -> None:
        self._trees = {(str(tree.act), str(tree.version)): tree for tree in trees}

    def resolves(self, ref: ProvisionRef) -> Resolution:
        tree = self._trees.get((str(ref.act), str(ref.version)))
        if tree is None:
            return Resolution.UNCHECKABLE
        return Resolution.PRESENT if tree.find(ref.location) is not None else Resolution.ABSENT


_DETAIL = {
    Resolution.ABSENT: "which is offered but names no provision in {version}",
    Resolution.UNCHECKABLE: "which is offered but {version} was never fetched, so it is unchecked",
}

_REASON = {
    Resolution.ABSENT: FailureReason.UNRESOLVED,
    Resolution.UNCHECKABLE: FailureReason.UNCHECKABLE,
}


def _check_key(
    key: str, context: ExplainContext, resolver: ProvisionResolver
) -> CitationFailure | None:
    """One key: offered? then resolvable? `None` when it is both — the only way through."""
    offered = context.resolve(key)
    if offered is None:
        return CitationFailure(
            key=key,
            reason=FailureReason.UNKNOWN_KEY,
            detail=f"{key!r}, which was not offered for this change",
        )
    resolution = resolver.resolves(offered.ref)
    if resolution is Resolution.PRESENT:
        return None
    return CitationFailure(
        key=key,
        reason=_REASON[resolution],
        detail=f"{key!r}, " + _DETAIL[resolution].format(version=offered.ref.version),
    )


def _slots(explanation: Explanation) -> tuple[tuple[int, CitedSentence], ...]:
    """Every citing slot, in output order, the optional applicability note last."""
    numbered: list[tuple[int, CitedSentence]] = list(enumerate(explanation.sentences))
    if explanation.applicability_note is not None:
        numbered.append((APPLICABILITY_NOTE, explanation.applicability_note))
    return tuple(numbered)


def check_explanation(
    explanation: Explanation, context: ExplainContext, resolver: ProvisionResolver
) -> GateResult:
    """Check every citation of every sentence. Pure; the failures come back ordered.

    A sentence fails as a whole if any one of its keys fails, because a sentence stands on all
    of them: one bad citation is enough to make the claim ungrounded, and half-accepting it
    would ship a sentence pointing at something that is not there.
    """
    failures: list[SentenceFailure] = []
    citations = 0
    for index, sentence in _slots(explanation):
        citations += len(sentence.citations)
        rejected = tuple(
            failure
            for key in sentence.citations
            if (failure := _check_key(key, context, resolver)) is not None
        )
        if rejected:
            failures.append(SentenceFailure(index=index, text=sentence.text, citations=rejected))
    return GateResult(
        failures=tuple(failures),
        sentences=len(_slots(explanation)),
        citations=citations,
    )


def note_is_verbatim(note: CitedSentence, after: str, text_char_cap: int) -> bool:
    """Whether an applicability note quotes the AFTER text the model was actually shown.

    Containment rather than equality, because the note quotes one statement out of a longer
    provision. Whitespace is collapsed on both sides through the project's one normaliser, so a
    quotation that differs only in line breaks still counts; neither string is stored, and
    nothing here touches the verbatim text.

    Collapsing is all the normaliser does, which makes one property of the stored text
    load-bearing here: it can squeeze a run of whitespace but it cannot insert one, so
    containment rests on the stored text carrying a separator where the markup opened a block
    (`eu/formex/text.py`).
    Without that separator a note quoting `…or health. 2. The Member State…` the way a person
    would write it fails containment against a stored `…health.2.The Member State…` and is
    counted ungrounded although it quotes the law correctly.

    The reference is the **capped** text and not the whole provision. The note has to be a
    quotation of the evidence the model had, and a match against characters past the truncation
    marker is coincidence rather than quotation. `cap_text` is what defines "as the model was
    shown it" for the judge and the review worksheet too, so all three ask the same question of
    the same string.

    An empty AFTER, which is what a deletion has, is `False`: there is nothing there to quote.
    """
    quoted = normalize_for_comparison(note.text)
    if not quoted:
        return False
    return quoted in normalize_for_comparison(cap_text(after, text_char_cap)[0])


def unsupported_coordinates(
    explanation: GatedExplanation, context: ExplainContext, unit: ProvisionLocation
) -> tuple[str, ...]:
    """Coordinates the sentences name that nothing in the model's evidence supports.

    Defended the same way `note_is_verbatim` is: no opinion about whether any sentence is
    right. The recogniser reads coordinates off model prose (`explain.coordinates`), and each
    one is tested against the two sets the context builder computed from the trees:
    `localised`, what the diff localised, and `shown`, what the capped evidence contains.
    Support follows the path: a mention counts as supported when it, or a coordinate on the
    same path through it, is in either set. `paragraph 9` against a localised
    `PA 9 ALN 1 PTA (e)` is supported, and so is `9(e)` against a localised `PA 9`; the diff
    put a difference on that path, so the naming is grounded. `shown` is a leg of support
    because most mentions outside `changed_within` are sameness claims about paragraphs that
    genuinely did not change and were visibly on the page (measured 2026-08-08: 6 of the 7 a
    strict reading flagged), and counting those would flood the number with legitimate prose.

    Counted only, per coordinate naming, in output order, deduplicated within a sentence and
    not across sentences. Never counted for a sentence the gate itself wrote: a fallback
    sentence is quoted provision text, and this project does not pattern-match provision
    text. The applicability note is excluded too; it has its own counted, stricter check. A
    context whose sets were never computed answers nothing rather than everything
    (`coordinates_checked`).
    """
    if not context.coordinates_checked:
        return ()
    supported = context.localised | context.shown
    found: list[str] = []
    for item in explanation.sentences:
        if item.fallback:
            continue
        for mention in sorted(mentioned_locations(item.text, unit)):
            if not _on_a_supported_path(mention, supported):
                found.append(mention.canonical)
    return tuple(found)


def _on_a_supported_path(mention: ProvisionLocation, supported: frozenset[str]) -> bool:
    """Membership up to a shared path, over canonical strings; no tree and no text is read."""
    for depth in range(len(mention.segments), 1, -1):
        candidate = ProvisionLocation(segments=mention.segments[:depth]).canonical
        for given in supported:
            if candidate == given or given.startswith(f"{candidate} "):
                return True
    return False
