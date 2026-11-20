# Project summary

## What phonfeat is

`phonfeat` is the notation-aware layer between the abstract structures
of [`lingcore`](https://github.com/<your-user>/lingcore) and a study
that actually reads data. It knows how sounds are written down, and it
knows how they are described.

It provides:

- **Canonicalization** of IPA and X-SAMPA strings, so the same phone
  has one spelling.
- **Tokenization** of a written form into segments, with diacritics
  stacked onto the phone they modify and prosody kept separate.
- **Reading profiles**, which declare what a corpus assumes about its
  own notation — substitutions, separators, characters to ignore.
- **Corpus survey**, a diagnostic report on what a set of forms would
  require before it can be tokenized.
- **Inventories**: segments, optional categories, a feature matrix and
  a tokenizer, bound into one object.
- **Feature models**: the bundled PanPhon- and Hayes-style tables, and
  the loader for tables of your own.

In the family of packages, `phonfeat` sits above `lingcore` and below
`lingaligner`:

```
lingcore      abstract structures: segments, features, matrices
   |
phonfeat      notation, tokenization, feature data, inventories
   |
lingaligner   alignment, distances, comparison
```

## What phonfeat is not

- **Not a file reader.** A corpus, here, is a list of strings.
  Extracting those strings from a spreadsheet, a Python literal or a
  text dump is the caller's job. The package provides machinery for
  reading strings, not for opening files.
- **Not a corpus object.** It does not know that some forms answer
  the same concept or belong to the same language. That grouping is a
  property of a study, and it belongs to the layer above.
- **Not a distance.** It exposes features and categories; how far
  apart two segments are is a modelling decision, and it lives in
  `lingaligner`.
- **Not a theory.** No phonology, no allophony, no syllable structure,
  no sound change. Notation and feature data, nothing more.

These exclusions are deliberate. They are what let a study with an
unusual transcription convention be handled by declaring a profile
rather than by editing the package.

## Design principles

1. **Notation is data, not code.** The symbol tables and feature
   tables are YAML files. Adding a notation or a feature system adds
   data; it does not add branches to a function.
2. **A profile says what the caller knows.** A corpus that writes
   `c` for `t͡ʃ` is not wrong, it is written in a practical orthography.
   The package does not guess; the caller declares, in a small YAML
   document, how the strings should be read.
3. **Fail loudly on a string, report patiently on a corpus.** One
   `tokenize` call that cannot proceed raises with the offset and the
   offending code point. One `survey` call over ten thousand forms
   collects every blocker and keeps going, because the first bad cell
   in a spreadsheet is not the interesting one.
4. **Determinism.** Symbol matching is longest-first, ties broken by
   codepoint order, so the same input always yields the same segments.
5. **Honest diagnostics.** `survey` reports what a corpus requires and
   stops. It does not silently repair, reorder or drop.

## Status

### Implemented in v0.1

- `canonicalize_ipa`, `canonicalize_xsampa` — spelling normalization.
- `tokenize` — maximal-munch tokenization of IPA and X-SAMPA.
- `Profile`, `load_profile` — declarative reading of a corpus.
- `survey`, `SurveyReport`, `Blocker` — corpus diagnostics.
- `Inventory` — segments, categories, features and a tokenizer.
- `load_feature_model`, `load_symbol_table`, `FeatureModel`,
  `SymbolTable` — the bundled data and the loaders for your own.
- `PhonfeatError` and its subclasses.

### Planned

- **`ipa_to_xsampa`, `xsampa_to_ipa`** — conversion through the symbol
  tables. The IPA-to-X-SAMPA direction is lossless; the reverse is
  not, because X-SAMPA spells some distinctions with one form.
- **`attach_features`** — attaching a feature model's values to
  segments, so a tokenized corpus carries its descriptions.
- **`inventory_from_corpus`** — deriving a segment inventory from a
  corpus instead of taking it from a table.
- **`minimal_feature_set`** — computing a feature system sufficient to
  distinguish an inventory's segments.

### Not planned

- **File readers.** Spreadsheets, JSON, databases: the caller's
  business.
- **A corpus object.** The grouping is the study's, and the study is
  the package above.
- **Distances and trees.** Comparison is `lingaligner`'s work.
- **A built-in orthography converter.** Orthography-to-phonology
  requires knowing the language; a profile is how a caller supplies
  what they know.

## Versioning

`phonfeat` follows [semantic versioning](https://semver.org/) from
`0.1.0`. While the major version is `0`, breaking changes may occur
between minor versions and are recorded in `docs/decisions.md`.

## License

GPL-3.0-or-later. See `LICENSE`.
