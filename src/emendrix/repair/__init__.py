"""`emendrix.repair` — correcting one part of an entry that is already committed.

The loop's unit of work is a whole transition: it fetches two versions, diffs them, explains
every change and writes one entry. That is the right unit for producing an entry and the wrong
one for correcting a part of it, because the model is not deterministic: re-running a
transition to fix one change rewrites every correct explanation beside it, and a reader who
quoted a neighbouring sentence yesterday finds different words at the same URL today.

So a repair addresses **the thing that is wrong and nothing else**: it reads a committed
payload, takes it apart, replaces one part of it, and writes it back through `OutputRepo`, which
replaces the entry in place and keeps every other entry in that act's `CHANGELOG.md`
byte-identical. One kind re-reads the corpus, because the part that is wrong is the stored text
itself and no payload can show that; it still replaces that part and nothing else.

Four properties hold for every repair kind, and each is a test:

1. **Round-trip identity.** Taking an entry apart and putting it back unchanged re-serialises to
   the bytes it came from, except for fields the schema has gained since it was written.
2. **Sibling byte-identity.** Repairing one change leaves every other change's prose, citations
   and gate outcome exactly as they were.
3. **No-op safety.** An entry a repair does not actually change is not written. The comparison
   is against the re-serialised original, so schema drift alone never counts as a change.
4. **Re-runnable.** Running a repair twice produces one commit.

A repair is always explicitly invoked and is never reached from the resume path: `holds_finished`
treats a settled failure as settled on purpose, and a repair that a backfill could trigger would
re-address the same entries for ever.

Layout:

```
entry         read one committed payload, take it apart, put it back, decide whether it moved
select        which committed entries a repair kind would touch, over a whole repository
corroborate   the deterministic repair: the third signal recomputed
explanations  the paid repair: a change with no explanation, asked again from its payload
unexplained   the restating repair: a note that quoted a library, put in the house register
staleness     whether a change still reads as the evidence its explanation was written about
rederive      today's parse of a transition already published, and its merged delta
reask         asking again about the changes whose evidence moved, and splicing the answers
evidence      the fetching repair: a pass over a repository, to a budget, and what it would cost
pricing       what a paid repair would address and cost, computed before anything is sent
render        the table an operator decides from, before anything is written
commit        opening the repository, committing what moved, and naming the commit
cli           `emendrix repair`: the EU composition root and the sub-verbs
```

Everything except `cli` is generic over any corpus, exactly as `backfill/` is: core types, the
committed document, and no corpus vocabulary at all.
"""

from emendrix.repair.entry import (
    RepairResult,
    RepairTarget,
    UnitShift,
    delta_of,
    moved,
    rebuild,
    shift_between,
    with_record,
)
from emendrix.repair.select import for_act, read_targets

__all__ = [
    "RepairResult",
    "RepairTarget",
    "UnitShift",
    "delta_of",
    "for_act",
    "moved",
    "read_targets",
    "rebuild",
    "shift_between",
    "with_record",
]
