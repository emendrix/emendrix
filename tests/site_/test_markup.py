"""The four helpers every page is built out of, checked on their own.

Escaping is the site's only defence against a stray tag in text that came out of a legal
document or out of a model, `inline` is the two inches of Markdown the metric caveats are
written in, `cut` is the house promise that a truncation is visible, and `count` agrees a
noun with the number in front of it. Each is asserted here rather than through a rendered
page, because a page that happens to contain no `<` is not evidence that the escaping still
works.
"""

from __future__ import annotations

from emendrix.site_.markup import count, cut, escape, inline


def test_text_out_of_a_document_can_never_open_a_tag() -> None:
    assert escape('<script>"x"&y') == "&lt;script&gt;&quot;x&quot;&amp;y"


def test_inline_honours_the_two_constructs_the_caveats_use_and_nothing_else() -> None:
    assert inline("**bold** and `code`") == "<strong>bold</strong> and <code>code</code>"
    assert inline("<b>not markup</b> and _not italic_") == (
        "&lt;b&gt;not markup&lt;/b&gt; and _not italic_"
    )


def test_one_is_the_only_singular_and_zero_is_plural_english() -> None:
    """Zero and two read the same way; one is the case a bare `f"{n} provisions"` gets wrong."""
    assert count(0, "provision") == "0 provisions"
    assert count(1, "provision") == "1 provision"
    assert count(2, "provision") == "2 provisions"


def test_a_cut_quotation_says_how_much_it_dropped() -> None:
    assert cut("abc", 10) == "abc"
    assert cut("a" * 20, 5) == "aaaaa […truncated by emendrix: 15 characters omitted…]"
