"""`emendrix.eu.formex` — Formex 4 markup → the core provision vocabulary.

The structured format of EU legislation is **Formex 4**, not AKN4EU: no `akn` manifestation
resolves for these acts and the XHTML one carries zero `eId`s (verified 2026-08-05). Formex is
the better hand in any case, because its nesting maps 1:1 onto CELLAR's own
modification-location vocabulary, which is what makes the structural diff and the reference
label set directly comparable.

```
text.py        the two text forms (verbatim / comparison) and the machine-readable dates
locations.py   which element contributes which location segment, and the tag vocabulary
documents.py   which members of a package are documents, and where the units are in them
parse.py       the walk: package → ProvisionTree, with a coverage report beside it
amending.py    an amending act: its own tree, what it amends, and the provisions it quotes
model.py       ParserCoverage — what the walk could not place, counted rather than hidden
parser.py      Formex4Parser, the object the adapter holds
```

Parsing is `xml.etree.ElementTree`'s object model throughout, entered through the hardened
`fromstring` in `eu/xml_.py` because every document here is bytes off the network. `lxml` buys
nothing: no fixture needs XPath beyond `find`, the documents are read once each behind a disk
cache, and it would put a C build in the container for it.

Three properties this package guarantees, each tested:

- **Verbatim.** Stored text is the document's own characters in the document's own spacing;
  whitespace normalisation lives only in the comparison form, which is built separately at
  extraction time. The one thing serialising a tree has to add is a line break where the
  markup opened a block and left no text at all, so a title does not run into its subtitle.
- **Deterministic.** No clock, no network, no model, and a fixed document order — two runs
  produce identical trees, because changelogs are diffed in git.
- **Counted.** Every element the vocabulary does not know is descended through and tallied
  into `ParserCoverage`, never dropped and never raised on.
"""

from emendrix.eu.formex.amending import parse_amending_act
from emendrix.eu.formex.model import ParsedAct, ParsedAmendingAct, ParserCoverage
from emendrix.eu.formex.parse import parse_act
from emendrix.eu.formex.parser import Formex4Parser

__all__ = [
    "Formex4Parser",
    "ParsedAct",
    "ParsedAmendingAct",
    "ParserCoverage",
    "parse_act",
    "parse_amending_act",
]
