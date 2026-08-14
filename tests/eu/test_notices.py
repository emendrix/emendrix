"""What a tree notice does with the values it has no business trusting.

The routing table is read off a document the server writes, and `parse_tree_notice` builds the
whole version inventory of an act from it. So the two questions here are the same question
twice: does one unreadable field cost the inventory, or does it cost only itself?

The notices in `tests/fixtures/eu/` are the real ones and are exercised through
`test_cellar.py`. These are hand-built minima, and deliberately so: no live notice is known to
carry either of these values, which is exactly why the behaviour needs stating somewhere.
"""

from __future__ import annotations

from emendrix.eu.identifiers import Celex
from emendrix.eu.notices import parse_tree_notice

CELEX = Celex.parse("32024R1689")


def _notice(*, document_date: str, entry_into_force: str, system: str) -> bytes:
    return f"""<NOTICE>
      <WORK>
        <ID_CELEX><VALUE>32024R1689</VALUE></ID_CELEX>
        <WORK_DATE_DOCUMENT><VALUE>{document_date}</VALUE></WORK_DATE_DOCUMENT>
        <RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE>
          <VALUE>{entry_into_force}</VALUE>
        </RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE>
        <SAMEAS><URI>
          <IDENTIFIER>32024R1689</IDENTIFIER><TYPE>{system}</TYPE>
        </URI></SAMEAS>
        <SAMEAS><URI>
          <IDENTIFIER>32024R1689</IDENTIFIER><TYPE>celex</TYPE>
        </URI></SAMEAS>
      </WORK>
    </NOTICE>""".encode()


def test_a_well_formed_date_survives() -> None:
    """The honest path, so the two tests below are about the exception and not about the parse."""
    notice = parse_tree_notice(
        _notice(document_date="2024-06-13", entry_into_force="2007/11/23", system="celex"), CELEX
    )
    assert notice.work.document_date is not None
    assert notice.work.document_date.isoformat() == "2024-06-13"
    assert [item.isoformat() for item in notice.work.entry_into_force] == ["2007-11-23"]


def test_an_impossible_date_is_unreadable_rather_than_fatal() -> None:
    """`2026-02-30` spells like a date and is not one. Only `date()` knows the calendar.

    The parser already answers `None` for `nonsense`, so answering `None` here is that same
    contract rather than a new leniency, and the alternative is a `ValueError` out of
    `parse_tree_notice` that costs the act its entire version inventory over one field nobody
    reads. Coverage gaps are counted, not crashed on.
    """
    notice = parse_tree_notice(
        _notice(document_date="2026-02-30", entry_into_force="2026-13-01", system="celex"), CELEX
    )
    assert notice.work.document_date is None
    assert notice.work.entry_into_force == ()
    assert notice.versions, "the inventory survives the unreadable field"


def test_a_system_the_adapter_cannot_address_is_dropped_not_raised() -> None:
    """`<TYPE>` lands in a URL path segment unencoded, so `ResourceRef` refuses `../..`.

    Refusing it must not become a `ValidationError` out of the inventory: the reference is
    simply one fewer address to try, exactly like a `SAMEAS` missing its `IDENTIFIER`.
    """
    notice = parse_tree_notice(
        _notice(document_date="2024-06-13", entry_into_force="2024-08-01", system="../../evil"),
        CELEX,
    )
    assert [ref.system for ref in notice.work.identifiers] == ["celex"]
