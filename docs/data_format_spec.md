# Data format specification

This document defines every data file that `phonfeat` reads. It is
normative: a file is valid if and only if it satisfies the
constraints stated here.

All files are YAML 1.2, UTF-8 encoded, with Unix line endings
(`\n`). Keys are lowercase with underscores; string values may use
any UTF-8 characters unless otherwise noted.

Two top-level shapes are defined:

- **Feature system files** (`*.feature.yaml`) describe a
  feature system and the phones it covers.
- **Symbol table files** (`*.symbols.yaml`) describe how to
  tokenize a notation.

Additional auxiliary files (`deprecations.yaml`,
`diacritic_order.yaml`) are specified in their own sections.

---

## 1. Feature system files

A feature system file defines a `lingcore.FeatureSystem` and a set
of phones with feature values.

### 1.1 Top-level structure

```yaml
name: panphon
version: "0.1.0"
description: "PanPhon-style distinctive features."
source: "Adapted from ipa_all_panphon in data.ods."
features:
  - name: voi
    kind: binary
    description: "Voiced."
    aliases: []
phones:
  - ipa: "p"
    xsampa: "p"
    type: consonant
    name: "voiceless bilabial plosive"
    characteristics: [vls, blb, stp]
    features:
      voi: false
      nas: false
      # ...
```

Required top-level keys: `name`, `version`, `features`, `phones`.

Optional top-level keys: `description`, `source`, `license`,
`metadata` (a mapping of arbitrary keys).

### 1.2 The `features` block

A list of feature definitions. Order is significant: it defines
the column order of any `FeatureMatrix` materialized from this
system.

Each entry has:

| Key           | Type    | Required | Notes                          |
|---------------|---------|----------|--------------------------------|
| `name`        | string  | yes      | Canonical name.                |
| `kind`        | string  | no       | `binary` (default), `multi`, or `scalar`. Only `binary` is implemented in v0.1. |
| `description` | string  | no       | Human-readable.                |
| `aliases`     | list    | no       | Alternative names.             |

Constraints:

- Feature names must be unique within the file.
- Aliases must not collide with any other feature's name or alias.
- Aliases may be given as a string (single alias), which is
  wrapped as a one-element list by the loader.

### 1.3 The `phones` block

A list of phone definitions.

Each entry has:

| Key              | Type    | Required | Notes                          |
|------------------|---------|----------|--------------------------------|
| `ipa`            | string  | yes      | Canonical IPA form.            |
| `xsampa`         | string  | no       | Canonical X-SAMPA form.        |
| `type`           | string  | yes      | `consonant`, `vowel`, or `other`. |
| `name`           | string  | no       | Human-readable description.    |
| `classification_tags` | list | no    | Short classifier tags, e.g. `[vls, blb, stp]`. See §1.4. |
| `features`       | mapping | no       | Feature values. Defaults to empty. |
| `metadata`       | mapping | no       | Arbitrary application data.    |

The `xsampa` and `metadata` keys are specified but not currently
produced by `scripts/ods_to_yaml.py`, and `storage.py` does not read
them. `name` is likewise specified but neither produced nor read.

Constraints:

- `ipa` values must be unique within the file.
- `type` must be one of the three values listed.
- Every key in `features` must match a declared feature name or
  alias.
- `classification_tags` entry values are not validated against a
  vocabulary; `phonfeat` accepts any abbreviation (§1.4).
- The `ipa` value must be in canonical form (§4).

### 1.4 The `phones` block — classification tags

The optional `classification_tags` list holds short classifier
abbreviations that describe the phone's articulatory properties.
Each element is a single abbreviation, e.g. `vls` (voiceless),
`blb` (bilabial), `stp` (stop). A phone may have any number of
tags; a phone with no tags has no articulatory classification.

```yaml
- ipa: s
  type: consonant
  classification_tags: [sib, frc, vls, alv]
  features:
    ...
```

Some properties are naturally multi-valued. A phone may have
multiple tags under the same classifier: `s` is both a sibilant
(`sib`) and a fricative (`frc`), both of which are manner
properties. The schema does not enforce one-tag-per-classifier.
Consumers who want structured classification can group tags by
classifier using the mapping in the `definitions` sheet.

`phonfeat` does not enforce a fixed vocabulary of tags. The
built-in files use the abbreviations defined in the `definitions`
sheet of the source ODS.

*In previous schema versions (1.0 and earlier), this field was
called `characteristics` and stored under a single classifier
name. Files written against 1.0 are rejected by the current
loader.*

---

## 2. Symbol table files

A symbol table defines the mapping from notation-specific strings
to canonical phones. `phonfeat` uses one symbol table per notation
(IPA, X-SAMPA).

### 2.1 Top-level structure

```yaml
notation: ipa
description: "IPA symbol table."
diacritics:
  - symbol: "ʰ"
    kind: suffix
    description: "Aspirated."
  - symbol: "̃"
    kind: combining
    description: "Nasalized."
tie_bar: "͡"
symbols:
  - symbol: "p"
    canonical: "p"
    kind: base
  - symbol: "t͡ʃ"
    canonical: "t͡ʃ"
    kind: base
  - symbol: "a"
    canonical: "a"
    kind: base
```

Required top-level keys: `notation`, `symbols`.

Optional: `description`, `diacritics`, `tie_bar`.

**Not yet implemented.** The `diacritics` and `tie_bar` blocks, and
the per-symbol `kind` field below, are specified here but are neither
produced by `scripts/ods_to_yaml.py` nor read by `storage.py`. The
shipped tables contain only `schema_version`, `notation`,
`description`, and `symbols`. Treat those three constructs as
reserved for the tokenizer work rather than as current format
features.

### 2.2 The `symbols` block

Each entry has:

| Key        | Type   | Required | Notes                          |
|------------|--------|----------|--------------------------------|
| `symbol`   | string | yes      | The notation-specific form.    |
| `canonical`| string | yes      | The canonical phone symbol (see §4). |
| `kind`     | string | no       | `base` (default) or `modifier`. |

The tokenizer performs maximal munch over `symbols` sorted by
descending `symbol` length. Longer matches win.

### 2.3 The `diacritics` block

Each entry has:

| Key          | Type   | Required | Notes                          |
|--------------|--------|----------|--------------------------------|
| `symbol`     | string | yes      | The diacritic as written.      |
| `kind`       | string | yes      | `prefix`, `suffix`, or `combining`. |
| `description`| string | no       | Human-readable.                |
| `canonical_position` | integer | no | Order in the canonical diacritic sequence (§4). Defaults to 100. |

The `canonical_position` values defined across all diacritics
determine the ordering rule in §4.3.

---

## 3. Deprecations and diacritic ordering

### 3.1 `deprecations.yaml`

Maps deprecated or variant glyphs to their canonical replacements.

```yaml
- from: "g"           # Latin small g
  to: "ɡ"             # IPA script g
  reason: "IPA convention."
- from: "ʧ"           # ligature tesh
  to: "t͡ʃ"
  reason: "Use tie-barred affricate."
```

Each entry: `from` (string), `to` (string), optional `reason`.

When canonicalizing IPA, `phonfeat` applies these substitutions in
order, using longest-match-first so that `ʧ` is replaced before
`t` is considered.

### 3.2 `diacritic_order.yaml`

A list of diacritic categories in canonical order.

```yaml
- category: phonation
  symbols: ["̥", "̬", "ʰ", "̤", "̰"]
- category: place
  symbols: ["̪", "̺", "̻"]
- category: rounding
  symbols: ["ʷ", "ʲ", "ˠ", "ˤ", "ᶣ"]
- category: syllabicity
  symbols: ["̩", "̯"]
- category: release
  symbols: ["ⁿ", "ˡ", "̚"]
- category: nasalization
  symbols: ["̃"]
- category: length
  symbols: ["ː", "ˑ"]
- category: tone
  symbols: ["˥", "˦", "˧", "˨", "˩"]
```

When reordering a phone's diacritics into canonical form, the
loader sorts them by the position of their category in this list,
then by their position within the category's `symbols` list.

---

## 4. Canonical forms

### 4.1 IPA canonical form

A phone's IPA canonical form is produced by applying these
transformations in order:

1. **NFC normalization.** Unicode Normalization Form C.
2. **Deprecation replacement.** Apply `deprecations.yaml`.
3. **Diacritic reordering.** Sort combining diacritics by
   `diacritic_order.yaml` (§3.2). If a diacritic's category is not
   listed, it retains its original position, relative to other
   unlisted diacritics.
4. **Tie bar normalization.** Prefer the combining tie bar
   (U+0361, `t͡ʃ`) over the ligature (U+02A8). This is currently
   achieved through `deprecations.yaml` (ligature affricates are
   listed there as replacements), not by a separate normalization
   step in `canonicalize.py`. Preferring tie bars over unmarked
   sequences is *not* implemented.

The canonical form is what appears in a feature system file's
`ipa` field.

### 4.2 X-SAMPA canonical form

A phone's X-SAMPA canonical form is produced by applying these
transformations in order:

1. **ASCII constraint.** X-SAMPA uses printable ASCII.
2. **Multi-character sequence preservation.** Sequences like `tS`
   are single symbols, not two.
3. **Underscore-di­acritic normalization.** Diacritics are always
   written as `_X` suffixes; a diacritic never appears between the
   base and another diacritic.
4. **Deprecation replacement.** Apply `deprecations.yaml` for
   X-SAMPA-specific variants.

The canonical form is what appears in a feature system file's
`xsampa` field.

### 4.3 Diacritic stacking order

A phone may carry multiple diacritics. In canonical form, they
appear in this order, immediately following the base:

1. Voicing and phonation: `̥`, `̬`, `̤`, `̰`
2. Place: `̪`, `̺`, `̻`
3. Rounding and labialization: `ʷ`, `ʲ`, `ˠ`, `ˤ`, `ᶣ`
4. Syllabicity: `̩`, `̯`
5. Release: `ⁿ`, `ˡ`, `̚`
6. Nasalization: `̃`
7. Length: `ː`, `ˑ`
8. Tone: `˥`, `˦`, `˧`, `˨`, `˩`

The `diacritic_order.yaml` file may refine this list but must
cover at least these categories in this relative order.

---

## 5. Validation

A file is valid if it satisfies every constraint in this
specification. `phonfeat` validates files at load time and raises
`phonfeat.errors.DataFormatError` with a message identifying the
offending entry.

Validators check:

- **Structural:** required keys present; types match.
- **Referential:** every feature value keys a declared feature;
  every `canonical` in a symbol table matches an `ipa` in the loaded
  feature system. (The second half is not yet enforced: the loader
  validates each symbol table in isolation, without a feature system
  in hand.)
- **Uniqueness:** feature names, phone `ipa` values, symbol table
  entries.
- **Canonicalization:** every phone's `ipa` field is already in
  canonical form; a violation is an error, not silently fixed.

### 5.1 Known gaps between this spec and the loader

These are specified but not enforced by `storage.py` as of
`phonfeat` 0.1.0. They are listed rather than removed so the next
session does not have to rediscover them:

- Unknown top-level keys are ignored, not rejected.
- Unknown keys inside a `features` or `phones` entry are ignored.
- `classification_tags` are not checked against a tag vocabulary.
- Symbol-table `canonical` values are not cross-checked against a
  feature system.
- The `diacritics`, `tie_bar`, and per-symbol `kind` constructs are
  not parsed (§2.1).

Closing any of these is a behavior change and needs a test.

Canonicalization being an error rather than an auto-fix is
deliberate: it forces the data producer to run the canonicalizer
and commit its output, so the file on disk and the file in memory
agree.

---

## 6. Examples

### 6.1 A minimal feature system

```yaml
name: toy
version: "0.1.0"
features:
  - name: voi
    description: "Voiced."
  - name: nas
    description: "Nasal."
phones:
  - ipa: "p"
    xsampa: "p"
    type: consonant
    name: "voiceless bilabial plosive"
    features:
      voi: false
      nas: false
  - ipa: "b"
    xsampa: "b"
    type: consonant
    name: "voiced bilabial plosive"
    features:
      voi: true
      nas: false
  - ipa: "m"
    xsampa: "m"
    type: consonant
    name: "voiced bilabial nasal"
    features:
      voi: true
      nas: true
```

### 6.2 A minimal symbol table

```yaml
notation: ipa
symbols:
  - symbol: "p"
    canonical: "p"
  - symbol: "b"
    canonical: "b"
  - symbol: "m"
    canonical: "m"
  - symbol: "a"
    canonical: "a"
```

---

## 7. Versioning

This specification is versioned alongside `phonfeat`. The current
version is **1.1**, corresponding to `phonfeat` 0.1.x. A file may
declare the schema version it was written against:

```yaml
schema_version: "1.1"
```

If present, `phonfeat` rejects files declaring any version other
than the current one; if absent, the loader assumes the current
version.

### Revision history

**1.1** (2026-10-29): Replaced `characteristics` (a list of
compound phrases like `sib frc`) with `classification_tags` (a
list of single abbreviations like `sib`, `frc`). Files written
against 1.0 are rejected.

**1.0** (2026-10-15): Initial version. `characteristics` as a
list of tags.
