"""Where XML that came off the network is parsed, and the one policy that governs it.

Every document this adapter reads (tree notices, branch notices, the notification feed, every
member of every Formex package) is bytes from a remote endpoint. The stdlib's
`xml.etree.ElementTree` does not resolve *external* entities, so XXE is not reachable here, but
it does expand *internal* ones: a 300-byte document with four levels of nested entity
declarations expands to 1000 characters, and each further level multiplies by ten.

`defusedxml` is the answer Python's own documentation points at for exactly this
(`docs.python.org/3/library/xml.html#xml-vulnerabilities`). It has no transitive dependencies
and returns the stdlib's own `Element`, so every `find`/`findall`/`iterfind` in the package is
untouched by it.

Honest framing of the severity: the source is one government endpoint over HTTPS and the
impact would be the availability of a batch job, not disclosure. This is hardening, not an
incident response. It is here rather than at seven call sites because a policy stated once can
be checked once: `tests/test_architecture.py` allows `defusedxml` in this module and nowhere
else, and forbids every other module from importing a *parsing* entry point out of the stdlib.
Importing `Element` for a type annotation stays legal; it parses nothing.

**No committed fixture loses coverage.** All 9.9 MB of real CELLAR data under `tests/fixtures/`
was checked on 2026-08-07: not one document declares a `DOCTYPE` or an `ENTITY`. Formex 4 in
the wild does not use them, so the guard costs nothing that was ever being read.

`eu/packages.py` is the one exception and states its own reason: it needs `XMLPullParser`, for
which `defusedxml` ships no wrapper.
"""

from __future__ import annotations

from typing import Final
from xml.etree.ElementTree import ParseError

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

__all__ = ["NOT_WELL_FORMED", "fromstring"]

NOT_WELL_FORMED: Final = (ParseError, DefusedXmlException)
"""What "this document cannot be read" looks like: two exception families, not one.

`ParseError` is a `SyntaxError`; `defusedxml`'s refusals (`EntitiesForbidden`, `DTDForbidden`,
`ExternalReferenceForbidden`) descend from `ValueError` instead, so an `except ParseError`
would let one through. That matters because of a rule this project holds elsewhere: coverage
gaps are *counted*, not crashed on. A member the corpus serves that this code declines to
expand is a gap of exactly the same kind as a corrupt one, and every call site that counts the
second must count the first.
"""
