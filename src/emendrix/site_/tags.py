"""Tags: the adjectives a version and a change carry, and the tally a version is summed up by.

A tag is `<span class="tag tag--{kind}">`: an adjective, never clickable, with one fixed look
per kind wherever it appears, so a reader who has learned what one looks like on one page reads
it on the next without looking again. Its words say what it means and its colour, glyph or
border style says the same thing, so no tag rests on colour alone. The definitions live on the
methodology page, under its glossary; a list of tags is followed by one link there, and a tag
itself never is one.

A version is summed up as a tally: its total in a sentence, then only the categories present,
each tag counting itself. The categories a version does not have are not printed. The honesty a
row of zeros once protected is kept by two rules instead: the total is always printed, and the
tag for changes where the sources differ is present whenever that count is not zero, so a
disagreement is never missing from a summary that has one.

Every number is read off the committed document, never recomputed: the total and the split are
`entry.counts`, and the per-shape tags are read off the same function the site's published rates
are counted by, so they add up to the count beside them. The stored field is still called
`disputed`; only the reader's words changed.
"""

from __future__ import annotations

from collections import Counter
from typing import Final

from emendrix.output import ChangelogEntry
from emendrix.site_.dispute import dispute_shape
from emendrix.site_.markup import Html, count, escape
from emendrix.site_.untouched import UNTOUCHED_SENTENCE, all_textless, textless_words, untouched

__all__ = [
    "GLOSSARY_OF",
    "HELP_WORDS",
    "LIST_HELP_WORDS",
    "SHAPE_TAGS",
    "tag",
    "tags_help",
    "tally",
]

SHAPE_TAGS: Final[dict[str, tuple[str, str]]] = {
    "evidenced": ("differ-text", "Not in every list"),
    "no_text": ("differ-none", "No text found"),
    "kind": ("differ-kind", "Kinds differ"),
}
"""Each shape a disagreement takes, as its tag's kind and words, in the order the methodology
table lists them. The keys are `DisputeShapes`' own field names, which a test asserts: a fourth
shape added there without a tag here would be a disagreement a summary could not name."""

GLOSSARY_OF: Final[dict[str, str]] = {
    "substantive": "substantive",
    "dates-only": "dates-only",
    "no-text": "without-text",
    "differ": "sources-differ",
    "differ-text": "not-in-every-list",
    "differ-none": "no-text-found",
    "differ-kind": "kinds-differ",
    "unexplained": "unexplained",
    "quoted": "quoted-verbatim",
    "diff-only": "unexplained",
    "all-explained": "unexplained",
    "unattributed": "amending-act",
}
"""Every tag kind this module or a page can print, and the glossary term that defines it.

A test holds this against the glossary's own ids, so a tag cannot be printed that the page it
points readers to does not explain."""

HELP_WORDS: Final = "What these mean →"
"""The one link a list of tags is followed by, to the glossary that defines every one of them."""

LIST_HELP_WORDS: Final = "What the tags on these versions mean →"
"""The same link, said once above a list of version cards rather than under each of them."""


def tag(kind: str, words: str) -> Html:
    """One tag. `kind` names its fixed look and must be a key of `GLOSSARY_OF`."""
    return Html(f'<span class="tag tag--{escape(kind)}">{escape(words)}</span>')


def tags_help(root: str, words: str = HELP_WORDS) -> Html:
    """The link to the glossary, from a page whose climb to the site root is `root`."""
    return Html(
        f'<p class="tags-help"><a href="{escape(root)}methodology/#glossary">'
        f"{escape(words)}</a></p>"
    )


def _shapes(entry: ChangelogEntry) -> list[Html]:
    """One tag per shape the version's disagreements take, each counting itself."""
    shapes = Counter(
        dispute_shape(emitted.change.signals)
        for emitted in entry.changes
        if emitted.change.disputed
    )
    return [
        tag(kind, f"{shapes[shape]} {words[0].lower()}{words[1:]}")
        for shape, (kind, words) in SHAPE_TAGS.items()
        if shapes[shape]
    ]


def _tags(entry: ChangelogEntry, *, shapes: bool) -> list[Html]:
    """The categories present, in a fixed order, each only where its count is not zero.

    `substantive` is left to the tally where it is the whole of the version, and `without text`
    where every provision is in it, since the tally's sentence already says so. The gate's
    categories follow the split: a version the explain stage never ran for says that and
    nothing about explanations, and one with nothing unexplained and nothing quoted says so in
    one tag rather than as two absences.
    """
    counts = entry.counts
    split = counts.date_only or counts.textless
    tags: list[Html] = []
    if counts.substantive and (split or counts.substantive != counts.touched):
        tags.append(tag("substantive", f"{counts.substantive} substantive"))
    if counts.date_only:
        tags.append(tag("dates-only", f"{counts.date_only} dates only"))
    if counts.textless and not all_textless(entry):
        tags.append(tag("no-text", f"{counts.textless} without text"))
    if counts.disputed:
        tags.append(tag("differ", f"{counts.disputed} where sources differ"))
        if shapes:
            tags.extend(_shapes(entry))
    if entry.diff_only:
        tags.append(tag("diff-only", "No explanations for this version"))
        return tags
    if counts.unexplained:
        tags.append(tag("unexplained", f"{counts.unexplained} without an explanation"))
    if counts.quoted:
        tags.append(tag("quoted", f"{counts.quoted} quoted verbatim"))
    if not counts.unexplained and not counts.quoted:
        tags.append(tag("all-explained", "All explained"))
    return tags


def tally(entry: ChangelogEntry, *, shapes: bool, root: str | None = None) -> list[Html]:
    """A version summed up: the total in a sentence, the tags present, and the glossary link.

    `shapes` adds, after the sources-differ tag, one tag per shape the disagreements take; the
    version's own page has room for them and a card in a list does not. `root` is the climb to
    the site root, and a page that prints one glossary link for a whole list of cards passes
    none. A version that touched nothing is a sentence and nothing else, because no category
    can be present in it.
    """
    if untouched(entry):
        return [Html(f'<p class="tally">{escape(UNTOUCHED_SENTENCE)}</p>')]
    total = (
        textless_words(entry)
        if all_textless(entry)
        else f"{count(entry.counts.touched, 'change')} in this version"
    )
    lines = [Html(f'<p class="tally">{escape(total)}</p>')]
    items = _tags(entry, shapes=shapes)
    if items:
        lines.append(Html('<ul class="tags">' + "".join(f"<li>{t}</li>" for t in items) + "</ul>"))
    if root is not None:
        lines.append(tags_help(root))
    return lines
