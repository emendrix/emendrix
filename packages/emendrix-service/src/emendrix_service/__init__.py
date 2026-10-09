"""emendrix-service: email watchlists over the published emendrix change record.

It filters what the record already states and never re-derives it: a watchlist is a set of keys,
a match is an intersection with changes the record names, and an email repeats stored facts with
their links. It reads the record only through `emendrix_record`, never imports the pipeline and
makes no model call. Its side effects each sit in one module: the clock in `clock.py`, the
environment in `settings.py`, the database under `db/`, the listener in `app.py`, outbound
connections in `mail/transport.py` and `ops/ship.py`.

Nothing here is legal advice. See `README.md`.
"""

from emendrix_record import DISCLAIMER

__all__ = ["DISCLAIMER", "__version__"]

__version__ = "0.1.0"
