# Concepts

This document explains the mental model behind phonfeat's API. Read it
before the tutorial if you are new; read it after if you prefer to
learn by example.

## Two notations, one set of phones

The same phone can be written in more than one way. IPA writes the
voiced velar nasal `ŋ`; X-SAMPA writes `N`. Neither is more correct,
and a corpus may mix conventions without meaning to — two transcribers
on the same project will.

phonfeat holds a **symbol table** per notation: a YAML file mapping
every spelling it accepts to a canonical form.

```
notation   ipa | xsampa
symbols    {spelling: canonical}
```

The table does two jobs. It is the alphabet the tokenizer matches
against, and it is the dictionary that says which spellings mean the
same thing. A table is data: adding a notation, or accepting one more
spelling, is an edit to YAML.

**Canonicalization** is the step before matching. It applies Unicode
normalization and a table of deprecated spellings — the ligature `ʧ`
becomes `t͡ʃ`, so a corpus typed before Unicode 6 still tokenizes. Note
that canonicalization is *within* a notation: `canonicalize_xsampa`
normalizes X-SAMPA spellings and does not translate them into IPA.

## Segments

A segment is a phone: the smallest unit the model handles. `phonfeat`
returns [`lingcore.Segment`](https://github.com/<your-user>/lingcore)
objects, not strings, because a segment carries more than its symbol.

- `symbol` — the canonical spelling, in the notation being read.
- `type` — `"vowel"`, `"consonant"`, `"other"`, or whatever a feature
  model declares. Without a model, everything is `"other"`.

Segments from the tokenizer have empty `classification` and `values`:
tokenizing is about splitting a string, not about describing what the
pieces mean. Attaching descriptions is a separate step.

## Tokenizing

Matching is **maximal munch**: at each position the longest symbol in
the table wins, ties broken by codepoint order so the result is
deterministic. This is what makes `t͡ʃ` one segment rather than three.

Two rules follow from how transcription works:

- **Diacritics stack onto the preceding phone.** A combining mark or a
  tone letter modifies the phone before it, so `kʰ` is one segment
  whose symbol is `kʰ`, not a `k` followed by an aspiration mark.
- **Prosody stands alone.** Stress marks and tone bars are segments of
  type `"other"`. `ˈmata` is four segments, the first of them a stress
  mark.

Matching runs on **decomposed** text (NFD), so a base and its
combining mark are matched separately and then stacked; the assembled
symbol is composed back to NFC. This matters: composing first would
turn `a` + `◌̃` into the precomposed `ã`, which is not a row of any
symbol table, and every nasalized vowel in the corpus would be
rejected.

Two consequences worth knowing:

- An input with no segments at all — an empty string — tokenizes to an
  empty tuple, not an error.
- A character the table does not know is an error, and the error names
  the offset and the code point. Silently dropping it would make a
  typo look like a missing phone.

## Reading a corpus: profiles

A corpus is rarely written in textbook notation. A wordlist of
Austronesian cognates may use a practical orthography in which `c` is
`t͡ʃ` and `y` is `j`; a Chibchan questionnaire may write tone as `_H`.
Both tokenize cleanly as IPA, and both yield a plausible, wrong
inventory. This is the central difficulty phonfeat exists to address.

A **`Profile`** is the caller's statement about their own strings:

| Field | Meaning |
|---|---|
| `notation` | `"ipa"` or `"xsampa"` |
| `substitutions` | textual rewrites, longest key first |
| `split` | a regex separating independent forms in one string |
| `strip_chars` | characters removed after splitting |
| `description` | free text, echoed in reports |

The order of operations is fixed and documented: substitutions over
the whole string, then split, then strip. A profile is data, so it can
be reviewed by the person who knows the language, and reused for every
file from the same source.

A profile does not make the package assume anything. It records what
the caller decided.

## Surveying: what the data requires

`survey(forms)` tokenizes everything it can and reports what it could
not, without raising:

- how many forms there were, how many tokenized, how many did not;
- **blockers** — the characters that stopped tokenization, ranked, each
  with a few verbatim examples;
- **unmatched** — every character the table cannot consume;
- the **inventory** that came out, with frequencies;
- **feature coverage**, split three ways: described, base-only (the
  marked form is absent but its base is present), and undescribed;
- the **type distribution** of the segments found.

The point of the report is that it answers a question the package
cannot: *does this corpus mean what I think it means?* A clean
tokenization rate is not evidence of a correct reading. The three-way
coverage split is there because base-only is where misreadings hide —
a precomposed `ñ` reads as `n` plus a tilde, and lands there.

## Feature models

A **feature model** is a `lingcore.FeatureSystem` bundled with the
phones it describes:

- the ordered features, which define the columns;
- one `Segment` per phone, carrying values keyed by feature name.

phonfeat ships two: `panphon` (5730 phones, 24 features, a few
seconds and a couple of hundred megabytes on first load) and `hayes`
(140 phones, 28 features, about a tenth of a second). Both are
generated from their published sources by a script, and both are
data.

Both bundled tables are strictly binary: their values are
`Value("+")` and `Value("-")`, nothing else. A phone that has no
value for a feature simply carries no entry for it, and that absence
is what becomes `NaN` in a numeric matrix. This is why the undefined
counts matter: `tense` is undefined for a hundred-odd phones in the
Hayes table not because "not applicable" was recorded, but because
the table does not describe it for them.

## Inventories

An **`Inventory`** is the object a consumer actually holds: the
segments of one study, with their features, their categories and the
tokenizer that reads their notation.

```
Inventory
  segments     the phones this study recognises
  features     a numeric matrix, or None
  categories   {name: symbols}, empty if the inventory is undivided
  notation     how forms are written
  profile      how the strings of the corpus are read
  model        the feature model it came from
```

Categories are the inventory's way of saying that classes differ. An
inventory that declares none makes no claim, and a distance computed
over it treats every feature as applying to every segment. An
inventory that declares `{"vowel": ..., "consonant": ...}` claims that
vowel features do not apply to consonants, and a distance is then
entitled to charge a fixed cost across the boundary instead of
comparing feature by feature.

`group_by_type=True` builds those categories from the feature model's
own segment types. It is off by default: the default should claim the
least.

Encoding feature values is deliberately tolerant. `+` is 1.0, `-` is
0.0, and anything else — a missing value, a `0`, a third state such as
`±` — is `NaN`. `lingcore`'s encoder raises instead, which is right
for the bundled tables, where an unexpected token is a bug, and wrong
for a table assembled from somebody's spreadsheet, where one odd cell
should not abort the build. `describe()` counts undefined cells per
feature, so the odd cell is visible as a number rather than as an
exception.

## Where the boundary is

phonfeat ends where comparison begins.

- It does not decide whether two segments are similar.
- It does not decide whether two forms are cognate.
- It does not read files.

Those belong to `lingaligner` and to the study that drives it. Keeping
the boundary there is what allows a corpus shape nobody has thought of
yet — cognate sets, wordlists, a single speaker's field notes — to be
handled by the layer above without changing this one.
