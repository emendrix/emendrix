"""Who runs this, what it is and is not, and what it does on the reader's machine.

The page a visitor reaches from the nav or the footer when they want to know whether the site
is worth trusting with their attention. Everything on it is either a sentence this repository
already says somewhere else, a fact about the tool rather than about the law, or a value the
deployment passed on the command line. It describes emendrix; it never describes a regulation.

Four of its values are the deployment's own: the operator's name, their public page, an
address to write to, and what the poller on this instance last did. None of them is committed,
and none has a default, so a build given none of the four renders the page without its "Who
runs it" section rather than with a placeholder where a person should be. The section appears
when any one is set and says only what it was given, which is why each is rendered on its own
rather than as one sentence needing all of them.

The polling sentences are in that section because they are facts about the instance rather than
about the corpus: how far the corpus has been read is a property of whoever is running this
copy, and a reader who cannot tell a quiet corpus from a stopped one has no other way to ask.

"What it is not" says so in the page's own words rather than reprinting the disclaimer. The
footer carries that constant on this page as on every other, and a reader who met the same
sentence twice on one screen would read the second as a different claim they had to compare.
The section also states what the roster does not cover, from the same constant the acts index
prints and under the same condition: `pitch.SCOPE` claims no Directive is watched, so both
pages render it from `SiteInputs.kinds` and drop it the day one is.

No JSON-LD: there is no schema.org type that describes a page about a tool honestly, and the
rule in `seo.py` is that a page declares a type or declares nothing.

No clock, no network, no model call, like every other page here.
"""

from __future__ import annotations

from emendrix.site_.chrome import PageChrome, page, repository_links
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.pitch import PITCH, SCOPE, scope_holds
from emendrix.site_.polled import PolledState
from emendrix.site_.urls import depth_of, up

__all__ = ["render_about"]

_PATH = "about/"
_DEPTH = depth_of(_PATH)
"""One directory down from the site root, so every internal link on it climbs once."""

_WHAT_IT_IS = (
    "emendrix watches the Publications Office notification feed for the acts on its watchlist. "
    "When one of them is amended it fetches both consolidated versions as structured XML, "
    "computes which articles and annexes differ, checks that finding against two independent "
    "signals, the publisher's own amendment metadata and a parse of the amending act's "
    "instructions, and has a model phrase the difference between the two verbatim texts. "
    "Anything the three sources disagree about ships marked disputed rather than dropped."
)

_NOT_THE_MODEL = (
    "The model never decides whether something changed, which provisions were involved, or what "
    "kind of change it is. Every other stage is deterministic Python, and each result is "
    "committed to a git repository as Markdown and JSON before any of it reaches a page."
)

_NOT_A_SUBSTITUTE = (
    "It is not a lawyer's review, and it is not the official text. Every act and every event "
    "here links the consolidated version the comparison was computed from, and that document, "
    "not this page, is the one to read when an answer has to be right."
)

_NOT_CURATED = (
    "Nothing here is selected to flatter the tool. Every figure the project measures is "
    "published with the sentence saying what it does not mean, the cases it fails included."
)

_PRIVACY = (
    "This site sets no cookies, counts no readers and asks nothing of any other host. The one "
    "script it loads is served from here and fetches this site's own search index, so a search "
    "runs in the browser and reaches nobody. Nothing about a reader is stored anywhere."
)

_MAILBOX = (
    "A message sent to that address arrives in the operator's own mailbox and goes nowhere else."
)


def _last_checked(polled: PolledState | None) -> list[Html]:
    """How far the corpus has been read, and what has been announced but cannot be read yet.

    `checked_through` is the end of the last window the poller read and not the moment it ran,
    so the sentence says "published up to": a reader weighing whether a quiet corpus is a
    stopped one is owed the date the corpus was read through, and a cursor dressed as a run
    time would be the one claim these two sentences exist to let them check. Neither sentence
    says whether the answer is good or bad, which is the reader's judgement and not the page's.

    A record with no window end is a poller that has never completed one, so there is nothing
    to report and nothing is printed, exactly as for a build handed no record at all.
    """
    if polled is None or polled.checked_through is None:
        return []
    lines = [
        Html(
            f"<p>The corpus was last checked for changes published up to "
            f"{escape(polled.checked_through.isoformat())}.</p>"
        )
    ]
    if polled.waiting:
        alone = polled.waiting == 1
        waiting = (
            "has been announced and is waiting for its text"
            if alone
            else "have been announced and are waiting for their text"
        )
        since = (
            ""
            if polled.waiting_since is None
            else f"{', first seen on ' if alone else ', the oldest first seen on '}"
            f"{polled.waiting_since.isoformat()}"
        )
        lines.append(
            Html(
                f"<p>{escape(count(polled.waiting, 'consolidation'))} "
                f"{escape(waiting)}{escape(since)}.</p>"
            )
        )
    return lines


def _who_runs_it(chrome: PageChrome, polled: PolledState | None) -> list[Html]:
    """The operator, their page, their address and the poller's record, each only if given.

    A name with a URL is a linked name; a URL with no name is a link whose text is the URL,
    which is the honest rendering of a deployment that published an address and no person. The
    contact line is separate, because a build may pass an address and nothing else.

    The address is wrapped in the `email_off` comment pair, which is the documented opt-out
    from the edge rewriting a `mailto:` into a placeholder a script decodes. Left alone, that
    rewrite loaded a second script on this one page while the footer beneath it promised one
    (verified against the live site on 2026-09-03), and on a site whose product is the
    precision of its own claims that is the worst class of defect there is.
    """
    checked = _last_checked(polled)
    if not (chrome.operator or chrome.operator_url or chrome.contact or checked):
        return []
    lines = [Html("<h2>Who runs it</h2>")]
    if chrome.operator and chrome.operator_url:
        named = Html(f'<a href="{escape(chrome.operator_url)}">{escape(chrome.operator)}</a>')
    elif chrome.operator:
        named = escape(chrome.operator)
    elif chrome.operator_url:
        named = Html(f'<a href="{escape(chrome.operator_url)}">{escape(chrome.operator_url)}</a>')
    else:
        named = Html("")
    if named:
        lines.append(Html(f"<p>This instance of emendrix is run by {named}.</p>"))
    if chrome.contact:
        address = escape(chrome.contact)
        lines.append(
            Html(
                f"<p>Write to <!--email_off-->"
                f'<a href="{escape("mailto:" + chrome.contact)}">{address}</a>'
                f"<!--/email_off-->. {escape(_MAILBOX)}</p>"
            )
        )
    return lines + checked


def render_about(site: SiteInputs) -> Html:
    """The about page. Deterministic: same inputs, same bytes, no clock, no network."""
    chrome = site.chrome
    root = up(_DEPTH)
    source, changelogs = repository_links(chrome)
    body = join(
        (
            Html("<h1>About emendrix</h1>"),
            Html(f'<p class="lede">{escape(PITCH)}</p>'),
            Html("<h2>What it is</h2>"),
            Html(f"<p>{escape(_WHAT_IT_IS)}</p>"),
            Html(f"<p>{escape(_NOT_THE_MODEL)}</p>"),
            Html(
                f"<p>How each of those claims is measured, over what, and what none of the "
                f'figures means is on the <a href="{root}methodology/">methodology page</a>.</p>'
            ),
            Html("<h2>What it is not</h2>"),
            Html(f"<p>{escape(_NOT_A_SUBSTITUTE)}</p>"),
            *([Html(f"<p>{escape(SCOPE)}</p>")] if scope_holds(site.kinds) else []),
            Html(f"<p>{escape(_NOT_CURATED)}</p>"),
            *_who_runs_it(chrome, site.polled),
            Html("<h2>The code and the data</h2>"),
            Html(
                f"<p>The generator is open source in {source}, and the changelog documents it "
                f"writes are public in {changelogs}. Every page here is a rendering of files "
                f"committed to those two places, so anything the site shows can be traced back "
                f"to something a reader can open.</p>"
            ),
            Html("<h2>On your machine</h2>"),
            Html(f"<p>{escape(_PRIVACY)}</p>"),
        ),
        "\n",
    )
    return page(
        title="About — emendrix",
        description=("Who runs emendrix, what it is and is not, and what it does on your machine."),
        body=body,
        path=_PATH,
        chrome=chrome,
        feeds=((feed_path(None), feed_title(None)),),
    )
