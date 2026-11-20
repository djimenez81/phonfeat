# API reference

Every public class and function exported by phonfeat.

Functions that raise take their exceptions from `phonfeat.errors`: the
family is rooted at `PhonfeatError`, so one `except` clause catches
all of it.

## `canonicalize_ipa(text)`

**Purpose.** Normalize an IPA string's spelling without changing what
it denotes.

**Signature.**

```python
canonicalize_ipa(text: str) -> str
```

**Notes.** Applies Unicode normalization and the deprecated-spelling
table: `ʧ` becomes `t͡ʃ`, `ɱ` variants collapse, and so on. Single
phone only. For a string of several phones use `tokenize`, which does
its own normalization; the separate helper exists because it is
useful on its own.

Raises `TypeError` if `text` is not a string.

---

## `canonicalize_xsampa(text)`

**Purpose.** The same for X-SAMPA: normalize spelling *within* the
notation. It does not translate X-SAMPA into IPA.

**Signature.**

```python
canonicalize_xsampa(text: str) -> str
```

---

## `tokenize(text, notation="ipa", *, model=None)`

**Purpose.** Split a written form into segments.

**Signature.**

```python
tokenize(
    text: str,
    notation: str = "ipa",
    *,
    model: str | FeatureModel | None = None,
) -> tuple[Segment, ...]
```

**Parameters.**

| Name | Type | Description |
|---|---|---|
| `text` | `str` | The form, in `notation`. |
| `notation` | `str` | `"ipa"` or `"xsampa"`. |
| `model` | `str` or `FeatureModel` | Used to type the segments. A built-in name (`"panphon"`, `"hayes"`) or a loaded model. |

**Returns.** One `lingcore.Segment` per phone, in order. `symbol` is
the canonical spelling *in the notation being read*, `type` comes from
the model or is `"other"`. `classification` and `values` are empty:
tokenizing splits, it does not describe.

**Raises.** `TokenizationError` if part of the string matches no
symbol; the message carries the offset and the code point.
`NotationError` for an unknown notation.

**Notes.** Matching is maximal munch, longest symbol first, ties by
codepoint. Diacritics and tone letters stack onto the preceding phone;
stress marks and tone bars are separate segments of type `"other"`.
Matching runs on decomposed text (NFD) and composes each assembled
token back to NFC, which is what lets `a` + a combining tilde be
recognised as one segment.

---

## `Profile`

**Purpose.** How to read the strings of one corpus.

**Signature.**

```python
Profile(
    notation: str = "ipa",
    substitutions: Mapping[str, str] = {},
    split: str | None = None,
    strip_chars: str = "",
    description: str = "",
)
```

**Fields.**

| Field | Description |
|---|---|
| `notation` | `"ipa"` or `"xsampa"`. |
| `substitutions` | Textual rewrites applied before matching, longest key first. Keys and values must be non-empty and must differ. |
| `split` | Regex separating independent forms inside one string. `None` keeps each string whole. |
| `strip_chars` | Characters removed from each form after splitting. |
| `description` | Free text, echoed in reports. |

**Methods.**

- `expand(text) -> tuple[str, ...]` — substitutions over the whole
  string, then split, then strip. This is the order used everywhere.
- `rewrite(text) -> str` — substitutions and strip only, no split.
- `to_mapping() -> dict` — a plain dict, for writing the profile back
  out.

**Notes.** Frozen; the substitution mapping is a read-only view. The
order of operations is fixed so that a profile and the tokenizer
cannot disagree about what a form is.

---

## `load_profile(path)`

**Purpose.** Read a profile from a YAML file.

**Signature.**

```python
load_profile(path: str | Path) -> Profile
```

**Raises.** `DataFormatError` if the document is not a mapping, if a
key is unknown, or if a field has the wrong type.

---

## `survey(forms, notation=None, *, profile=None, model=None, examples=3)`

**Purpose.** Report what a set of forms requires before it can be
tokenized.

**Signature.**

```python
survey(
    forms: Iterable[str],
    notation: str | None = None,
    *,
    profile: Profile | None = None,
    model: str | FeatureModel | None = None,
    examples: int = 3,
) -> SurveyReport
```

**Parameters.**

| Name | Type | Description |
|---|---|---|
| `forms` | iterable of `str` | The corpus, as strings. |
| `notation` | `str` or `None` | Overrides the profile's notation; `None` means use the profile's, or `"ipa"`. |
| `profile` | `Profile` | How to read the strings. |
| `model` | `str` or `FeatureModel` | Enables the feature-coverage sections. |
| `examples` | `int` | How many verbatim examples to keep per blocker. |

**Returns.** A `SurveyReport`. It never raises on a bad form: a form
that cannot be tokenized is counted and its first offending character
recorded.

---

## `SurveyReport`

**Purpose.** The result of `survey`.

**Fields.**

| Field | Type | Description |
|---|---|---|
| `notation` | `str` | The notation used. |
| `source_forms` | `int` | Entries received. |
| `forms` | `int` | Forms after the profile's splits. |
| `tokenized` | `int` | Forms that produced at least one segment. |
| `tokens` | `int` | Segments produced in total. |
| `blockers` | `tuple[Blocker, ...]` | Ranked, most frequent first. |
| `segments` | `Mapping[str, int]` | Segment symbol to frequency. |
| `unmatched` | `Mapping[str, int]` | Every character the table cannot consume. |
| `described` | `Mapping[str, int]` or `None` | Segments with a feature row, and how many match exactly. |
| `base_only` | `Mapping[str, int]` or `None` | Segments whose marked form is absent but whose base is present. |
| `undescribed` | `Mapping[str, int]` or `None` | Segments with no feature row at all. |
| `types` | `Mapping[str, int]` or `None` | Segment type to count. |
| `profile` | `Profile` or `None` | The profile used, for the record. |

**Properties and methods.**

- `failed -> int` — forms that did not tokenize.
- `coverage -> float` — tokenized forms over total forms.
- `render() -> str` — a readable report, including the top blockers
  with examples, the ranked inventory, and the three-way feature
  coverage.

**Notes.** `described`, `base_only` and `undescribed` are `None` when
no model was given. They are the part of the report that answers
"is this corpus being read the way its author intended?" rather than
"does it parse?".

---

## `Blocker`

**Purpose.** One character that stopped tokenization, and how often.

**Fields.**

| Field | Type | Description |
|---|---|---|
| `char` | `str` | The character that matched no symbol. |
| `count` | `int` | Forms in which it was the first such character. |
| `examples` | `tuple[str, ...]` | Up to `examples` forms containing it, verbatim. |

**Properties.** `codepoint` — the code point, e.g. `"U+00F1"`, which
is what tells an ordinary letter from a lookalike.

---

## `Inventory`

**Purpose.** The segments of one study, with their features,
categories and tokenizer.

**Signature.**

```python
Inventory(
    segments: Sequence[Segment | str] = (),
    features: FeatureMatrix | None = None,
    categories: Mapping[str, Sequence[str]] = {},
    notation: str = "ipa",
    profile: Profile | None = None,
    model: FeatureModel | None = None,
)
```

**Fields.**

| Field | Description |
|---|---|
| `segments` | The phones. A bare string becomes a segment typed `"other"`. Defaults to the model's phones. |
| `features` | Segment-by-feature matrix; built from `model` when omitted. |
| `categories` | `{category_name: symbols}`; empty means one undivided inventory. |
| `notation` | How forms are written. |
| `profile` | How to read a corpus's strings. |
| `model` | The feature model it came from. |

**Methods.**

- `tokenize(text) -> tuple[Segment, ...]` — applies the profile, if
  any, then tokenizes.
- `describe() -> dict` — segment count, type counts, categories,
  feature count, and undefined cells in total and per feature.
- `render() -> str` — the same, as text.

**Class methods.**

- `from_feature_model(model, *, notation="ipa", profile=None,
  group_by_type=False) -> Inventory` — build from a feature model,
  optionally turning each segment type into a category.

**Properties.** `symbols` — the symbols, in inventory order.

**Raises.** `DataFormatError` on duplicate symbols, on a category
naming a symbol the inventory does not hold, on a symbol in two
categories, or on a feature matrix whose rows do not match the
segments.

**Notes.** Immutable. Feature values are encoded `+` to 1.0, `-` to
0.0, and anything else to `NaN` — including `0` and third states. This
is more tolerant than `lingcore`'s encoder on purpose; `describe()`
makes the tolerance visible.

---

## `load_feature_model(name_or_path)`

**Purpose.** Load a feature model, built-in or from a file.

**Signature.**

```python
load_feature_model(name_or_path: str | Path) -> FeatureModel
```

**Parameters.** A built-in name (`"panphon"`, `"hayes"`) or a path to
a YAML document in the format of `data_format_spec.md`.

**Notes.** Built-ins are cached after the first load. PanPhon takes a
few seconds and a couple of hundred megabytes; Hayes takes about a
tenth of a second. Nothing loads implicitly: a caller who wants no
data loading never pays for it.

---

## `load_symbol_table(notation_or_path)`

**Purpose.** Load a symbol table, built-in or from a file.

**Signature.**

```python
load_symbol_table(notation_or_path: str | Path) -> SymbolTable
```

---

## `SymbolTable`

**Purpose.** A notation's alphabet: spelling to canonical form.

**Fields.** `notation` (str), `symbols` (`Mapping[str, str]`),
`description` (str).

**Methods.** `canonical_for(symbol) -> str`, raising `KeyError` for an
unknown spelling. Also supports `len()` and `in`.

---

## `FeatureModel`

**Purpose.** A feature system bundled with the phones it describes.

**Fields.** `system` (`lingcore.FeatureSystem`) and `phones`
(`Mapping[str, Segment]`).

**Methods.** `symbols() -> tuple[str, ...]` (sorted);
`classification_tags(symbol)` and `classifications(symbol)`, which read
the per-phone classification the tables carry. Also supports
`len()`, `in`, iteration and `model[symbol]`.

---

## Exceptions

| Exception | Raised when |
|---|---|
| `PhonfeatError` | Base class; catching it catches everything below. |
| `NotationError` | The notation is unknown, or not applicable. |
| `TokenizationError` | Part of a string matches no symbol. Carries the offset and code point. |
| `DataFormatError` | A data file or profile violates its format. |
| `UnknownSegmentError` | A symbol has no entry in the symbol or feature table. |
