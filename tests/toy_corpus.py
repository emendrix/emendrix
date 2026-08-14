"""`ToyCorpusAdapter`, the second implementor of the seam.

A flat's house rules, in two versions, held entirely in memory. It is deliberately alien:
no law, no legal identifiers, no network, no files, versions called `v1`/`v2`, citations
pointing at `example.invalid`. Its whole job is to keep `CorpusAdapter` honest, because an
abstraction validated against one implementation is not an abstraction.

It also exercises the awkward parts on purpose: a location code outside the vocabulary
(`SLOT`), verbatim text with irregular whitespace, an act version that is not there yet
(`ConsolidationPending`), and a language nobody published (`EnglishUnavailable`).

Not a fixture of anything real. Nothing in here is legal content.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import (
    ActId,
    AmendingActDoc,
    ChangeType,
    Citation,
    ConsolidationPending,
    EnglishUnavailable,
    ProvisionLocation,
    ProvisionNode,
    ProvisionRef,
    ProvisionText,
    ProvisionTree,
    QuotedProvision,
    Unavailable,
    VersionDescriptor,
    VersionId,
    normalize_for_comparison,
)

HOUSE_RULES = ActId(corpus="toy", key="house-rules", display_name="House Rules of Flat 3B")
AMENDMENT = ActId(corpus="toy", key="house-rules-amendment-1", display_name="Rule change, June")

V1 = VersionId("v1")
V2 = VersionId("v2")
V3_PENDING = VersionId("v3")
"""Agreed at the June meeting, not yet written up: the toy's `ConsolidationPending` case."""

LANGUAGE = "ENG"

_QUIET_HOURS_V1 = "Quiet hours run from 22:00 until 07:00 on\n   every day of the week."
_QUIET_HOURS_V2 = _QUIET_HOURS_V1
_BINS_V1 = "The bins go out on Tuesday evening."
_BINS_V2 = "The bins go out on Tuesday evening,  and the recycling on the first Tuesday."
_GUESTS_V1 = "Guests staying more than three nights are announced in the group chat."
_PARCELS_V2 = "Parcels left in the hallway are moved to the shelf by whoever finds them."
_ROTA_V1 = "Kitchen: Ada.   Bathroom: Bo.   Hallway: Cy."
_ROTA_V2 = "Kitchen: Bo.   Bathroom: Cy.   Hallway: Ada."
_SLOT_V1 = "Saturday morning."
_SLOT_V2 = "Sunday morning."


def _node(
    location: str, text: str, heading: str, children: tuple[ProvisionNode, ...] = ()
) -> ProvisionNode:
    return ProvisionNode.from_plain_text(location, text, heading=heading, children=children)


def _tree(version: VersionId, roots: tuple[ProvisionNode, ...]) -> ProvisionTree:
    return ProvisionTree(act=HOUSE_RULES, version=version, language=LANGUAGE, roots=roots)


def _rota(text: str, slot_text: str) -> ProvisionNode:
    # `SLOT` is not in `LocationCode`: the toy corpus proves the UNKNOWN escape hatch
    # survives a full round trip through the seam.
    return _node(
        "AN I",
        text,
        "Cleaning rota",
        children=(_node("AN I SLOT 2", slot_text, "Deep clean"),),
    )


_V1_TREE = _tree(
    V1,
    (
        _node("AR 1", _QUIET_HOURS_V1, "Quiet hours"),
        _node("AR 2", _BINS_V1, "Bins"),
        _node("AR 3", _GUESTS_V1, "Guests"),
        _rota(_ROTA_V1, _SLOT_V1),
    ),
)

_V2_TREE = _tree(
    V2,
    (
        _node("AR 1", _QUIET_HOURS_V2, "Quiet hours"),
        _node("AR 2", _BINS_V2, "Bins"),
        _node("AR 4", _PARCELS_V2, "Parcels"),
        _rota(_ROTA_V2, _SLOT_V2),
    ),
)

_AMENDMENT_TREE = ProvisionTree(
    act=AMENDMENT,
    version=V1,
    language=LANGUAGE,
    roots=(
        ProvisionNode.from_plain_text(
            "AR 1",
            "Rule 2 is replaced by the following, Rule 3 is deleted and a rule on parcels "
            "is inserted.",
            heading="Changes agreed",
        ),
    ),
)


def _quoted(location: str | None, text: str, change_type: ChangeType) -> QuotedProvision:
    return QuotedProvision(
        location=None if location is None else ProvisionLocation.parse(location),
        stated_change_type=change_type,
        text=ProvisionText(text),
        comparison_text=normalize_for_comparison(text),
    )


class ToyCorpusAdapter:
    """An in-memory corpus that satisfies `CorpusAdapter` and knows nothing about law."""

    def __init__(self, *, observed_on: date, language: str = LANGUAGE) -> None:
        # The observation date is passed in, never read from a clock: the core rule.
        self.observed_on = observed_on
        self.language = language

    def discover_versions(self, act: ActId) -> list[VersionDescriptor]:
        self._require_known(act)
        if act == AMENDMENT:
            return [VersionDescriptor(act=act, version=V1, languages=(LANGUAGE,))]
        return [
            VersionDescriptor(
                act=act, version=V1, version_date=date(2026, 1, 15), languages=(LANGUAGE,)
            ),
            VersionDescriptor(
                act=act, version=V2, version_date=date(2026, 6, 1), languages=(LANGUAGE,)
            ),
            VersionDescriptor(
                act=act, version=V3_PENDING, version_date=date(2026, 9, 1), languages=()
            ),
        ]

    def fetch_version(self, act: ActId, version: VersionId) -> ProvisionTree | Unavailable:
        self._require_known(act)
        if self.language != LANGUAGE:
            return EnglishUnavailable(
                act=act,
                version=version,
                requested_language=self.language,
                available_languages=(LANGUAGE,),
                observed_on=self.observed_on,
                detail="the flat only writes its rules in English",
            )
        if version == V3_PENDING:
            return ConsolidationPending(
                act=act,
                in_force=date(2026, 9, 1),
                observed_on=self.observed_on,
                detail="agreed at the June meeting, not yet written up",
            )
        trees = {V1: _V1_TREE, V2: _V2_TREE}
        if version not in trees:
            raise ValueError(f"unknown toy version: {version!r}")
        return trees[version]

    def parse_amending_act(self, act: ActId) -> AmendingActDoc | Unavailable:
        if act != AMENDMENT:
            raise ValueError(f"not a toy amending act: {act}")
        return AmendingActDoc(
            act=AMENDMENT,
            tree=_AMENDMENT_TREE,
            amends=(HOUSE_RULES,),
            quoted=(
                _quoted("AR 2", _BINS_V2, ChangeType.MODIFIED),
                _quoted("AR 3", _GUESTS_V1, ChangeType.DELETED),
                # The prose omits the identifier of what it inserts, exactly as amending
                # documents in the real corpus do.
                _quoted(None, _PARCELS_V2, ChangeType.INSERTED),
            ),
        )

    def render_citation(self, ref: ProvisionRef) -> Citation:
        anchor = ref.location.canonical.lower().replace(" ", "-")
        return Citation(
            ref=ref,
            url=f"https://example.invalid/{ref.act.key}/{ref.version}#{anchor}",
            label=f"{ref.location.human}, {ref.version}",
        )

    @staticmethod
    def _require_known(act: ActId) -> None:
        if act not in (HOUSE_RULES, AMENDMENT):
            raise ValueError(f"unknown toy act: {act}")
