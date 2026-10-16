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
| `characteristics`| list    | no       | Short classifier tags, e.g. `[vls, blb, stp]`. |
| `features`       | mapping | no       | Feature values. Defaults to empty. |
| `metadata`       | mapping | no       | Arbitrary application data.    |

Constraints:

- `ipa` values must be unique within the file.
- `type` must be one of the three values listed.
- Every key in `features` must match a declared feature name or
  alias.
- Every key in `characteristics` must match a declared
  characteristic tag (see §1.4).
- The `ipa` value must be in canonical form (§4).

### 1.4 Feature values and undefined

The `features` mapping may contain, for each feature, one of:

- `true` — the feature applies and is positive.
- `false` — the feature applies and is negative.
- *absent from the mapping* — the feature is undefined for this
  phone.

This is a three-valued encoding. An absent feature is **not**
equivalent to `false`: it means the feature does not apply to the
phone, or the phone's value for that feature is not specified.

Example: mid tone, whose PanPhon features are both undefined.

```yaml
- ipa: "˧"
  type: other
  name: "mid tone"
  features: {}
```

The loader translates `true` to `Value("+")`, `false` to
`Value("-")`, and absence to no entry in `Segment.values`.

### 1.5 Characteristics

The optional `characteristics` list holds short tags classifying
the phone. These become `Segment.classification` values, keyed by
whatever classifier the consumer chooses.

`phonfeat` does not enforce a fixed vocabulary of characteristic
tags, but the built-in files use the abbreviations defined in the
`definitions` sheet of the source ODS. Consumers who want
validation can supply a `ValueSet` per classifier at
`SegmentInventory` construction time.

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
   (U+0361, `t͡ʃ`) over the ligature (U+02A8). Prefer tie bars
   over sequences without tie bars when the combination is a
   recognized affricate.

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

- **Structural:** required keys present; types match; no unknown
  keys at the top level.
- **Referential:** every feature value keys a declared feature;
  every characteristic keys a declared tag (if a vocabulary is
  supplied); every `canonical` in a symbol table matches an `ipa`
  in the loaded feature system.
- **Uniqueness:** feature names, phone `ipa` values, symbol table
  entries.
- **Canonicalization:** every phone's `ipa` field is already in
  canonical form; a violation is an error, not silently fixed.

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
version is **1.0**, corresponding to `phonfeat` 0.1.x. A file may
declare the schema version it was written against:

```yaml
schema_version: "1.0"
```

If present, `phonfeat` rejects files declaring a future version.
If absent, the loader assumes the current version.
```
