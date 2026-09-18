"""The words this site uses, each defined once, on the methodology page, under its own anchor.

Every tag on the site links here rather than carrying its own definition, and every definition
has an `id`, so a page can point a reader at the one word it used. The entries define the
site's own vocabulary, what a tag or a heading means when emendrix prints it; none of them says
anything about the law. Each is true of the code that decides the state it names: the change
kinds of `diff`, the three-way split of `output/counts.py`, the three shapes of `dispute.py`,
the two clocks of `clocks.py` and the applies line of `pages/prose.py`. A definition that drifted
from its code would be the site misdescribing itself in the one place it explains itself.

It is a module of its own because the methodology page is at the size cap, and because the
tags point at its ids: `tags.GLOSSARY_OF` is held against `GLOSSARY` by a test.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.markup import Html, escape

__all__ = ["GLOSSARY", "glossary_html"]

GLOSSARY: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "version",
        "Version",
        "One consolidated text of an act, compared with the one recorded before it. A version "
        "is named by the date its changes came into force, or by the day emendrix first saw it "
        "where no in-force date is recorded.",
    ),
    (
        "amending-act",
        "Amending act",
        "An act whose instructions changed a watched act, as the committed changelog names it "
        "for a change. Each has a page here listing every watched act it changed. A version "
        'labelled "no amending act named" is one for which the EU\'s records name none: a fact '
        "about those records, not a doubt about the text.",
    ),
    (
        "change",
        "Change",
        "One article or annex that differs between two versions. The total on a version counts "
        "provisions, so a provision changed twice in one version counts once there and has two "
        "entries in the version's list of changes.",
    ),
    (
        "substantive",
        "Substantive",
        "A provision whose text changed in more than its dates, and which has text to show.",
    ),
    ("modified", "Modified", "The provision is in both versions and its text differs."),
    ("inserted", "Inserted", "The provision is in this version and not in the previous one."),
    ("deleted", "Deleted", "The provision is in the previous version and not in this one."),
    (
        "renumbered",
        "Renumbered",
        "The provision is in both versions, under a different number in each.",
    ),
    (
        "deferred",
        "Deferred",
        "The only differences in the provision's text are dates that moved, and exactly one "
        "date was added. The word says a date changed and nothing else did; it does not say "
        "what the date governs.",
    ),
    (
        "dates-only",
        "Dates only",
        "A provision whose every change in the version is deferred: it moved a date and "
        "nothing else.",
    ),
    (
        "without-text",
        "Without text",
        "A provision the EU's amendment metadata or the amending act's instructions named and "
        "the comparison of the two texts did not find, so there is no text on either side to "
        "show. It is still listed, with the source that named it.",
    ),
    (
        "sources-differ",
        "Where sources differ",
        "Each change is checked against three sources: a comparison of the two texts, the EU's "
        "own amendment metadata, and the amending act's instructions. Where they do not agree "
        "about a change, it is shown with what each source said, and none is dropped or "
        "overruled. It is a statement about the sources, not about the law. The measured table "
        "above counts the same thing, in its row on changes where the signals disagree.",
    ),
    (
        "not-in-every-list",
        "Not in every list",
        "Found in the text, but not every source lists it. The comparison read the change and "
        "its text is shown; it does not mean the text is in doubt, only that another source "
        "did not enumerate this provision.",
    ),
    (
        "no-text-found",
        "No text found",
        "A source lists it, but there is no text to show. It does not mean the change did not "
        "happen; the one source that carries text did not find it.",
    ),
    (
        "kinds-differ",
        "Kinds differ",
        "The sources name different kinds of change. Every source that looked found the "
        "provision and they disagree about how it changed; it does not say which of them is "
        "right.",
    ),
    (
        "unexplained",
        "Explanations",
        "An explanation is a model's account of a change, written from the two texts alone, "
        "and every provision it cites must be one it was given. A change without an "
        'explanation says why it has none. "All explained" means every change carries one, '
        'and "No explanations for this version" means the explain stage was not run for it.',
    ),
    (
        "quoted-verbatim",
        "Quoted verbatim",
        "A sentence the citation check replaced with a quotation of the provision, because the "
        "sentence it replaced cited something it could not trace. The count is of sentences.",
    ),
    (
        "in-force",
        "In force",
        "The date the EU's amendment metadata gives for the changes of a version. Where it "
        "gives none, the page says the in-force date is not stated rather than guessing one.",
    ),
    (
        "first-seen",
        "First seen, or detected",
        "The day emendrix first recorded the version. It is a fact about when this tool ran, "
        "not a legal date, and it names a version only where no in-force date is recorded.",
    ),
    (
        "applies-from",
        "Applies from",
        "The date a change applies from, printed only where it can be read without "
        "interpretation from a date change in the act's own text. Otherwise the change says "
        '"no date changed", where its text moved no date, or "not readable", with the reason '
        "where one is recorded.",
    ),
    (
        "consolidated-version",
        "Consolidated version",
        "An act's text with its amendments folded in, as EUR-Lex publishes it, identified by a "
        "code such as 02011R1169-20250401, whose date is the one EUR-Lex gives that text. On a "
        "version page v1 is the previous version and v2 this one, and the explanations cite "
        "them that way.",
    ),
)
"""(id, term, definition), in reading order: the objects, the kinds of change, the split of a
version's total, the three ways sources differ, the explanations, then the two clocks."""


def glossary_html() -> list[Html]:
    """The glossary section: its heading, and one addressable term per definition."""
    lines = [
        Html('<h2 id="glossary">Words this site uses</h2>'),
        Html('<dl class="glossary">'),
    ]
    for ident, term, definition in GLOSSARY:
        lines.append(Html(f'<dt id="{escape(ident)}">{escape(term)}</dt>'))
        lines.append(Html(f"<dd>{escape(definition)}</dd>"))
    lines.append(Html("</dl>"))
    return lines
