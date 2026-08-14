"""A stand-in for the real Formex parser, so the adapter can be tested in isolation.

The adapter's own job, identifiers in, cached bytes out, states passed through untouched, is
testable on its own; parsing markup is not. This records what it was handed and produces a tree
with one provision in it, so the seam is exercised without pretending to parse anything.

**The one provision is not decoration.** A tree with no provisions is what the adapter reads
as "this package carried no act document I could read", and it answers a first-class
state rather than the empty tree. A stub that returned nothing would therefore make every
test using it assert against that state instead of against the seam it means to test.
`finds_nothing=True` asks for the empty tree deliberately, which is what the test of that rule
uses.
"""

from __future__ import annotations

from emendrix.core import AmendingActDoc, ProvisionNode, ProvisionTree
from emendrix.eu.packages import FormexPackage


class RecordingParser:
    """Implements `emendrix.eu.adapter.FormexParser` and remembers every package."""

    def __init__(self, *, finds_nothing: bool = False) -> None:
        self.packages: list[FormexPackage] = []
        self.finds_nothing = finds_nothing

    def parse_version(self, package: FormexPackage) -> ProvisionTree:
        self.packages.append(package)
        roots = (
            ()
            if self.finds_nothing
            else (ProvisionNode.from_plain_text("AR 1", "Subject matter and scope."),)
        )
        return ProvisionTree(
            act=package.act,
            version=package.served_version,
            language=package.language,
            roots=roots,
        )

    def parse_amending(self, package: FormexPackage) -> AmendingActDoc:
        return AmendingActDoc(act=package.act, tree=self.parse_version(package))
