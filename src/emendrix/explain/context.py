"""What the model is shown besides the two texts: the citation keys it may use.

A citation key is an **opaque string the caller mints**. The model copies keys; it never
constructs one, and it has no field to put a URL in (`schema.py`). Resolving a key back to a
`ProvisionRef`, and from there to a clickable citation that only the adapter can render,
happens on this side of the call, in `OfferedCitation`.

That indirection is what keeps the explain stage corpus-agnostic: the default key is built
from the canonical location and the version tag, both of which the toy corpus has as much as
the EU one does. A caller that prefers `art4:v1` may mint that instead; nothing here reads a
key's contents.

Which provisions are offered is decided *structurally*, from the change type, and it is the
whole of the anti-hallucination invariant's second half: an insertion has no "before" to cite,
a deletion has no "after", so those keys are simply absent from the offered set and a sentence
that cites one fails the gate by construction.

The context also carries the two sets the gate's unsupported-coordinate check tests membership
against, `localised` and `shown`, computed here because this is the one place holding the
change, the trees and the cap at once. The gate is handed them as frozen data and does set
membership only, exactly as it is handed `offered`: a second construction of either set inside
the gate would be the classic silent hole `gate/check.py` names.
"""

from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Change, Delta, ProvisionLocation, ProvisionRef, ProvisionTree, VersionId
from emendrix.explain.capping import cap_text

__all__ = [
    "NOTHING_TO_EXPLAIN",
    "ExplainContext",
    "OfferedCitation",
    "build_context",
    "contexts_for_delta",
    "explainable",
]

NOTHING_TO_EXPLAIN = (
    "the structural diff did not see this change, so it carries no text; another signal named "
    "the unit and the disagreement ships as `disputed`"
)
"""Why a change can reach this stage with nothing to explain — and why that is not an error.

The corroborator appends a change for every unit the corpus metadata or the instruction parse
names and the diff did not (`corroborate/merge.py`). The diff is the only signal carrying
text, so those changes have a location, a kind, `disputed=True` and no quotable text at all.
They are routine — the REACH pair produces 32 of them — and they must ship, so the explain
stage records this reason against them and moves on rather than raising.
"""


class OfferedCitation(BaseModel):
    """One provision the model may cite, under one key.

    `ref` is the resolution the gate and the renderer need; `key` and `label` are the only
    two things the model ever sees.
    """

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1, description="The opaque token the model copies into output.")
    label: str = Field(min_length=1, description="Human form shown beside the key in the prompt.")
    ref: ProvisionRef = Field(description="What the key resolves to. Never shown to the model.")

    @classmethod
    def for_ref(cls, ref: ProvisionRef) -> OfferedCitation:
        """The default key for a provision: canonical location, version tag, corpus-agnostic."""
        return cls(
            key=f"{ref.location.canonical}@{ref.version}",
            label=f"{ref.location.human}, {ref.version}",
            ref=ref,
        )


class ExplainContext(BaseModel):
    """Everything handed to the model for one change, beyond the change itself.

    `surrounding` is optional and defaults to empty on purpose: a `Change` carries its own
    verbatim texts but not its parent's, and a caller holding the provision tree is
    the only one who can supply that. Inventing it here would be guessing.
    """

    model_config = ConfigDict(frozen=True)

    offered: tuple[OfferedCitation, ...] = Field(
        min_length=1, description="The complete set of keys this change's sentences may cite."
    )
    surrounding_heading: str | None = Field(
        default=None, description="Heading of the enclosing provision, when the caller has it."
    )
    surrounding_text: str | None = Field(
        default=None, description="Verbatim text of the enclosing provision, when available."
    )
    localised: frozenset[str] = Field(
        default=frozenset(),
        description="Canonical sub-provision strings the structural diff localised to.",
    )
    shown: frozenset[str] = Field(
        default=frozenset(),
        description="Canonical strings of sub-provisions whose own text the capped evidence "
        "contains, on either side.",
    )
    coordinates_checked: bool = Field(
        default=False,
        description="Whether `localised` and `shown` were computed from the trees. False "
        "suppresses the unsupported-coordinate count rather than letting two empty sets "
        "fake one.",
    )

    def key_for(self, ref: ProvisionRef) -> str | None:
        """The key this context offers for `ref`, if it offers one."""
        for offered in self.offered:
            if offered.ref == ref:
                return offered.key
        return None

    def resolve(self, key: str) -> OfferedCitation | None:
        """The offered citation behind `key`, or `None` — the gate's containment lookup."""
        for offered in self.offered:
            if offered.key == key:
                return offered
        return None

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(offered.key for offered in self.offered)


def _refs(change: Change, from_version: VersionId, to_version: VersionId) -> Iterator[ProvisionRef]:
    """The provisions a change may cite: whichever of its two sides actually exists.

    A renumbered provision is offered under both locations, because both are real: it is the
    one change type where the "before" key is not simply the same location in an older version.
    """
    act, location = change.provision.act, change.location
    if change.before is not None:
        before_location = change.previous_location or location
        yield ProvisionRef(act=act, version=from_version, location=before_location)
    if change.after is not None:
        yield ProvisionRef(act=act, version=to_version, location=location)


def _rekeyed(
    location: ProvisionLocation, keyed_at: ProvisionLocation, unit: ProvisionLocation
) -> ProvisionLocation:
    """A before-side coordinate of a renumbered unit, re-keyed under the unit's new location."""
    if keyed_at == unit:
        return location
    return ProvisionLocation(
        segments=(*unit.segments, *location.segments[len(keyed_at.segments) :])
    )


def _support(
    change: Change,
    before_tree: ProvisionTree | None,
    after_tree: ProvisionTree | None,
    text_char_cap: int | None,
) -> tuple[frozenset[str], frozenset[str], bool]:
    """The two coordinate-support sets, and whether they mean anything.

    `localised` is the diff's own localisation, `Change.changed_within`, as canonical
    strings. `shown` asks, for every sub-provision under the unit, whether its own verbatim
    text appears inside the capped text the model was shown; a coordinate visible on either
    side was shown. Containment is on the verbatim strings, exact by construction: a parser
    assembles a unit's text from the same fragments its descendants carry, and any separator
    it inserts at a block boundary is inserted by the enclosing element into its own stream,
    so a descendant's fragments still land contiguously and a descendant's text is a literal
    substring of the unit's. The comparison form is deliberately not used here: it collapses
    whitespace and separates at every boundary including the inline ones, so containment over
    it answers a different question from the one the model was shown the answer to.

    The final element is `False` when the cap was not supplied, a tree an existing side needs
    is missing, or a unit cannot be found in its tree, so a caller can never mistake "nobody
    looked" for "nothing is supported". `cap_text` appends a marker naming the dropped count;
    the slice takes it back off, because the marker is about the evidence and not part of it.
    """
    if text_char_cap is None:
        return frozenset(), frozenset(), False
    localised = frozenset(location.canonical for location in change.changed_within)
    shown: set[str] = set()
    unit = change.location
    for tree, text, keyed_at in (
        (before_tree, change.before, change.previous_location or unit),
        (after_tree, change.after, unit),
    ):
        if text is None:
            continue
        node = None if tree is None else tree.find(keyed_at)
        if node is None:
            return frozenset(), frozenset(), False
        body = cap_text(str(text), text_char_cap)[0][:text_char_cap]
        for inner in node.walk():
            if inner is node or not str(inner.text).strip():
                continue
            if str(inner.text) in body:
                shown.add(_rekeyed(inner.location, keyed_at, unit).canonical)
    return localised, frozenset(shown), True


def explainable(change: Change) -> bool:
    """Whether there is anything here for a model to read.

    False exactly for the textless changes the corroborator appends (see `NOTHING_TO_EXPLAIN`).
    Checked with `is None`, not truthiness: an empty provision text is a text.
    """
    return change.before is not None or change.after is not None


def build_context(
    change: Change,
    *,
    from_version: VersionId,
    to_version: VersionId,
    surrounding_heading: str | None = None,
    surrounding_text: str | None = None,
    before_tree: ProvisionTree | None = None,
    after_tree: ProvisionTree | None = None,
    text_char_cap: int | None = None,
) -> ExplainContext:
    """The default offered set for one change: its own before side, its own after side.

    The versions come from the `Delta`, not the `Change` — a change carries a single
    `ProvisionRef`, pointing at whichever version still contains it (the new one, except for
    deletions), so the pair has to be passed in.

    The trees and the cap are optional because the prompt does not read the coordinate-support
    sets: a context built without them prompts identically, carries
    `coordinates_checked=False`, and the gate then counts nothing rather than counting every
    mention as unsupported. A caller gating an explanation passes all three.

    Raises `ValueError` for a change with no text on either side. That is a caller error *at
    this entry point* — you asked for a context for something that cannot have one. It is not
    how a batch meets the case: `contexts_for_delta` answers `None` for those changes and
    `explain_delta` records `NOTHING_TO_EXPLAIN` against them, because they are routine output
    and a routine outcome may not raise.
    """
    offered = tuple(OfferedCitation.for_ref(ref) for ref in _refs(change, from_version, to_version))
    if not offered:
        raise ValueError(
            f"{change.location.canonical} carries no text on either side; there is nothing to "
            f"explain and nothing it could cite. Use `explainable()` to filter, or "
            f"`contexts_for_delta()`, which answers None for these."
        )
    localised, shown, checked = _support(change, before_tree, after_tree, text_char_cap)
    return ExplainContext(
        offered=offered,
        surrounding_heading=surrounding_heading or change.heading,
        surrounding_text=surrounding_text,
        localised=localised,
        shown=shown,
        coordinates_checked=checked,
    )


def contexts_for_delta(
    delta: Delta,
    *,
    before_tree: ProvisionTree | None = None,
    after_tree: ProvisionTree | None = None,
    text_char_cap: int | None = None,
) -> tuple[ExplainContext | None, ...]:
    """One slot per change, in the delta's order — the default `explain_delta` input.

    `None` marks a change with nothing to explain. The slot is kept rather than dropped so the
    result of a run stays positionally aligned with the delta it came from, and so a caller
    building its own contexts has to decide what to do about these rather than discover them.

    The trees and the cap fill the coordinate-support sets (`_support`); the offered keys are
    a pure function of the delta with or without them, which is what lets the gate build its
    contexts with the trees while the explain stage builds the same offered sets without.
    """
    return tuple(
        build_context(
            change,
            from_version=delta.from_version,
            to_version=delta.to_version,
            before_tree=before_tree,
            after_tree=after_tree,
            text_char_cap=text_char_cap,
        )
        if explainable(change)
        else None
        for change in delta.changes
    )
