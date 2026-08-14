"""The changes the committed cassettes cover, built from the pinned fixtures, never by hand.

The replay test and the recorder must agree byte for byte on what was asked, or the cassette
keys diverge and every replay misses. So both import the cases from here, and here builds them
the only honest way: run the real parser over the committed fixture packages and pull the
changes the real diff produced. No hand-authored legal content reaches the model.

Four cases, chosen to exercise the four shapes the prompt has to handle, and pinned by
location so a change in the diff shows up as a failure here rather than as a silently
different prompt:

- AI Act `AR 4` (MODIFIED): the worked example, both texts present, `applies_from` unchanged.
- AI Act `AR 4a` (INSERTED): no BEFORE text at all, and `applies_from` unknown.
- AI Act `AR 113` (MODIFIED): the application article, carrying 2026-07-27, 2026-12-02,
  2027-12-02 and 2028-08-02 in `dates_added` (measured 2026-08-06). This is the
  applicability-note case: the AFTER text states when things apply, so the model may quote it
  and may not infer from it. Its `applies_from` stays *unknown* because the text changed
  beyond its dates, which is exactly the honest outcome the second clock predicts.
- MDR `AR 34` (DEFERRED): a real `applies_from` date on the change. The AI Act transition
  contains no `DEFERRED` unit at all (measured: 0 of 45), so the type is exercised on the
  MDR postponement, where six units actually carry it.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict

from emendrix.core import Change, ChangeType, Delta, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from emendrix.explain import ExplainContext, build_context
from eu_pins import AI_ACT, AI_ACT_V2, MDR, MDR_V1, MDR_V2, package

AI_ACT_OJ: Final = AI_ACT
"""The act as published in the Official Journal is its own version tag."""

PINNED: Final[tuple[tuple[str, str, str, str, ChangeType], ...]] = (
    (AI_ACT, AI_ACT_OJ, AI_ACT_V2, "AR 4", ChangeType.MODIFIED),
    (AI_ACT, AI_ACT_OJ, AI_ACT_V2, "AR 4a", ChangeType.INSERTED),
    (AI_ACT, AI_ACT_OJ, AI_ACT_V2, "AR 113", ChangeType.MODIFIED),
    (MDR, MDR_V1, MDR_V2, "AR 34", ChangeType.DEFERRED),
)
"""`(celex, before, after, location, expected type)`. The expected type is asserted, not assumed."""


class PinnedCase(BaseModel):
    """One change and its offered citations: everything an explain call needs."""

    model_config = ConfigDict(frozen=True)

    celex: str
    change: Change
    context: ExplainContext

    @property
    def location(self) -> str:
        return self.change.location.canonical


def _tree(client: CellarClient, celex: str, version: str) -> ProvisionTree:
    return parse_act(package(client, celex, version)).tree


def _delta(client: CellarClient, celex: str, before: str, after: str) -> Delta:
    return compute_delta(_tree(client, celex, before), _tree(client, celex, after))


def pinned_cases(client: CellarClient) -> tuple[PinnedCase, ...]:
    """The pinned subset, parsed fresh from the fixtures. Deterministic and offline."""
    cases: list[PinnedCase] = []
    for celex, before, after, location, expected in PINNED:
        delta = _delta(client, celex, before, after)
        change = next(c for c in delta.changes if c.location.canonical == location)
        assert change.change_type is expected, (
            f"{celex} {location} is {change.change_type}, not {expected}: the diff moved, "
            f"which is a finding to explain rather than a pin to update"
        )
        cases.append(
            PinnedCase(
                celex=celex,
                change=change,
                context=build_context(
                    change, from_version=delta.from_version, to_version=delta.to_version
                ),
            )
        )
    return tuple(cases)
