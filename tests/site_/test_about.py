"""The page that says who runs the site, and the rule that it names nobody by default.

Rendered directly rather than through the built tree, because the whole point of the operator
fields is that the committed build passes none of them: the configured shapes exist only in a
string a test asks for. What the shipped tree carries is asserted over the golden instead.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from helpers import REPORTS, text_of

from emendrix import DISCLAIMER
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_.inputs import collect_site
from emendrix.site_.markup import escape
from emendrix.site_.pages.about import render_about

OBSERVED = date(2026, 8, 9)

OPERATOR = "A. Person"
OPERATOR_URL = "https://example.invalid/who"
CONTACT = "hello@example.invalid"


def _about(*, operator: str = "", operator_url: str = "", contact: str = "") -> str:
    site = collect_site(
        generated_on=OBSERVED,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        operator=operator,
        operator_url=operator_url,
        contact=contact,
    )
    return render_about(site)


def test_the_page_says_what_the_tool_is_and_points_at_the_measurements() -> None:
    rendered = _about()
    assert "<h1>About emendrix</h1>" in rendered
    assert "<h2>What it is</h2>" in rendered
    assert "The model never decides whether something changed" in rendered
    assert 'href="../methodology/">methodology page</a>' in rendered


def test_the_disclaimer_reaches_this_page_once_like_every_other_page() -> None:
    """The footer carries it here as everywhere, and the body does not carry it again.

    "What it is not" is the one section on the site where the disclaimer would sit naturally,
    which is exactly why it printed twice on one screen: a reader meeting the same sentence
    in a section and again in the footer reads the second as a further claim to compare
    against the first. The section says what the tool is not in its own words instead.
    """
    rendered = _about()
    assert escape(DISCLAIMER) in text_of(rendered)
    assert text_of(rendered).count(escape(DISCLAIMER)) == 1
    assert "<h2>What it is not</h2>" in rendered
    assert "it is not the official text" in rendered


def test_a_build_that_names_nobody_has_no_who_runs_it_section() -> None:
    """The committed build passes none of the three, and a placeholder would be worse than
    silence: an about page that names a person nobody can write to is a claim, not a courtesy.
    """
    rendered = _about()
    assert "<h2>Who runs it</h2>" not in rendered
    assert "mailto:" not in rendered


def test_the_operator_is_named_and_linked_when_both_are_given() -> None:
    rendered = _about(operator=OPERATOR, operator_url=OPERATOR_URL, contact=CONTACT)
    assert "<h2>Who runs it</h2>" in rendered
    assert f'<a href="{OPERATOR_URL}">{escape(OPERATOR)}</a>' in rendered
    assert f'<a href="mailto:{CONTACT}">{CONTACT}</a>' in rendered


def test_a_name_without_a_url_is_plain_words_and_a_url_without_a_name_is_its_own_text() -> None:
    named = _about(operator=OPERATOR)
    assert "<h2>Who runs it</h2>" in named
    assert "<a href" not in named.split("<h2>Who runs it</h2>")[1].split("<h2>")[0]
    assert escape(OPERATOR) in named
    addressed = _about(operator_url=OPERATOR_URL)
    assert f'<a href="{OPERATOR_URL}">{OPERATOR_URL}</a>' in addressed


def test_a_contact_alone_renders_the_contact_line_alone() -> None:
    rendered = _about(contact=CONTACT)
    assert "<h2>Who runs it</h2>" in rendered
    assert "is run by" not in rendered
    assert f'<a href="mailto:{CONTACT}">{CONTACT}</a>' in rendered


def test_the_contact_address_is_marked_so_the_edge_leaves_it_alone() -> None:
    """The footer promises one script and this is the page that would have loaded two.

    The edge rewrites a `mailto:` into a placeholder its own script decodes, and did so here
    until 2026-09-03, on the one page whose subject is what the site does on a reader's
    machine. The comment pair is the documented opt-out, so it is markup with a job and a test.
    """
    rendered = _about(contact=CONTACT)
    assert f'<!--email_off--><a href="mailto:{CONTACT}">{CONTACT}</a><!--/email_off-->' in rendered


def test_every_operator_value_is_escaped_in_the_href_and_in_the_text() -> None:
    """All three arrive from a command line and none of them is trusted."""
    rendered = _about(
        operator='Bobby "><script>',
        operator_url='https://example.invalid/"><script>',
        contact='a"><script>@example.invalid',
    )
    assert "<script>" not in rendered
    assert "&quot;&gt;&lt;script&gt;" in rendered


def test_the_page_promises_no_tracking_without_saying_the_word_a_second_time() -> None:
    """The footer's `no cookies, no analytics, no third-party requests` is on every page, and
    the golden holds each page to exactly one occurrence of that word: a second one would mean
    something had grown a tracker. So the privacy paragraph says the same thing in its own
    words rather than repeating the one the count watches.
    """
    rendered = _about()
    assert rendered.count("analytics") == 1
    assert "sets no cookies, counts no readers" in rendered
