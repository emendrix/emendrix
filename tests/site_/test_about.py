"""The page that says who runs the site, and the rule that it names nobody by default.

Rendered directly rather than through the built tree, because the whole point of the operator
fields and of the poller's record is that the committed build passes none of them: the
configured shapes exist only in a string a test asks for. What the shipped tree carries is
asserted over the golden instead, and that the flag reaches the page at all is asserted through
the shipped command in `test_site_build.py`.
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
from emendrix.site_.pitch import SCOPE
from emendrix.site_.polled import PolledState

OBSERVED = date(2026, 8, 9)

OPERATOR = "A. Person"
OPERATOR_URL = "https://example.invalid/who"
CONTACT = "hello@example.invalid"

POLLED = PolledState(checked_through=date(2026, 9, 11), waiting=3, waiting_since=date(2026, 9, 3))


def _about(
    *,
    operator: str = "",
    operator_url: str = "",
    contact: str = "",
    kinds: tuple[tuple[str, int], ...] = (),
    polled: PolledState | None = None,
) -> str:
    site = collect_site(
        generated_on=OBSERVED,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        operator=operator,
        operator_url=operator_url,
        contact=contact,
        kinds=kinds,
        polled=polled,
    )
    return render_about(site)


def test_what_it_is_not_states_the_roster_scope_once_and_under_the_same_condition() -> None:
    """The acts index prints the same constant, so the two pages cannot say it differently,
    and both drop it the day a Directive is watched rather than carrying a false sentence."""
    rendered = _about(kinds=(("Regulation", 4),))
    assert text_of(rendered).count(escape(SCOPE)) == 1
    assert rendered.index("it is not the official text") < rendered.index(escape(SCOPE)[:40])
    assert escape(SCOPE) not in _about(kinds=(("Regulation", 60), ("Directive", 7)))
    assert escape(SCOPE) not in _about()


def test_the_scope_paragraph_leaves_the_disclaimer_alone() -> None:
    """The footer carries the disclaimer here as everywhere, exactly once, and the new
    paragraph is about the roster rather than about advice."""
    rendered = _about(kinds=(("Regulation", 4),))
    assert text_of(rendered).count(escape(DISCLAIMER)) == 1
    assert "advice" not in escape(SCOPE)


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


def test_the_state_file_gives_the_page_the_date_the_corpus_was_read_through() -> None:
    """Two sentences a deployment cannot fudge: the cursor the poller reached, and what has
    been announced since without its text arriving. The first says "published up to" because
    that is what the cursor means; a run time would be a different and unsupported claim."""
    rendered = _about(polled=POLLED)
    assert "<h2>Who runs it</h2>" in rendered
    assert "The corpus was last checked for changes published up to 2026-09-11." in rendered
    assert (
        "3 consolidations have been announced and are waiting for their text, "
        "the oldest first seen on 2026-09-03." in rendered
    )
    assert "stale" not in rendered and "healthy" not in rendered


def test_one_waiting_consolidation_reads_as_one_rather_than_as_a_plural() -> None:
    """A page of one should not read as a rendering accident, and it dates the one it has."""
    rendered = _about(
        polled=PolledState(
            checked_through=date(2026, 9, 11), waiting=1, waiting_since=date(2026, 9, 10)
        )
    )
    assert (
        "1 consolidation has been announced and is waiting for its text, "
        "first seen on 2026-09-10." in rendered
    )


def test_nothing_waiting_prints_the_cursor_and_no_second_sentence() -> None:
    """The quiet answer is the normal one and it still says how far the corpus was read."""
    rendered = _about(polled=PolledState(checked_through=date(2026, 9, 11)))
    assert "published up to 2026-09-11." in rendered
    assert "waiting for" not in rendered


def test_a_build_handed_no_state_file_renders_the_page_it_renders_today() -> None:
    """The flag is optional, so a clone, a fresh checkout and any deployment that does not
    pass it get exactly the page they got before it existed. A record the poller wrote before
    closing its first window is the same answer, byte for byte."""
    plain = _about()
    assert "<h2>Who runs it</h2>" not in plain
    assert "last checked" not in plain
    assert _about(polled=PolledState()) == plain
    assert _about(operator=OPERATOR, polled=PolledState()) == _about(operator=OPERATOR)


def test_the_polling_sentences_leave_the_disclaimer_alone() -> None:
    """The footer carries it here as everywhere, exactly once, whatever the section holds."""
    assert text_of(_about(polled=POLLED)).count(escape(DISCLAIMER)) == 1
