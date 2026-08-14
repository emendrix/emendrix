"""The public CELLAR surface: resolve an act, list its versions, fetch its structured text.

Everything here goes through `eu.http` and therefore through the disk cache; nothing here
raises where the corpus gave an answer.

## The fallback chain, and why it returns values

A consolidated version can exist and have no English text: `02024R1689-20240712` is published
in eleven languages, English not among them (verified 2026-08-05, still true 2026-08-06). A
version can also exist in English with no *structured* text at all: 5 of REACH's 68
consolidated versions offer only PDF and XHTML (both numbers asserted by
`tests/eu/test_cellar.py`). And a version can simply not exist yet, because consolidation lags
publication by ten days to three weeks.

So `fetch_formex` answers with one of four things, and three of them are states:

```
consolidated <lang> fmx4        →  FormexPackage
   ↓ no such manifestation, and this is the act's first consolidation
the act as published in the OJ  →  FormexPackage, marked `fell_back`
   ↓ not available either, or the fallback does not apply
no text in that language        →  EnglishUnavailable
no structured text at all       →  StructuredTextUnavailable
version not consolidated yet    →  ConsolidationPending
```

The fallback is deliberately narrow: it applies only when the requested version is the act's
**earliest** consolidation, where "the previous text" genuinely is the original act. Falling
back from a 2022 consolidation of REACH to the 2006 original would answer a different
question than the one asked, silently. When it does apply, the package records it
(`FormexPackage.fell_back`, `served_version`) so no caller can mistake one for the other.

Every state carries `observed_on`, passed in at construction from the CLI boundary — this
module never reads a clock for anything but fetch provenance.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import (
    ActId,
    ConsolidationPending,
    EnglishUnavailable,
    StructuredTextUnavailable,
    Unavailable,
    VersionDescriptor,
    VersionId,
)
from emendrix.eu.http import ACCEPT_BRANCH_NOTICE, ACCEPT_TREE_NOTICE, ACCEPT_ZIP, CellarHttp
from emendrix.eu.identifiers import Celex, ResourceRef, VersionKey, parse_version_id
from emendrix.eu.notices import (
    FORMEX_FORMAT,
    TreeNotice,
    VersionRecord,
    WorkMetadata,
    parse_tree_notice,
)
from emendrix.eu.packages import FormexPackage

__all__ = ["ABSENT_STATUSES", "DEFAULT_LANGUAGE", "CellarClient"]

DEFAULT_LANGUAGE = "ENG"
"""v0.1 ships English only, by scope cap."""

ABSENT_STATUSES = frozenset({404, 406})
"""The two refusals that mean *the document is not there*, and no others.

`404` for a manifestation that does not exist in that language or format, `406` for a work
with no expression in the requested language — both verified 2026-08-06 (`eu/http.py`). Every
other non-200 is the server refusing *us*, and must never be read as a fact about the corpus.
"""


class CellarClient:
    """Content-negotiated retrieval from the Publications Office, by identifier.

    Holds the parsed tree notices it has seen for the life of the process; the bytes behind
    them live in the disk cache, so a second process pays no network either.
    """

    def __init__(
        self,
        http: CellarHttp,
        *,
        observed_on: date,
        language: str = DEFAULT_LANGUAGE,
    ) -> None:
        self.http = http
        self.observed_on = observed_on
        self.language = language.upper()
        self._notices: dict[str, TreeNotice] = {}

    # ------------------------------------------------------------------ notices

    def tree_notice(self, celex: Celex) -> TreeNotice:
        """The act's version inventory (`notice=tree`), parsed."""
        cached = self._notices.get(celex.value)
        if cached is not None:
            return cached
        response = self.http.get(
            ResourceRef(system="celex", identifier=celex.value), accept=ACCEPT_TREE_NOTICE
        )
        if not response.ok:
            raise LookupError(f"no tree notice for {celex}: HTTP {response.status_code}")
        notice = parse_tree_notice(response.body, celex)
        self._notices[celex.value] = notice
        return notice

    def branch_notice(self, celex: Celex) -> bytes:
        """The act's metadata and amendment graph (`notice=branch`), as bytes.

        Interpreted by `modmeta.py`: the modification annotations that are the reference label set
        live in here (`RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL/ANNOTATION`). This step's job
        is to have the bytes, cached, so that step never touches the network.
        """
        response = self.http.get(
            ResourceRef(system="celex", identifier=celex.value), accept=ACCEPT_BRANCH_NOTICE
        )
        if not response.ok:
            raise LookupError(f"no branch notice for {celex}: HTTP {response.status_code}")
        return response.body

    def resolve(self, celex: Celex) -> WorkMetadata:
        """The act itself: title, document date, entry-into-force dates, identifiers."""
        return self.tree_notice(celex).work

    def versions(self, celex: Celex) -> list[VersionDescriptor]:
        """Every version of the act, oldest first, the OJ text included."""
        notice = self.tree_notice(celex)
        act = notice.work.act
        return [record.to_descriptor(act) for record in notice.versions]

    # -------------------------------------------------------------------- text

    def fetch_formex(
        self,
        celex: Celex,
        version: VersionId,
        *,
        language: str | None = None,
        allow_original_fallback: bool = True,
    ) -> FormexPackage | Unavailable:
        """The Formex 4 package of one version — or the state that says why there is none."""
        wanted = (language or self.language).upper()
        notice = self.tree_notice(celex)
        act = notice.work.act
        key = parse_version_id(version)
        record = notice.version(version)

        if record is None:
            return ConsolidationPending(
                act=act,
                observed_on=self.observed_on,
                detail=(
                    f"{version} is not among the {len(notice.versions)} versions the tree "
                    f"notice lists for {celex}"
                ),
            )

        package = self._fetch_manifestation(notice, record, key, version, wanted)
        if package is not None:
            return package

        original = notice.version(celex.version)
        if (
            original is not None
            and allow_original_fallback
            and self._fallback_applies(notice, record)
        ):
            fallback = self._fetch_manifestation(
                notice, original, parse_version_id(original.version), version, wanted
            )
            if fallback is not None:
                return fallback

        return self._unavailable(act, record, version, wanted)

    # ---------------------------------------------------------------- internals

    def _fetch_manifestation(
        self,
        notice: TreeNotice,
        record: VersionRecord,
        key: VersionKey,
        requested: VersionId,
        language: str,
    ) -> FormexPackage | None:
        """Try every address this version's Formex might answer on, best first."""
        for ref in _candidates(record, key, language):
            response = self.http.get(ref, accept=ACCEPT_ZIP)
            if response.status_code in ABSENT_STATUSES:
                continue
            if not response.ok:
                # Anything else — a 403, a 429, a challenge page — is the *server* refusing
                # us, not the corpus saying the text does not exist. Turning it into
                # `EnglishUnavailable` would persist a false claim about an act, so it fails
                # loudly instead, exactly as a bad notice response does above.
                raise LookupError(
                    f"unexpected HTTP {response.status_code} from {response.url}: "
                    f"{response.text(200)!r}"
                )
            return FormexPackage.from_zip(
                response.body,
                act=notice.work.act,
                requested_version=requested,
                served_version=record.version,
                language=language,
                source_url=response.url,
                fetched_at=response.fetched_at,
            )
        return None

    @staticmethod
    def _fallback_applies(notice: TreeNotice, record: VersionRecord) -> bool:
        """Only the act's earliest consolidation falls back to the act as published."""
        consolidated = notice.consolidated
        return bool(consolidated) and record.version == consolidated[0].version

    def _unavailable(
        self, act: ActId, record: VersionRecord, version: VersionId, language: str
    ) -> Unavailable:
        """Name the state the corpus's refusals add up to, from what the notice offered."""
        languages = record.languages
        if language not in languages:
            return EnglishUnavailable(
                act=act,
                version=version,
                requested_language=language,
                available_languages=languages,
                observed_on=self.observed_on,
                detail=f"the tree notice offers {', '.join(languages) or 'no language'}",
            )
        formats = record.formats(language)
        return StructuredTextUnavailable(
            act=act,
            version=version,
            formats_offered=formats,
            observed_on=self.observed_on,
            detail=(
                f"no {FORMEX_FORMAT} manifestation retrievable in {language}; "
                f"the tree notice offers {', '.join(formats) or 'no format'}"
            ),
        )


def _candidates(record: VersionRecord, key: VersionKey, language: str) -> tuple[ResourceRef, ...]:
    """Addresses to try for one version's Formex: the notice's own first, then constructed.

    The notice publishes the identifier that actually resolves, which is the only reliable
    way to know whether a consolidation answers on `consolidation/` or on `celex/`: pre-2018
    consolidations answer only on `celex/`, measured against live CELLAR on 2026-08-05.
    The constructed candidates cover the case where the notice lists no manifestation at all
    — the request then costs one 404, which is cached like any other answer.
    """
    ordered: list[ResourceRef] = []
    announced = record.manifestation(language, FORMEX_FORMAT)
    if announced is not None:
        ordered.append(announced.ref)
    ordered.extend(key.resource_refs(f".{language}.{FORMEX_FORMAT}"))
    seen: set[tuple[str, str]] = set()
    unique: list[ResourceRef] = []
    for ref in ordered:
        identity = (ref.system, ref.identifier)
        if identity not in seen:
            seen.add(identity)
            unique.append(ref)
    return tuple(unique)
