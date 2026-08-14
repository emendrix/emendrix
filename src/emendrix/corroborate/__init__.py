"""`emendrix.corroborate` — three independent signals held against each other.

The evaluation story of this project is not "the diff is accurate". It is that three
independently derived answers to *which provisions changed* (a structural diff of the two texts,
the corpus's own modification metadata, and a parse of the amending document's instructions) can
be compared, and that their disagreements are publishable findings rather than embarrassments.

```
merge    Delta + metadata signal + instruction signal → Delta with signals + disputed flags
report   the measurement of that: per-signal unit sets, pairwise precision/recall/F1, and the
         disagreement list, all read back off the merged delta rather than computed beside it
```

Core types only. Nothing in here knows what a legal identifier, a markup format or a role code
is: the corpus vocabulary stays in the adapter that read it, which is what lets this package run
unchanged over the toy corpus (`tests/toy_corpus.py`). No network, no clock, no model.
"""

from emendrix.corroborate.merge import Corroboration, corroborate
from emendrix.corroborate.report import (
    CorroborationReport,
    Disagreement,
    SignalAgreement,
    SignalUnits,
    agreement,
)

__all__ = [
    "Corroboration",
    "CorroborationReport",
    "Disagreement",
    "SignalAgreement",
    "SignalUnits",
    "agreement",
    "corroborate",
]
