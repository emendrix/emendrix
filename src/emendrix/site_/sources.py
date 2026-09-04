"""A path inside a git repository, printed as a link only where the home's layout is known.

Two pages print such a path, and they name two different repositories: the methodology page
names the evaluation report it read every published figure out of, and an event page names the
changelog document its entry was committed to. The repositories differ, the honesty rule does
not, so the rule is stated once here rather than twice. It sits beside the page modules rather
than inside one of them because a page importing markup from another page makes the second
page's shape a dependency of the first, and neither of these pages is about the other.

Both branches are honest, which is the whole requirement: a build given no public home, or
given one whose file layout is not known here, prints the path for a reader who has the
checkout, and only a home whose shape is known becomes a link.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.markup import Html, escape

__all__ = ["file_url", "repo_file"]

_GITHUB: Final = "https://github.com/"
"""The one public host whose file layout this module knows. A prefix, not a vendor endorsement."""


def file_url(repo_url: str, path: str) -> str | None:
    """Where a committed file is browsable under a public home, or None when the shape is unknown.

    GitHub serves a committed file at `<repo>/blob/<ref>/<path>`, and `main` is the ref a
    public home publishes; a bare join of the repository URL and the path answers 404, which
    is how the link proving the methodology page's figures came to fail on its first click
    (verified 2026-09-03, and again over a changelog repository's own `CHANGELOG.md` on
    2026-09-04). The ref is `main` rather than a recorded revision because `eval run` records
    the revision of the tree it scored and the report is committed after it, so a URL naming
    that revision would point at a tree the file is not in yet.

    Any other host renders the path as text instead: the layout of a forge nobody has checked
    is a guess, and a guessed link is worse here than no link at all.
    """
    base = repo_url.rstrip("/")
    return f"{base}/blob/main/{path}" if base.startswith(_GITHUB) else None


def repo_file(path: str, repo_url: str) -> Html:
    """A path inside the repository: a link where one can be built, plain text otherwise.

    The path is printed either way, so the sentence around it reads the same in both
    configurations and nothing has to be worded twice.
    """
    shown = Html(f"<code>{escape(path)}</code>")
    href = file_url(repo_url, path) if repo_url else None
    if href is None:
        return shown
    return Html(f'<a href="{escape(href)}">{shown}</a>')
