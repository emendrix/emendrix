"""What the output repository already holds, which is the only resume record that cannot be lost.

The ledger next door answers "what has this installation attempted, and what did it cost?". This
module answers "what does the product already contain?", and the two have different lifetimes.
The ledger is a file in a working directory; the changelog repository is the artifact the whole
loop exists to produce and is mounted, kept and backed up as such. A container that starts with
an empty filesystem has no ledger and every transition looks new, so a backfill that trusted the
ledger alone would re-run, and re-pay for, work that is already committed.

So the question is asked of the repository first, and the answer is a file existing at a path that
is a pure function of the act and the version the transition produced (`output/json_out.py`
spells the layout out once). No state, no cursor, nothing to corrupt: kill a backfill, delete
everything it wrote outside the changelog repository, start it again, and it skips what it
finished.

The ledger still earns its place: it is where a *failure* and its retry count live, and where a
transition that legitimately produced nothing to diff is remembered, neither of which leaves a
file behind. The two are consulted together and neither is derived from the other.
"""

from __future__ import annotations

from collections.abc import Iterable

from emendrix.backfill.plan import TransitionPlan
from emendrix.output import OutputRepo

__all__ = ["emitted_keys"]


def emitted_keys(repository: OutputRepo | None, plans: Iterable[TransitionPlan]) -> frozenset[str]:
    """The keys of the planned transitions this repository already carries an entry for.

    An unconfigured repository (there is none in a dry run that was never given one) answers
    with the empty set rather than with a claim about what has been done.

    "Carries an entry" means a *finished* one. An entry written while the provider was
    refusing calls is not work this run need not do again, so `holds_finished` reads it rather
    than only looking for it, which is what lets a run interrupted by an exhausted credit
    balance complete itself the next time it is started.
    """
    if repository is None:
        return frozenset()
    return frozenset(
        transition.key
        for plan in plans
        for transition in plan.transitions
        if repository.holds_finished(transition.act, transition.to_version)
    )
