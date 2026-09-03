"""`emendrix.site_`: the published static site, generated from committed artifacts.

The trailing underscore keeps the import from shadowing anything named `site` (the same
convention as `eval_`). Everything here is deterministic Python over things a previous run
wrote and a person committed: no clock, no network, no model.

Four names are the package's whole surface: what the site is built from (`read_entries`,
`collect_site`, `SiteInputs`) and what writes it (`write_site`). The renderers stay behind
their own modules, because a page is chosen by the builder and by nobody else.
"""

from emendrix.site_.build import write_site
from emendrix.site_.entries import read_entries
from emendrix.site_.inputs import SiteInputs, collect_site

__all__ = ["SiteInputs", "collect_site", "read_entries", "write_site"]
