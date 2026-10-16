"""`emendrix.eu.substances`: which EU tables hold substance entries, and what identifies them.

Three things, and nothing else:

- `profiles.py`: which table of which act is read as entries, which column keys a row, which
  columns carry identifiers, and the header words that must be present before a table at that
  position is trusted. Every profile was read off the markup on a stated date and fails closed
  when the header no longer matches.
- `numbers.py`: CAS, EC and CLP Index numbers, recognised by shape and **check digit only**. No
  list of substances from outside the corpus is consulted, so a value the act prints with a
  wrong digit is counted and never published as an identifier.
- `keys.py`: the four key forms a profile may name, read from one cell.

The rule the package keeps: a row is an entry because the act prints it in a profiled table,
and an identifier is an identifier because its check digit holds. Nothing here says what a
substance is or whether it is regulated; it says where a number appears.
"""

from emendrix.eu.substances.keys import KeyForm, KeyReading, entry_name, read_key
from emendrix.eu.substances.numbers import (
    SCHEMES,
    Scheme,
    cas,
    ec,
    identifiers_in,
    index,
    read_identifier,
)
from emendrix.eu.substances.profiles import (
    PROFILES,
    TableProfile,
    header_matches,
    profiles_for,
)

__all__ = [
    "PROFILES",
    "SCHEMES",
    "KeyForm",
    "KeyReading",
    "Scheme",
    "TableProfile",
    "cas",
    "ec",
    "entry_name",
    "header_matches",
    "identifiers_in",
    "index",
    "profiles_for",
    "read_identifier",
    "read_key",
]
