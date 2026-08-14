"""`Formex4Parser` — the object `EuCorpusAdapter` holds, and the coverage it keeps aside.

The adapter's seam is two methods returning core types (`eu/adapter.py`), because that is all
the generic engine may know. The coverage report is not part of that contract — it is an
adapter-side measurement, consumed by the eval harness — so this class exposes both: the
narrow Protocol methods, and the wider `read_*` ones that hand back the counts as well.

It holds no state between calls. Parsing the same package twice returns equal trees.
"""

from __future__ import annotations

from emendrix.core import AmendingActDoc, ProvisionTree
from emendrix.eu.formex.amending import parse_amending_act
from emendrix.eu.formex.model import ParsedAct, ParsedAmendingAct
from emendrix.eu.formex.parse import parse_act
from emendrix.eu.packages import FormexPackage

__all__ = ["Formex4Parser"]


class Formex4Parser:
    """Implements `emendrix.eu.adapter.FormexParser` over Formex 4 markup."""

    def parse_version(self, package: FormexPackage) -> ProvisionTree:
        """The provision tree of one version of one act."""
        return parse_act(package).tree

    def parse_amending(self, package: FormexPackage) -> AmendingActDoc:
        """An amending document: its own tree, what it amends, and what it quotes."""
        return parse_amending_act(package).document

    def read_version(self, package: FormexPackage) -> ParsedAct:
        """The tree *and* the parser-coverage report — what the eval harness measures."""
        return parse_act(package)

    def read_amending(self, package: FormexPackage) -> ParsedAmendingAct:
        """The amending document *and* the parser-coverage report."""
        return parse_amending_act(package)
