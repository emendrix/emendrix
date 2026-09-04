# The output format

What a run writes: the layout of the output git repository, the shape of the Markdown, the
versioned JSON beside it, and every cap that can truncate a quote. Start at
[`../README.md`](../README.md) for how to run it, and [`./pipeline.md`](./pipeline.md) for what
produces these events.

## A regulatory dependency with a review workflow

The product claim of this project is that your regulatory dependencies get the same review workflow
as your code dependencies, and `emendrix.output` is where that claim is cashed. A run ends as a
**commit in a local git repository you own**: one directory per act, a Markdown `CHANGELOG.md`
with the newest version first, and the same events as versioned JSON beside it:

```bash
uv run emendrix run --once --output-repo ~/regulatory-changelog     # or [output] in watchlist.toml
uv run emendrix diff 32017R0745 02017R0745-20170505 02017R0745-20200424 \
    --fixture-dir tests/fixtures/eu --markdown                      # diff-only: no model, no key
```

```
~/regulatory-changelog/eu/32017R0745/CHANGELOG.md
~/regulatory-changelog/eu/32017R0745/changes/02017R0745-20200424.json
```

The format is chosen for what it *forces*: every sentence carries a citation that links to a
provision in a version; `before`/`after` are verbatim quotes rather than paraphrase, so the model
cannot be wrong about them; applicability is on its own line, separate from the text change,
because "in force" and "applies to you" are different questions; and the change type comes from
the structural diff, never from the model's opinion. A `disputed` change is rendered and marked
with *what* disagreed, "seen by corpus metadata, not by the structural diff", because a
disagreement hidden is a disagreement lied about. A sentence the citation gate wrote in place of
ungrounded prose says so in the text. Both quote caps are printed with the number of characters
they dropped: a silently truncated "verbatim" quote is worse than a long one. The committed golden
file [`../tests/output/golden/mdr-changelog.md`](../tests/output/golden/mdr-changelog.md) is a real
example, byte-asserted against what the command writes.

## Three decisions about the repository

**It is yours.** emendrix creates it if it is absent and commits into it, and never pushes;
pushing, hosting and ownership are not this tool's business.

**It must be a repository emendrix made.** A path that resolves inside an existing git repository
is refused before a byte is written, and so is a path that *is* one and does not carry emendrix's
own marker file. Together those are the general form of the embarrassing bug where a mis-scoped
`git add` commits emendrix's source into your changelog or the reverse.

**Re-emitting an event is a no-op.** Identical bytes are not rewritten, nothing is committed when
nothing was staged, and an entry that *has* changed is replaced in place rather than duplicated at
the top, so a cron entry running hourly produces one commit per amendment.

**A correction is a new commit on top, and history is never rewritten.** `emendrix repair` is the
one command that reaches into entries already committed. It reads a payload, replaces one part of
it and writes it back through the same writer, so the entry is replaced in place and every other
entry in that act's `CHANGELOG.md` keeps its bytes. It is always invoked explicitly and is never
reached from a resume, it writes only the entries it actually changes, and each one is its own
commit whose subject says the entry was repaired rather than emitted. What a repair did is
recorded on the entry as a `repairs` entry beside the `explain` and `gate` blocks, which keep
recording the run that produced it: no repair retracts a call that was made. Re-serialising an
entry written under an older schema adds the fields the schema has gained since, so a repaired
entry's diff carries those additions beside the correction; entries the repair had nothing to say
about are not touched at all, which is what keeps that drift on the corrected set and nowhere
else.

**A repaired explanation was written later than the entry it sits in, and the entry says so.**
`emendrix repair explanations` asks the model again for a change that shipped with no
explanation, so that change's prose is newer than every sentence beside it and than the
`detected_on` date, which does not move: a repair is not a detection. The `repairs` entry carries
the date the pass ran, how many changes it addressed, how many it repaired, how many it could not,
and what the calls cost. It also carries `coordinates_checked: false`, because a repair works from
the entry's own stored texts and holds neither provision tree, so the gate's coordinate check did
not run; recording it is how an unrun check is kept from reading as one that passed. A change the
model failed on again keeps the reason it was committed with, word for word.

"Newest first" means the newest **version**, not the newest emission. The poller runs forward and a
backfill fills history in underneath it weeks later, so a new entry is inserted at its place in the
order rather than at the top; every entry already in the file keeps its bytes and its neighbours.
Backfilling after a poll therefore produces the file a poll after a backfill would, and which
happened first stops being visible in the artifact.

There is deliberately **no default path**. Every other location the project picks by itself is
disposable, a response cache or a watch state file, and a git repository the tool commits into is
neither. With nothing configured, `run` prints its report and writes nothing.

## The JSON

The JSON carries `schema_version` from its first byte because other tools read it.

Two things in it are there for a reader who wants to render the events differently later. Each
change names the acts that amended it (`amending_acts`), as corpus-scoped identifiers rather than
a string to parse, so grouping a changelog by amending act needs no second pass over the corpus. No
title is fetched for one, so the identifier is what ships. And each signal publishes the claims
behind its verdict (`corroboration.signals[].claims`), at the depth the corpus made them, so an
annotation on `AR 5 PA 1 ALN 1 PTA (bb)` survives into the artifact instead of being flattened to
`AR 5`. The structural diff publishes none: it produces the changes themselves, so a copy there
would be a second delta. Neither field is a schema bump: both have defaults, and `schema_version`
stays `1.0`.

A rendering of these artifacts as a browsable site is in [`./site.md`](./site.md).
