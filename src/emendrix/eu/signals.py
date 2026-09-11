"""The EU adapter's two second opinions for one version pair, in corroboration's own shape.

`corroborate()` wants a metadata signal and an instruction signal; the loop (`graph/`) has an
act and two version identifiers. This module is the translation, and it composes what the
fetch layer, the parser and the metadata reader already provide. It is not part of
`CorpusAdapter` and must not become part of it (`core/adapter.py`): a corpus that
publishes no modification metadata has no `SignalSource`, and two `UNAVAILABLE` signals are
silence, not dissent.

Five decisions, all forced by what the corpus actually does (verified 2026-08-06 against the
pinned branch notices; `eu/modmeta.py` carries the evidence):

1. **The window is `(date(A), date(B)]`, not "the amending act".** A version pair can fold in
   several amending acts, and one amending act's changes can be dated separately. When A is
   the act as published in the OJ there is no lower bound, because everything up to B
   belongs to the pair.
2. **A version with no date in the tree notice yields no metadata signal.** Guessing a window
   would quietly widen or narrow the reference set, and a silent reference set is worse than
   an absent one. A window the corpus annotated nowhere answers the same way and for the same
   reason: `metadata_signal` is where that is decided, and its docstring holds the evidence.
3. **The instruction parse is read only when the window names exactly one amending act.** It
   is a cross-check, not ground truth, and attributing two acts' instructions to one pair
   would measure nothing. Where it is skipped the report says how many acts the window folds
   in, so the reason is in the output rather than in this file.
4. **The window goes down to the instruction parse as well.** It already chose the document;
   it now also says which of that document's instructions this pair may claim, because an
   amending act's orders can be dated years apart and the act is read whole. A record dated
   nowhere is claimed as before.
5. **The amending act's own dates are read here and passed down as a value.** The act's text
   usually writes no date at all, and the day it took effect is published in its own tree
   notice (`eu/instructions/notice_dates.py`). That notice is a document about the amending
   act, never a modification annotation about the amended one: the metadata signal may say
   where the third signal looks and must never say what it finds there, and this does not
   change that. The parse fetches nothing itself, exactly as it reads no clock.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import ActId, Signal, SignalReport, VersionId
from emendrix.corroborate.sources import TransitionSignals
from emendrix.eu.cellar import ABSENT_STATUSES, CellarClient
from emendrix.eu.http import ACCEPT_TREE_NOTICE
from emendrix.eu.identifiers import Celex, ResourceRef, celex_of
from emendrix.eu.instructions import (
    ActDates,
    Window,
    instruction_signal,
    parse_act_dates,
    parse_instructions,
)
from emendrix.eu.modmeta import ModificationSet, parse_branch_modifications
from emendrix.eu.modmeta import metadata_signal as build_metadata_signal
from emendrix.eu.packages import FormexPackage

__all__ = ["EuSignalSource", "act_dates", "instruction_signal_for"]


def act_dates(client: CellarClient, celex: Celex) -> ActDates:
    """What one act's own CELLAR tree notice publishes about the act's dates.

    The composition root's second read of a document the adapter already fetches for its
    version inventory, so it answers off the same disk cache and costs no second request in
    practice. It carries that read's freshness policy for the same reason: a listing can grow at
    any time, and this one would otherwise stay frozen for an act the client has not refreshed.

    An act the corpus has no notice for is dated from its own text alone, and that is a
    coverage gap like any other. Every other status is the server refusing *us* and fails
    loudly, exactly as `CellarClient.branch_notice` does on the same endpoint: read as an
    absent notice it would suppress this act's dates for the life of the process on the
    strength of one 403, which is a claim about an act made out of a refusal.
    """
    response = client.http.get(
        ResourceRef(system="celex", identifier=celex.value),
        accept=ACCEPT_TREE_NOTICE,
        volatile=True,
    )
    if response.status_code in ABSENT_STATUSES:
        return ActDates()
    if not response.ok:
        raise LookupError(f"no tree notice for {celex}: HTTP {response.status_code}")
    return parse_act_dates(response.body)


def instruction_signal_for(
    client: CellarClient,
    celex: Celex,
    act: ActId,
    *,
    window: Window | None = None,
    dates: ActDates | None = None,
) -> SignalReport:
    """The third signal for one amended act, read out of one amending act's own package.

    The one place that turns an amending act's identifier into the instruction signal, so the
    loop and anything that recomputes the signal over an entry already written cannot disagree
    about what was parsed or about the note that says how much of it was read. A package with no
    readable text is an answer and is reported as one.

    `window` is the consolidation's `(after, until]`, a value from the composition root. A
    caller holding none claims the whole act under the unbounded window, and the note counts
    what that window excluded either way. `dates` is the amending act's own published dates,
    read here when a caller does not already hold them.
    """
    fetched = client.fetch_formex(celex, celex.version, allow_original_fallback=False)
    if not isinstance(fetched, FormexPackage):
        return SignalReport.unavailable(
            Signal.INSTRUCTION_PARSE, note=f"{celex} has no readable text: {fetched.state}"
        )
    published = act_dates(client, celex) if dates is None else dates
    parsed = parse_instructions(fetched, dates=published)
    return instruction_signal(
        parsed,
        act,
        window=window,
        note=f"{celex}, {parsed.coverage:.3f} of its instruction clauses read",
    )


class EuSignalSource:
    """Modification annotations and amending-act instructions, per transition, cached per act.

    Reads through the same `CellarClient` — and therefore the same disk cache or fixture set —
    as everything else in the adapter, so an offline run stays offline.
    """

    def __init__(self, client: CellarClient) -> None:
        self.client = client
        self._modifications: dict[str, ModificationSet] = {}
        self._dates: dict[str, dict[str, date | None]] = {}
        self._act_dates: dict[str, ActDates] = {}

    def signals_for(
        self, act: ActId, from_version: VersionId, to_version: VersionId
    ) -> TransitionSignals:
        """Both signals for one version pair, each with the note that explains its absence."""
        celex = celex_of(act)
        modifications = self._modification_set(celex)
        window = self._window(celex, from_version, to_version)
        if window is None:
            return TransitionSignals(
                metadata=SignalReport.unavailable(
                    Signal.CORPUS_METADATA,
                    note=f"the tree notice dates neither {from_version} nor {to_version}",
                ),
                instructions=SignalReport.unavailable(
                    Signal.INSTRUCTION_PARSE, note="no dated window to select an amending act"
                ),
            )
        start, end = window
        records = modifications.between(start, end)
        amending = tuple(dict.fromkeys(r.amending_celex for r in records if r.amending_celex))
        return TransitionSignals(
            metadata=build_metadata_signal(
                records,
                note=f"{len(records)} annotations in ({start or 'the act itself'}, {end}]",
            ),
            instructions=self._instructions(act, amending, window),
        )

    # ---------------------------------------------------------------- the pieces

    def _modification_set(self, celex: Celex) -> ModificationSet:
        found = self._modifications.get(celex.value)
        if found is None:
            found = parse_branch_modifications(self.client.branch_notice(celex))
            self._modifications[celex.value] = found
        return found

    def _version_dates(self, celex: Celex) -> dict[str, date | None]:
        found = self._dates.get(celex.value)
        if found is None:
            found = {str(item.version): item.version_date for item in self.client.versions(celex)}
            self._dates[celex.value] = found
        return found

    def _window(
        self, celex: Celex, from_version: VersionId, to_version: VersionId
    ) -> Window | None:
        """`(after, until]`, or `None` when the corpus does not date the pair.

        The lower bound is `None` when `from_version` is the act as published: everything
        annotated up to the later version belongs to the pair, and there is nothing before it.
        """
        dates = self._version_dates(celex)
        end = dates.get(str(to_version))
        if end is None:
            return None
        if str(from_version) == celex.value:
            return None, end
        start = dates.get(str(from_version))
        return None if start is None else (start, end)

    def _instructions(self, act: ActId, amending: tuple[str, ...], window: Window) -> SignalReport:
        """The third signal, when exactly one amending act is in the window and it has text.

        The window goes down with the act: it selects *which* document is read, and then which
        of that document's instructions this consolidation is entitled to claim.
        """
        if len(amending) != 1:
            return SignalReport.unavailable(
                Signal.INSTRUCTION_PARSE,
                note=(
                    "no amending act in this window"
                    if not amending
                    else f"the window folds in {len(amending)} amending acts: {', '.join(amending)}"
                ),
            )
        celex = Celex.parse(amending[0])
        return instruction_signal_for(
            self.client, celex, act, window=window, dates=self._published_dates(celex)
        )

    def _published_dates(self, celex: Celex) -> ActDates:
        """The amending act's own dates, parsed once per act for the life of the source."""
        found = self._act_dates.get(celex.value)
        if found is None:
            found = act_dates(self.client, celex)
            self._act_dates[celex.value] = found
        return found
