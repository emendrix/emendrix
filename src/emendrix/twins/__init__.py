"""Twin provisions: which units of one act are textually similar to units of another.

Computed deterministically from two stored trees with no model: the word ratio over every
same-kind unit pair, mutual best matches at a floor read off the corpus, children aligned
level by level below each pair, and the differing passages under caps that keep the map from
reproducing either text. `emendrix twins build` writes the result into the changelog repository
as one JSON document per pair. Twin means textually similar by this measure and nothing more.

Layout:

- `model.py`: the map's models and its path in the changelog repository.
- `pair.py`: the word ratio, mutual-best pairing, child alignment and the floor.
- `passages.py`: the differing passages and the caps on them.
- `build.py`: two trees to one map, and the map to its committed bytes.
- `write.py`: the map into the changelog repository, committed only when it moves.
- `cli.py`: `emendrix twins build`, the composition root.
"""
