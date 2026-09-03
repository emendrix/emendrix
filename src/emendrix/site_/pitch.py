"""The sentences that say what emendrix is and what it covers, for the pages that print them.

They live in a module of their own because two pages print each of them, and a product
description written twice is a product description that drifts: the methodology page and the
about page lead with `PITCH`, and the acts index and the about page both state `SCOPE`. Neither
claims anything measured: the figures are the methodology page's, and these are the sentences a
reader meets before any of them.
"""

from __future__ import annotations

from typing import Final

__all__ = ["PITCH", "SCOPE", "scope_holds"]

PITCH: Final = (
    "Your regulatory dependencies, with a changelog. emendrix watches EU legislation, computes "
    "provision-level diffs when it is amended, and explains what changed in plain English where "
    "every sentence cites a provision you can click."
)

SCOPE: Final = (
    "Every act here is watched in its English text. Directives are not on the watchlist: they "
    "take effect through each Member State's own transposing law, and a change to one has a "
    "second dimension this pipeline has no model for. A consolidated version with no English "
    "text is recorded as such and never translated."
)
"""What the roster covers, printed only while the roster's own kinds say it is true.

Its second sentence is a claim about one deployment's watchlist, so both pages that print it
render it from `SiteInputs.kinds` and drop it the day a Directive is watched. That is why it is
a constant with a condition rather than a paragraph of standing copy: a site whose product is
the precision of its own claims may not carry a sentence about itself that nothing re-checks.
"""

_TRANSPOSED: Final = "Directive"
"""The kind whose absence `SCOPE` claims. It is matched by the word the composition root names
that kind with, a label like every other on this site, which is what makes the claim checkable
at all rather than a sentence nobody could falsify."""


def scope_holds(kinds: tuple[tuple[str, int], ...]) -> bool:
    """Whether `SCOPE` is true of this roster: one was declared, and it names no Directive.

    An empty roster is not a roster that excludes Directives, it is a build with no watchlist,
    where the acts shown are whatever the changelog repository happens to hold. Saying what is
    watched needs something to have said what is watched.
    """
    return bool(kinds) and all(name != _TRANSPOSED for name, _ in kinds)
