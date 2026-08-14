"""`emendrix.eu` — the EU adapter: everything that knows what CELEX and Formex are.

The core knows none of it. This package implements `CorpusAdapter` for EU legislation and
owns the only network access in the system:

```
identifiers  CELEX / consolidated-CELEX grammar, and the resource paths each answers on
xml_         the hardened XML parser, and the one policy for reading bytes off the network
dates        the two date spellings CELLAR writes, read in one place rather than four
http         the one httpx client — retries, content negotiation, politeness
cache        the disk cache, and the fixture cache that makes CI offline by construction
notices      tree notice → what versions exist and how to fetch each one
packages     a fetched Formex 4 zip: its members and its provenance
cellar       the public surface: resolve, branch_notice, versions, fetch_formex
feed         the notification endpoint: channel, window, pagination — the WATCH stage's eyes
feed_atom    reading what it sends back, which is not what Atom promises
formex/      Formex 4 markup → provision trees, amending documents, coverage stats
mod_roles    the modification-role vocabulary, empirical, with what each role means
modmeta      branch-notice modification annotations — the reference label set and clock 1
references   amending-prose reference grammar ("in Article 1(2), point (g)") → a location
instructions/ the amending act's own instructions, read structurally — the third signal
links        EUR-Lex anchor citation URLs; provision-level ELI does not resolve
adapter      EuCorpusAdapter, composed from the above
```

`modmeta`, `instructions` and `feed` are **capabilities of this adapter, not part of the
seam**: the first two produce `core.SignalReport`s that `emendrix.corroborate` consumes, the
third feeds `emendrix.watch`, and the four-method `CorpusAdapter` Protocol stays four methods
wide.

Nothing outside `http` and `cache` may construct an HTTP client. `feed` reaches the network
too, and does it through `CellarHttp` like everything else, so there is exactly one client,
one cache and one retry policy. `tests/test_architecture.py` checks it.
"""

from emendrix.eu.adapter import EuCorpusAdapter, FormexParser
from emendrix.eu.cellar import CellarClient
from emendrix.eu.feed import FeedResult, fetch_notifications
from emendrix.eu.feed_atom import FeedEntry, FeedIdentifier, FeedPage, parse_feed
from emendrix.eu.formex import Formex4Parser, ParsedAct, ParsedAmendingAct, ParserCoverage
from emendrix.eu.identifiers import CORPUS, Celex, ConsolidatedId, act_id, celex_of
from emendrix.eu.instructions import (
    InstructionParse,
    InstructionRecord,
    instruction_signal,
    parse_instructions,
)
from emendrix.eu.links import render_citation
from emendrix.eu.mod_roles import ROLE_CHANGE_TYPE, ModRole, RoleCode, UnknownRole
from emendrix.eu.modmeta import (
    ModificationRecord,
    ModificationSet,
    metadata_signal,
    parse_branch_modifications,
    touched_units,
)
from emendrix.eu.notices import TreeNotice, VersionRecord, WorkMetadata
from emendrix.eu.packages import FormexPackage

__all__ = [
    "CORPUS",
    "ROLE_CHANGE_TYPE",
    "Celex",
    "CellarClient",
    "ConsolidatedId",
    "EuCorpusAdapter",
    "FeedEntry",
    "FeedIdentifier",
    "FeedPage",
    "FeedResult",
    "Formex4Parser",
    "FormexPackage",
    "FormexParser",
    "InstructionParse",
    "InstructionRecord",
    "ModRole",
    "ModificationRecord",
    "ModificationSet",
    "ParsedAct",
    "ParsedAmendingAct",
    "ParserCoverage",
    "RoleCode",
    "TreeNotice",
    "UnknownRole",
    "VersionRecord",
    "WorkMetadata",
    "act_id",
    "celex_of",
    "fetch_notifications",
    "instruction_signal",
    "metadata_signal",
    "parse_branch_modifications",
    "parse_feed",
    "parse_instructions",
    "render_citation",
    "touched_units",
]
