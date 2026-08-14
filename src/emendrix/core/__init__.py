"""`emendrix.core`: the typed vocabulary of the whole system.

Locations, provision trees, versions, changes, citations, the two clocks, the first-class
states, and the `CorpusAdapter` Protocol that is the entire seam to any specific corpus.

Pure Python and pydantic: no I/O, no network, no clock, no model, and no knowledge of any
particular body of law. Everything else in the project imports this; this imports nothing
of the project back. If a corpus-specific name ever appears in here, the seam is broken.
"""

from emendrix.core.adapter import AmendingActDoc, CorpusAdapter, QuotedProvision
from emendrix.core.changes import (
    Applicability,
    ApplicabilityUnchanged,
    ApplicabilityUnknown,
    ChangeType,
    Signal,
    SignalObservation,
    SignalSet,
    SignalStatus,
)
from emendrix.core.citations import Citation
from emendrix.core.claims import (
    COMPARABLE_KIND,
    SignalClaim,
    SignalReport,
    comparable_kind,
)
from emendrix.core.delta import Change, Delta, DeltaSummary, sort_changes
from emendrix.core.identifiers import ActId, ProvisionRef, VersionDescriptor, VersionId
from emendrix.core.location import ProvisionLocation, normalize_location
from emendrix.core.location_codes import (
    LocationCode,
    LocationSegment,
    SegmentCode,
    UnknownCode,
)
from emendrix.core.ordering import natural_key, roman_value
from emendrix.core.provisions import (
    ComparisonText,
    DateMention,
    ProvisionNode,
    ProvisionText,
    ProvisionTree,
    normalize_for_comparison,
)
from emendrix.core.states import (
    ConsolidationPending,
    EnglishUnavailable,
    StructuredTextUnavailable,
    Unavailable,
)

__all__ = [
    "COMPARABLE_KIND",
    "ActId",
    "AmendingActDoc",
    "Applicability",
    "ApplicabilityUnchanged",
    "ApplicabilityUnknown",
    "Change",
    "ChangeType",
    "Citation",
    "ComparisonText",
    "ConsolidationPending",
    "CorpusAdapter",
    "DateMention",
    "Delta",
    "DeltaSummary",
    "EnglishUnavailable",
    "LocationCode",
    "LocationSegment",
    "ProvisionLocation",
    "ProvisionNode",
    "ProvisionRef",
    "ProvisionText",
    "ProvisionTree",
    "QuotedProvision",
    "SegmentCode",
    "Signal",
    "SignalClaim",
    "SignalObservation",
    "SignalReport",
    "SignalSet",
    "SignalStatus",
    "StructuredTextUnavailable",
    "Unavailable",
    "UnknownCode",
    "VersionDescriptor",
    "VersionId",
    "comparable_kind",
    "natural_key",
    "normalize_for_comparison",
    "normalize_location",
    "roman_value",
    "sort_changes",
]
