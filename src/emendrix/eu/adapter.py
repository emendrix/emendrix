"""`EuCorpusAdapter` — the EU side of the seam, composed from the modules around it.

Four methods, the same four the toy corpus implements (`tests/toy_corpus.py`), and no fifth:
modification metadata and the notification feed are *capabilities* of this adapter, consumed
by eval and watch directly, and they never widen the Protocol.

The adapter itself holds no logic worth the name. It converts `ActId`/`VersionId` into EU
identifiers, asks `CellarClient`, and hands what comes back to a `FormexParser` — by default
the real one, `emendrix.eu.formex.Formex4Parser`. The parser stays a constructor seam so a
test can substitute a double without a network or a fixture, not because anything is missing.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from emendrix.core import (
    ActId,
    AmendingActDoc,
    Citation,
    ProvisionRef,
    ProvisionTree,
    StructuredTextUnavailable,
    Unavailable,
    VersionDescriptor,
    VersionId,
)
from emendrix.eu.cache import ResponseCache
from emendrix.eu.cellar import DEFAULT_LANGUAGE, CellarClient
from emendrix.eu.formex import Formex4Parser
from emendrix.eu.http import CellarHttp, polite_delay
from emendrix.eu.identifiers import celex_of
from emendrix.eu.links import render_citation
from emendrix.eu.packages import FormexPackage

__all__ = ["EuCorpusAdapter", "FormexParser"]


class FormexParser(Protocol):
    """Formex 4 bytes → core documents. Implemented by `emendrix.eu.formex.Formex4Parser`."""

    def parse_version(self, package: FormexPackage) -> ProvisionTree: ...

    def parse_amending(self, package: FormexPackage) -> AmendingActDoc: ...


class EuCorpusAdapter:
    """EU legislation, as the generic engine sees it: four methods and core types only."""

    def __init__(self, client: CellarClient, *, parser: FormexParser | None = None) -> None:
        self.client = client
        self.parser: FormexParser = parser if parser is not None else Formex4Parser()

    @classmethod
    def build(
        cls,
        *,
        observed_on: date,
        cache: ResponseCache | None = None,
        language: str = DEFAULT_LANGUAGE,
        parser: FormexParser | None = None,
        polite_delay_s: float | None = None,
    ) -> EuCorpusAdapter:
        """The ordinary construction: a cached HTTP client, an observation date, no clock read.

        `observed_on` is passed in from the CLI boundary and is what every first-class state
        this adapter returns is stamped with. `polite_delay_s` arrives the same way and falls
        back to the environment, so the workload that wants to fetch gently can say so.
        """
        http = CellarHttp(cache=cache, polite_delay_s=polite_delay(polite_delay_s))
        return cls(CellarClient(http, observed_on=observed_on, language=language), parser=parser)

    # ------------------------------------------------------------ the Protocol

    def discover_versions(self, act: ActId) -> list[VersionDescriptor]:
        """Every version of the act, oldest first — the OJ text first, then consolidations."""
        return self.client.versions(celex_of(act))

    def fetch_version(self, act: ActId, version: VersionId) -> ProvisionTree | Unavailable:
        """The provision tree of one version, or the state that says why there is none.

        Structured text can be unavailable two ways. The first is the corpus offering no Formex
        manifestation at all, which `fetch_formex` already names. The second is a package that
        arrives, parses without raising, and yields nothing: REACH's `02006R1907-20150513` and
        `02006R1907-20150601` do exactly that (verified 2026-08-11), because those archives
        carry member names that do not describe their contents and the act's own document lands
        on one named `.tif`, which the `.xml` filter in `FormexPackage.xml_members` drops before
        `act_documents` can select it by shape.

        Returning the empty tree would make that indistinguishable from a repeal: a diff across
        either version reports all 158 units of REACH deleted and then re-inserted, with a zero
        exit status and nothing marked. A version with no provisions cannot be compared against,
        so it is refused here and counted like any other coverage gap.
        """
        package = self.client.fetch_formex(celex_of(act), version)
        if not isinstance(package, FormexPackage):
            return package
        tree = self.parser.parse_version(package)
        if tree.roots:
            return tree
        return StructuredTextUnavailable(
            act=act,
            version=version,
            observed_on=self.client.observed_on,
            detail=(
                f"the {package.language} Formex package for {package.served_version} parsed to "
                f"no provisions; its {len(package.members)} members carry no act document this "
                f"parser could read"
            ),
        )

    def parse_amending_act(self, act: ActId) -> AmendingActDoc | Unavailable:
        """The amending act's own text — always the OJ publication, never a consolidation."""
        celex = celex_of(act)
        package = self.client.fetch_formex(celex, celex.version, allow_original_fallback=False)
        if not isinstance(package, FormexPackage):
            return package
        return self.parser.parse_amending(package)

    def render_citation(self, ref: ProvisionRef) -> Citation:
        """A EUR-Lex anchor URL and a precise human label (`eu/links.py`)."""
        return render_citation(ref)

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        """Release the connection pool. For the long-running callers: the watcher and the loop."""
        self.client.http.close()

    def __enter__(self) -> EuCorpusAdapter:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
