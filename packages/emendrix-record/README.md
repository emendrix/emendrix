# emendrix-record

The published emendrix record as a reader sees it: the models of the files the pipeline
publishes, a safe reader that reads them fresh on every call, and two pure helpers over the
record's keys. Every reader beside the pipeline reads the record through it, the MCP server in
`../emendrix-mcp` included, so there is one reader and one contract test against the writer.

> Not legal advice: this output is machine-computed from published texts, carries no lawyer's
> review, and is engineering assistance only.

## What it reads

Two locations it is given, both read-only, both read again on every call:

- the directory of a changelogs repository: `index.json` at the root, `<corpus>/<act>/index.json`
  per act, and the payloads under `<corpus>/<act>/changes/`, every path taken from the index and
  resolved under the root (one that leaves it is refused);
- optionally, the `api/v1/catalogue.json` a site build wrote, for labels, aliases, domains and
  page addresses. Without it every permalink is reported unavailable.

A payload whose bytes differ from the `sha256` its index row states is still returned, marked
as a mismatch: it means the repository is being rewritten while it is read. Every failure is a
value, `Unavailable`, with a sentence a caller can repeat, never an exception.

## What it never does

It depends on `pydantic` only and never on `emendrix`, so nothing that reads through it can
reach the pipeline's model stage. It calls no model, opens no connection, reads no clock and no
environment, and writes no file. It decides nothing: every field is read off a published file,
and the helpers in `links.py` and `locations.py` are mechanical rules written down in their
docstrings.

## Layout

| Module | Holds |
|---|---|
| `emendrix_record/__init__.py` | `DISCLAIMER`, the same sentence as the pipeline's |
| `emendrix_record/models.py` | the root index, an act index and the catalogue |
| `emendrix_record/payload.py` | one payload: the event, its changes, its corroboration |
| `emendrix_record/reasons.py` | `REASON_SENTENCES`, one sentence per `dispute_reason` code |
| `emendrix_record/reads.py` | what a read returns: `PayloadRead`, `ChangeRead`, `Unavailable` |
| `emendrix_record/record.py` | `Record`, which reads all of the above off disk, and `row_for` |
| `emendrix_record/links.py` | `change_anchor` and `entry_anchors`: the fragment the site gives one change |
| `emendrix_record/locations.py` | `within`, `parse_location` and `human` over canonical locations |

Two tests in the `emendrix` suite import both distributions:
`tests/output/test_record_contract.py` holds the models, the disclaimer, the dispute-reason
sentences and the anchor rule to the originals, and `tests/output/test_record_fixture.py` holds
the committed fixture under `tests/fixtures/` to what the emendrix writers produce. The member's
own `tests/test_record_architecture.py` checks over the source that it keeps the promises above.
