# Self-hosted fonts

Three WOFF2 files, subset from two open-licence families by `scripts/subset_fonts.py`, which
verifies each upstream file's SHA-256 before it writes anything. The site build copies these
bytes to the site root under names carrying a digest of their content, and the stylesheet loads
them by a relative `url()`. Nothing is fetched from a third party.

Both families are licensed under the SIL Open Font License 1.1, whose full text sits beside the
files. Both reserve their names, and a subset is a Modified Version under that licence, so the
subsets are renamed "Emendrix Sans" and "Emendrix Serif". The copyright, trademark, vendor,
designer, URL and licence records inside each file are kept as upstream wrote them.

| File | Family (upstream) | Weight | Bytes | SHA-256 of the subset |
|---|---|---|---|---|
| `sans-400.woff2` | IBM Plex Sans, as "Emendrix Sans" | 400 | 14,204 | `424f1d2e60d34c5c0aad19c5a6113f3592b0b22eb9447b0a973f0038b65349d4` |
| `sans-600.woff2` | IBM Plex Sans, as "Emendrix Sans" | 600 (SemiBold) | 15,208 | `e2b79ccd394ed42fc73342d573df135c489ee87f5e530bf23a883306719233c4` |
| `serif-400.woff2` | Source Serif 4, as "Emendrix Serif" | 400 (Text optical size) | 36,856 | `de886d3d1ff23fb2ac0ae9e5458861182992904ffc1dbf1ed61b33827b462c18` |

66,268 bytes in total, against a budget of 180 KB (184,320 bytes) and at most four files, both
asserted by `tests/site_/test_fonts.py`. The subset bytes depend on the fontTools version that
wrote them (4.65.0 here); the glyph set, the features and the names do not.

## Upstream

| | IBM Plex Sans | Source Serif 4 |
|---|---|---|
| Release | `@ibm/plex-sans@1.1.0`, <https://github.com/IBM/plex> | `4.005R`, <https://github.com/adobe-fonts/source-serif> |
| Archive | <https://github.com/IBM/plex/releases/download/%40ibm/plex-sans%401.1.0/ibm-plex-sans.zip> | <https://github.com/adobe-fonts/source-serif/releases/download/4.005R/source-serif-4.005_WOFF2.zip> |
| Archive SHA-256 | `fb365d910566e6d199cc2c15579a7dd9a267128e18431a394ed81f1970c69200` | `af10e80dcd2296748b04cb9917db9f7ba0ae65101165fd2f0c16b9812d9abd28` |
| Font version | 3.005 | 4.005 |
| File read | `ibm-plex-sans/fonts/complete/woff2/IBMPlexSans-Regular.woff2` | `source-serif-4.005_WOFF2/TTF/SourceSerif4-Regular.ttf.woff2` |
| Its SHA-256 | `ba711a3085ff9f27440b6b9c4550cfc47c97bf36591d5da958b975bb3add8c1a` | `6b053e98f0838afe81f3e784727be4583a7c13bb42f198dc5202ecffee0aaee0` |
| File read | `ibm-plex-sans/fonts/complete/woff2/IBMPlexSans-SemiBold.woff2` | |
| Its SHA-256 | `f78048030eab62e860efa39a0df79e2e5581bf122eb95b9bc42c0b8a4988d205` | |
| Licence | `LICENSE-IBMPlexSans.txt`, from the archive, Reserved Font Name "Plex" | `LICENSE-SourceSerif4.txt`, the repository's `LICENSE.md` at `4.005R`, Reserved Font Name "Source" |

## What each subset keeps

- **Sans characters:** `U+0020-007E, U+00A0-00FF, U+0100-017F, U+0218-021B, U+2010-2027,
  U+202F, U+2032-2034, U+20AC, U+2190-2193, U+2197, U+2208, U+2212, U+221A, U+2260,
  U+2264-2265`: Latin, Latin-1, Latin Extended-A, the Romanian comma-below letters, and the
  punctuation, arrows and signs the site prints.
- **Serif characters:** the sans ranges plus `U+0370-03FF, U+0400-045F`, Greek and basic
  Cyrillic, which stored provision text quotes.
- **Sans features:** `kern, mark, mkmk, ccmp, locl, zero, lnum, tnum`.
- **Serif features:** `kern, mark, mkmk, ccmp, locl, lnum, tnum, pnum`.
- **Dropped from both:** `liga`, `dlig`, `calt`, every stylistic set and all hinting, so no two
  characters of verbatim legal text can render as one glyph.
