# Tutorial

A worked example. By the end you will have taken a wordlist that does
not tokenize, found out why, described its conventions in a profile,
checked the reading against a feature table, and built an inventory.

The forms used here are the kind real data contains: a precomposed
`ñ`, a combining caron, a tone written as `_H`, and a nasalized vowel.

## 1. Install

```
pip install phonfeat
```

`lingcore` is installed with it.

## 2. Tokenize a string

```python
from phonfeat import tokenize

for segment in tokenize("pat͡ʃka"):
    print(repr(segment.symbol), segment.type)
```

```
'p' other
'a' other
't͡ʃ' other
'k' other
'a' other
```

Five segments, not six: the affricate is one phone, because the symbol
table lists `t͡ʃ` as one symbol and matching prefers the longest.

Two things to notice. Every segment is `"other"`, because without a
feature model the tokenizer does not know what a vowel is. And each
segment is a `lingcore.Segment`, not a string.

Diacritics and prosody behave differently, which is the next thing to
know:

```python
tuple(segment.symbol for segment in tokenize("ˈkʰaːta"))
# ('ˈ', 'kʰ', 'aː', 't', 'a')
```

The stress mark is its own segment. The aspirated `k` and the long `a`
are single segments, each carrying its modifier.

## 3. Give the segments types

```python
from phonfeat import load_feature_model, tokenize

hayes = load_feature_model("hayes")
for segment in tokenize("pat͡ʃka", model=hayes):
    print(segment.symbol, segment.type)
```

```
p consonant
a vowel
t͡ʃ consonant
k consonant
a vowel
```

`hayes` loads in about a tenth of a second. `panphon` is larger and
more detailed but takes a few seconds and a couple of hundred
megabytes on first use. Nothing loads unless you ask for it.

## 4. Find out why a corpus will not tokenize

```python
from phonfeat import survey

forms = ["ñak", "čata", "t͡ʃa", "di_H", "di_Hkata_H", "kãta"]
print(survey(forms).render())
```

```
survey: ipa
  tokenized 3 / 6 forms (50.0%), 9 tokens
  blockers (2):
    '_' U+005F  2 forms   e.g. 'di_H', 'di_Hkata_H'
    '̌' U+030C  1 form   e.g. 'čata'
  characters the ipa table cannot consume: 'H'(2), '_'(2), '̌'(1)
    → declare them in a profile's substitutions to read them
  inventory: 6 distinct segments
    a(3), k(2), t(1), t͡ʃ(1), ã(1), ñ(1)
```

Half the forms fail, and the report says why. Read it rather than
patching it:

- `_` at `U+005F` is the beginning of a tone spelling. Nothing is
  wrong with it, but the IPA table has no such symbol.
- `̌` at `U+030C` is a combining caron on its own, which means `č` was
  typed as `c` plus a combining mark rather than as a single
  character. That is a composition problem, not an unknown phone.

And then the part that matters most: **`ñ` is not in the blocker
list.** It tokenizes fine, as one segment, because decomposed it is an
`n` with a tilde — which is a real IPA phone, just not the one the
corpus means. A corpus can tokenize and still be read wrongly, which
is why step 6 exists.

## 5. Describe what the corpus assumes

Say what you know, instead of letting the package guess:

```python
from phonfeat import Profile, survey

profile = Profile(
    notation="ipa",
    substitutions={"ñ": "ɲ", "č": "t͡ʃ", "_H": "˥"},
    description="Field notes, pre-2010 transcription.",
)
print(survey(forms, profile=profile).render())
```

```
survey: ipa · profile: 3 substitution(s)
  tokenized 6 / 6 forms (100.0%), 24 tokens
  blockers: none
  inventory: 9 distinct segments
    a(7), k(3), t(3), ˥(3), d(2), i(2), t͡ʃ(2), ã(1), ɲ(1)
```

Substitutions are applied before matching, longest key first, so `_H`
is rewritten as a unit and never mistaken for a lone `_`. The
description is recorded and echoed, because a profile is a claim about
the data and claims should be attributable.

A profile can also **split** one string into several forms — a cell
holding `"agua, agua"` is two forms, not one — and **strip** characters
that carry no phonetic content, such as a hyphen marking a morpheme
boundary. Both are declared the same way, and the same file can be
reused for every batch from that source.

## 6. Check the reading against a feature table

Tokenizing is not the same as being read correctly. Survey again, now
with a feature model:

```python
print(survey(forms, profile=profile, model=hayes).render())
```

```
  feature coverage:
    described   20 tokens (83.3%)
    base-only   1 tokens (4.2%)
    undescribed 3 tokens (12.5%)
    base-only: ã(1)
    missing: ˥(3)
    types: consonant 46%, vowel 42%, other 12%
```

Three numbers, three different meanings:

- **described** — the segment has a row in the feature table. Nothing
  more to do.
- **base-only** — the marked form has no row, but its base does. `ã`
  is read as `a` plus a nasal diacritic, and the table describes `a`
  but not `ã`. This is where misreadings and diacritics both land: it
  is a question to answer, not an error to fix.
- **undescribed** — no row at all. `˥` is a tone, and the Hayes table
  has no tone segments. Any distance computed for it would be a
  guess, so `lingaligner` will refuse rather than invent one.

A large `base-only` share means the corpus is being read under a
convention you have not declared. A large `undescribed` share means
the feature table does not cover the inventory, which is a different
problem with a different fix.

## 7. Build an inventory

```python
from phonfeat import Inventory, load_feature_model

inventory = Inventory.from_feature_model(hayes, notation="ipa")
print(inventory.render())
```

```
segments    140 (vowel 26, consonant 104, other 10)
categories  none
notation    ipa
features    28 columns, 678 undefined cells
  undefined tense 113, anterior 84, distributed 84
```

The inventory is what a consumer holds: segments, features, categories
and a tokenizer. `group_by_type=True` turns each segment type into a
category, which is how an inventory says that vowel features do not
apply to consonants.

Look at the undefined counts. A feature that is undefined for most
segments is either class-specific or a mistake, and the count is what
tells them apart — `tense` at 113 is class-specific, a stray value on
one phone would not be.

## 8. What next

The inventory is where `phonfeat` stops. Comparing segments, aligning
forms and computing distances between languages belongs to
[`lingaligner`](https://github.com/<your-user>/lingaligner), which
takes this object directly.

Before using your own corpus at scale:

- Write the profile to a file and load it with `load_profile`, so the
  reading is reviewable by whoever knows the language, and reuse it.
- Run `survey` before every batch. Two numbers deserve attention:
  `base-only`, which means an undeclared convention, and `undescribed`,
  which means a feature table that does not cover the inventory.
