"""Pinning the documents the corpus is scored from, and recording what each case actually read.

Split from `build.py` at the seam between *choosing* transitions and *committing* the bytes they
are computed from. Two jobs live here:

- `fixture_pins` turns a selected corpus into the pin list `eu/fetch_fixtures.py` fetches, and
  decides on the way which amending acts can supply the third signal. Deciding that costs one
  fetch of each candidate, which is why it belongs to the generator and not to the runner: the
  runner never fetches anything.
- `RecordingCache` and `case_inputs` pin each case's inputs *by observing the case being
  computed*, so what the corpus claims to have been measured on is what was actually served.

The size cap is the only editorial judgement in the eval layer and it is mechanical: an amending
act whose own Formex would weigh more than `MAX_INSTRUCTION_BYTES` in the repository loses its
case the third signal, and the case records the reason. The CLP Regulation's 3.3 MB is why.
"""

from __future__ import annotations

import io
import zipfile

from emendrix.eu.cache import CachedResponse, ManifestEntry, ResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.fetch_fixtures import ORIGINAL, Pin
from emendrix.eu.identifiers import Celex
from emendrix.eu.packages import FormexPackage
from emendrix.eu.trims import trim_formex_zip
from emendrix.eval_.build import MAX_INSTRUCTION_BYTES
from emendrix.eval_.corpus import CaseInput, CorpusCase, EvalCorpus
from emendrix.eval_.runner import version_id

__all__ = ["RecordingCache", "case_inputs", "committed_size", "fixture_pins"]


def committed_size(package: FormexPackage) -> int:
    """How many bytes this package would weigh in the repo, after `eu/trims.py` has trimmed it."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for member in package.xml_members:
            archive.writestr(member.name, member.data)
    return len(trim_formex_zip(buffer.getvalue()))


def _instruction_fits(client: CellarClient, celex: str) -> bool:
    """Whether an amending act's own Formex is small enough to commit (see the cap above)."""
    try:
        parsed = Celex.parse(celex)
    except ValueError:
        return False
    fetched = client.fetch_formex(parsed, parsed.version)
    if not isinstance(fetched, FormexPackage):
        return False
    return committed_size(fetched) <= MAX_INSTRUCTION_BYTES


def fixture_pins(corpus: EvalCorpus, client: CellarClient) -> tuple[EvalCorpus, tuple[Pin, ...]]:
    """The documents the corpus needs, and the corpus with its third-signal decisions recorded.

    Deciding the third signal costs one fetch of each candidate amending act — which is why this
    lives here, in the generator, and not in the runner: the runner never fetches anything.
    """
    pins: dict[tuple[str, str], Pin] = {}

    def keep(pin: Pin) -> None:
        """One pin per document, keyed exactly as `merge_pins` keys it — first reason wins."""
        pins.setdefault((pin.celex, pin.version or ""), pin)

    for act in corpus.acts:
        keep(Pin(celex=act.celex, reason=f"eval corpus: {act.celex} notices"))
    decided: list[CorpusCase] = []
    for case in corpus.cases:
        for version in (case.from_version, case.to_version):
            keep(
                Pin(
                    celex=case.act,
                    version=ORIGINAL if version == case.act else version,
                    reason=f"eval corpus: {case.id}",
                )
            )
        source = case.instruction_source
        if source is not None and not _instruction_fits(client, source):
            decided.append(
                case.model_copy(
                    update={
                        "instruction_source": None,
                        "instruction_note": (
                            f"{source}: its own Formex exceeds the "
                            f"{MAX_INSTRUCTION_BYTES // 1024} KiB fixture cap"
                        ),
                    }
                )
            )
            continue
        if source is not None:
            keep(
                Pin(
                    celex=source,
                    version=ORIGINAL,
                    reason=f"eval corpus: instruction signal for {case.id}",
                )
            )
        decided.append(case)
    return corpus.model_copy(update={"cases": tuple(decided)}), tuple(
        sorted(pins.values(), key=lambda pin: (pin.celex, pin.version or ""))
    )


# --------------------------------------------------------------------------- digests


class RecordingCache:
    """A read-only cache that remembers what it served, so a case's inputs can be pinned.

    Wraps the fixture cache the run reads from and adds nothing to it — `offline` stays true, so
    there is still no code path from a miss to a socket.
    """

    def __init__(self, inner: ResponseCache) -> None:
        self.inner = inner
        self.served: list[ManifestEntry] = []

    @property
    def offline(self) -> bool:
        return self.inner.offline

    def get(self, key: str) -> CachedResponse | None:
        found = self.inner.get(key)
        if found is not None:
            self.served.append(found.entry)
        return found

    def store(self, response: CachedResponse) -> None:
        self.inner.store(response)

    def take(self, role: str) -> tuple[CaseInput, ...]:
        """The documents served since the last `take`, as pinned inputs under one role.

        A notice names its own role — the tree notice is routing, the branch notice is the
        reference label set — so only the texts take the role the caller was asking for.
        """
        taken = [entry for entry in self.served if entry.status_code == 200]
        self.served.clear()
        return tuple(
            CaseInput(
                role=_role_of(entry, role), url=entry.url, sha256=entry.sha256, size=entry.size
            )
            for entry in taken
        )


def _role_of(entry: ManifestEntry, given: str) -> str:
    accept = entry.accept or ""
    if "notice=tree" in accept:
        return "routing"
    if "notice=branch" in accept:
        return "metadata"
    return given


def case_inputs(
    client: CellarClient, cache: RecordingCache, case: CorpusCase
) -> tuple[CaseInput, ...]:
    """Pin one case's inputs by fetching exactly what scoring it fetches, and recording it.

    A fresh client per case, so each case pins its own routing notice rather than inheriting the
    one an earlier case of the same act happened to warm.
    """
    celex = Celex.parse(case.act)
    cache.take("discarded")
    collected: list[CaseInput] = []
    for role, version in (("from", case.from_version), ("to", case.to_version)):
        client.fetch_formex(celex, version_id(case, version))
        collected.extend(cache.take(role))
    client.branch_notice(celex)
    collected.extend(cache.take("metadata"))
    if case.instruction_source is not None:
        amender = Celex.parse(case.instruction_source)
        client.fetch_formex(amender, amender.version)
        collected.extend(cache.take("instructions"))
    return _dedupe(tuple(collected))


def _dedupe(inputs: tuple[CaseInput, ...]) -> tuple[CaseInput, ...]:
    """One entry per (role, url), in a fixed order — the same run must pin the same list."""
    seen: dict[tuple[str, str], CaseInput] = {}
    for item in inputs:
        seen.setdefault((item.role, item.url), item)
    return tuple(sorted(seen.values(), key=lambda item: (item.role, item.url)))
