"""`emendrix.texts`: the verbatim text of every provision of every stored version.

A directory beside the changelogs repository, never inside it and never published, holding one
file per version an adapter served. It sits beside the loop, not in it: no stage reads it, and
`emendrix run` is the same with or without it. The corpus, not the store, is the source of
truth, and every file in it can be rebuilt from there.

Layout:

- `model.py`: the header, node and state lines, and the unreadable answer.
- `codec.py`: a tree to the bytes of one version file, and back.
- `store.py`: `TextStore`, the directory, its two refusals and its reader.
- `config.py`: where the store lives, flag over environment over watchlist.
- `build.py`: `build_store`, filling the store from any corpus source.
- `cli.py`: `emendrix texts build|show`, the composition root.
"""
