"""The EU adapter's two second opinions for one version pair, in corroboration's own shape.

`corroborate()` wants a metadata signal and an instruction signal; the loop (`graph/`) has an
act and two version identifiers. This module is the translation, and it composes what the
fetch layer, the parser and the metadata reader already provide. It is not part of
`CorpusAdapter` and must not become part of it (`core/adapter.py`): a corpus that
publishes no modification metadata has no `SignalSource`, and two `UNAVAILABLE` signals are
silence, not dissent.

Three decisions, all forced by what the corpus actually does (verified 2026-08-06 against the
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
   amending act's orders can be dated years apart and the act is read whole. Only the act's own
   text dates them (`eu/instructions/effect.py`), never an annotation: the metadata may say
   where the third signal looks and must never say what it finds there. A record the act dated
   nowhere is claimed as before.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import ActId, Signal, SignalReport, VersionId
from emendrix.corroborate.sources import TransitionSignals
from emendrix.eu.cellar import CellarClient
from emendrix.eu.identifiers import Celex, celex_of
from emendrix.eu.instructions import Window, instruction_signal, parse_instructions
from emendrix.eu.modmeta import ModificationSet, parse_branch_modifications
from emendrix.eu.modmeta import metadata_signal as build_metadata_signal
from emendrix.eu.packages import FormexPackage

__all__ = ["EuSignalSource", "instruction_signal_for"]


def instruction_signal_for(
    client: CellarClient, celex: Celex, act: ActId, *, window: Window | None = None
) -> SignalReport:
    """The third signal for one amended act, read out of one amending act's own package.

    The one place that turns an amending act's identifier into the instruction signal, so the
    loop and anything that recomputes the signal over an entry already written cannot disagree
    about what was parsed or about the note that says how much of it was read. A package with no
    readable text is an answer and is reported as one.

    `window` is the consolidation's `(after, until]`, a value from the composition root. A
    caller holding none claims the whole act under the unbounded window, and the note counts
    what that window excluded either way.
    """
    fetched = client.fetch_formex(celex, celex.version, allow_original_fallback=False)
    if not isinstance(fetched, FormexPackage):
        return SignalReport.unavailable(
            Signal.INSTRUCTION_PARSE, note=f"{celex} has no readable text: {fetched.state}"
        )
    parsed = parse_instructions(fetched)
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
        return instruction_signal_for(self.client, Celex.parse(amending[0]), act, window=window)
