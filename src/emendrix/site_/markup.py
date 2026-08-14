"""Turning strings into HTML safely, and the two inches of Markdown the page understands.

The page renders text that came out of legal documents and out of a model. Neither is trusted
input, both can contain `<`, `&` and `"`, and a static page is exactly the artifact where a
stray tag is discovered by a stranger rather than by a test. So there is one escaping function
and **every string on the page goes through it, including the ones that look safe**.

`inline` is the second half. The metrics table's caveat sentences are written once, in
`eval_/metric_rows.py`, in the Markdown the README needs; re-authoring them in HTML would be the
same sentences in two places, which is how a caveat gets softened in one of them. So the page
reads the same rows and converts the two constructs those sentences use, `**bold**` and
`` `code` ``, and nothing else. It is not a Markdown renderer and must never grow into one:
anything it does not recognise is left as literal, escaped text, which is the safe direction to
fail in.

Truncation on this page is visibly marked exactly as it is in the changelog
(`output/markdown.py`), and reuses that module's marker rather than inventing a second wording
for the same promise. `count` is here for the same reason `cut` is: text formatting with no page
knowledge, needed by every module that renders a number, and a count phrased in one module and
not in the next is how "1 provisions" reaches a reader.

`Html` is a `NewType`, following `core/provisions.py`, which distinguishes `ProvisionText` from
`ComparisonText` the same way: two forms of text that must never be confused should not share a
type, and raw text and page-ready markup are both `str` with nothing between them but whether
somebody remembered to call `escape`. Be precise about what that buys, because it is easy to
overclaim:

- **It does** stop raw text being passed where a fragment is expected, and back. `mypy --strict`
  rejects it, at every function boundary in the package.
- **It does** make each `Html(...)` a visible, greppable "I have checked this line" marker, so
  the review question becomes *is this mint justified* rather than *did anyone look*.
- **It does not** check inside a minted string. An f-string interpolates anything, so
  `Html(f"<p>{raw}</p>")` type-checks. Nothing short of routing every fragment through a
  `.format()` helper changes that, and that trade buys less than it costs to read.

`markupsafe` is the library answer and works identically. It is not worth a dependency to
publish one static file, and it would not match the idiom already in `core/`.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from typing import Final, NewType

from emendrix.output.markdown import TRUNCATION_MARKER

__all__ = ["Html", "count", "cut", "escape", "inline", "join"]

Html = NewType("Html", str)
"""A string that is safe to place in the page. `escape` and `inline` are how one is minted."""

_BOLD: Final = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_CODE: Final = re.compile(r"`([^`]+)`")


def escape(value: str) -> Html:
    """Every string that reaches the page goes through here, including the safe-looking ones."""
    return Html(html.escape(value, quote=True))


def inline(value: str) -> Html:
    """Escaped text with `**bold**` and `` `code` `` honoured. Not a Markdown renderer.

    Escaping happens first, so the only tags in the result are the ones this function put
    there; the two patterns run over already-escaped text and cannot resurrect markup.
    """
    escaped = escape(value)
    with_code = _CODE.sub(lambda match: f"<code>{match[1]}</code>", escaped)
    return Html(_BOLD.sub(lambda match: f"<strong>{match[1]}</strong>", with_code))


def join(parts: Iterable[Html], separator: str = "") -> Html:
    """Concatenate fragments. Safe because every part already is, which is the type's job."""
    return Html(separator.join(parts))


def count(number: int, noun: str) -> str:
    """`0 acts`, `1 act`, `3 acts`. A page of one should not read as a rendering accident.

    `noun` is the singular and the plural is it plus `s`, which covers every noun this site
    counts (provision, act, change, sentence, event, transition, page, feed). A noun that
    pluralises any other way does not belong here: it would need its own plural passed in, and
    inventing one silently is how a page ends up saying `1 entrys`.

    `eval_/prose.py::count` is a helper of the same shape that takes an explicit plural, and the
    two are duplicated knowingly rather than merged: `eval_` may not import a page-rendering
    module, and widening this one to carry irregulars would break the rule it is written around.
    """
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def cut(value: str, cap: int) -> str:
    """`value` capped at `cap` characters, with the number of dropped characters shown.

    A silently shortened quotation of a legal text is worse than a long one, so the cut says how
    much it took, under the same rule and with the same marker as the changelog's quote caps.
    """
    if len(value) <= cap:
        return value
    return value[:cap].rstrip() + " " + TRUNCATION_MARKER.format(dropped=len(value) - cap)
