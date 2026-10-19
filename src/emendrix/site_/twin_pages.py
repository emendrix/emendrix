"""The twin surface, path -> contents: the twins index, each pair of acts' index, a page per
pair whose texts differ in more than numbering, and each committed map served under the API.

The index is written only where a shown map exists, since nothing links it otherwise. An
identical pair gets no page, because its page could only say that the texts are the same,
which its line on the pair index already says; nor does a pair whose texts differ in numbering
alone, whose page could only show renumbering. The API file is the map's committed bytes,
never a re-serialisation, so its digest is the record's.
"""

from __future__ import annotations

from emendrix.site_.inputs import SiteInputs
from emendrix.site_.pages.twin import render_twin_page
from emendrix.site_.pages.twins_index import render_twin_pair, render_twins_index
from emendrix.site_.twin_model import twin_views
from emendrix.site_.urls import twin_api_href, twins_href

__all__ = ["twin_pages"]


def twin_pages(site: SiteInputs) -> dict[str, str | bytes]:
    """Every twin file this build writes; empty where no shown map exists."""
    views = twin_views(site)
    if not views:
        return {}
    files: dict[str, str | bytes] = {f"{twins_href()}index.html": render_twins_index(site, views)}
    for view in views:
        files[f"{view.path}index.html"] = render_twin_pair(site, view)
        for shown in view.pages:
            files[f"{shown.path}index.html"] = render_twin_page(site, view, shown)
        committed = site.twins.raw.get(view.slug)
        if committed is not None:
            files[twin_api_href(view.slug)] = committed
    return files
