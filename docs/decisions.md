# Design decisions

A running log of choices made during the development of `phonfeat`.
Entries are appended in chronological order. Old decisions are not
edited when they become obsolete; instead, a new entry supersedes
them and references the old one.

For the `lingcore` decisions that `phonfeat` depends on, see
`lingcore/docs/decisions.md`. This file records decisions specific
to `phonfeat` itself.

---

## 2026-10-15 (before code was written)

### D1. Function-first public API

**Decision.** `phonfeat`'s public API is function-first:
`phonfeat.tokenize(...)`, `phonfeat.ipa_to_xsampa(...)`,
`phonfeat.inventory_from_corpus(...)`,
`phonfeat.minimal_feature_set(...)`. Internally these use
`lingcore` classes.

**Rationale.** Functions are simpler to learn and match what most
users want from a library. The class-based machinery lives
underneath; users don't need to construct `FeatureSystem` or
`SegmentInventory` by hand unless they want fine control.

### D2. ODS→YAML pipeline is a script, not a module

**Decision.** The converter lives in `scripts/ods_to_yaml.py`, is
not shipped in the wheel, and requires the optional
`phonfeat[ods,pandas]` extra.

**Rationale.** The ODS is development data, not user data. The
YAML is the interface to the code. Users never run the script.
Keeping it out of the wheel means users don't pull in `odfpy` and
`pandas` for something they'll never do.

### D3. ODS lives in `data/` at repo root; generated YAML in `src/phonfeat/data/`

**Decision.** The ODS source of truth is `data/data.ods` in the
repo root. The generated YAML lives in `src/phonfeat/data/` inside
the package, so it ships with the wheel.

**Rationale.** Two different audiences: the ODS is for maintainers
who need to inspect or edit the source data; the YAML is what the
runtime loads. Separating them makes it obvious which is which.

### D4. PanPhon and Hayes feature systems are kept separate

**Decision.** `phonfeat` ships two feature systems, `panphon` and
`hayes`, as separate YAML files. They are not merged.

**Rationale.** They differ in coverage (~5700 vs 140 phones),
feature inventory (24 vs 28 features), and distinctiveness
(PanPhon is not distinctive; Hayes is). Merging them creates one
of two bad outcomes: lose PanPhon's coverage, or invent features
Hayes never had. A future `phonfeat.merge_feature_systems` can
produce a merged system on demand, with a bridge table supplying
feature-name correspondences. That bridge doesn't exist yet.

### D5. Canonicalization is data-driven

**Decision.** The `deprecations.yaml` and `diacritic_order.yaml`
files drive IPA and X-SAMPA canonicalization. Neither the rules
nor the order is hardcoded in Python.

**Rationale.** Linguists disagree about canonical order,
deprecated glyphs, and dialectal variants. Making these data lets
users adjust without editing code.

### D6. Canonicalization is strict, not lenient

**Decision.** The loader rejects files whose `ipa` fields are not
already in canonical form. Canonicalization is the producer's job
(the script), not the consumer's (the loader).

**Rationale.** Silent auto-correction hides bugs. If a producer's
output is non-canonical, that's a bug in the producer, and it
should fail loudly.

### D7. Characteristics are inherited from base symbols

**Decision.** A phone not directly present in the grid sheets
inherits characteristics from its longest matching prefix, plus
extra tags for recognized diacritics.

**Rationale.** The grid sheets only contain base symbols. A phone
like `tˤ` isn't in `consonants_ipa` directly, but it's clearly
`t` + pharyngealization. Inheriting gives it useful
characteristics without requiring the producer to spell out every
variant.

### D8. Undistinguished phones are reported, not fixed

**Decision.** The ODS→YAML script reports groups of phones whose
feature vectors are identical. It does not attempt to add features
or drop phones.

**Rationale.** Fixing PanPhon's gaps is a research project, not a
script. Reporting the gaps tells the user where the feature system
is insufficient, which is what they want to know.

### D9. Corrupt data is a bug, not a warning

**Decision.** If two source rows canonicalize to the same phone
with different feature vectors, the script reports this as a
*disagreement*. Zero disagreements is the expected healthy state.

**Rationale.** Disagreements indicate either a bug in the source
data or a bug in the extractor. Either way, they need
investigation.

---

## 2026-10-20 (first working pipeline)

### D10. Data files use `schema_version`

**Decision.** Every generated data file declares
`schema_version: "1.1"`. The loader rejects files declaring any
version other than the current one.

**Rationale.** A schema change (like the `characteristics` →
`classification_tags` rename) needs a way to distinguish old and
new files. Strict rejection means a stale file fails loudly
instead of silently losing fields. See D18 for the version that
superseded this.

### D11. `FeatureModel` bundles a `FeatureSystem` and its phones

**Decision.** `load_feature_model(...)` returns a `FeatureModel`,
which has `.system` (a `lingcore.FeatureSystem`) and `.phones`
(a mapping from canonical symbol to `lingcore.Segment`).

**Rationale.** `lingcore.FeatureSystem` is the *schema*, not the
data. The phones live in the YAML but aren't part of
`FeatureSystem`. Bundling them in one object makes the loader's
return value carry everything a consumer needs. `FeatureModel` is
the "loaded form" of a feature-system file.

### D12. `load_feature_model` caches builtins, not paths

**Decision.** `load_feature_model("panphon")` and
`load_feature_model("hayes")` are cached with `@lru_cache`. A
`Path` argument bypasses the cache.

**Rationale.** Builtins are immutable within a session. Path-based
loads might point at files that change, so caching them would be
wrong. The cache is unbounded because there are only a handful of
builtins.

### D13. `load_feature_model` accepts name or path

**Decision.** `load_feature_model("panphon")` loads the bundled
file. `load_feature_model(Path("custom.yaml"))` or
`load_feature_model("path/to/file.yaml")` loads that file. A
string that is neither a builtin name nor a plausible path raises
`DataFormatError` reporting the unknown builtin.

**Rationale.** Users should be able to point at their own YAML
without copying it into the package. A string like
`"panphonn"` (typo) should say "unknown builtin" rather than
trying to open it as a file and failing with "file not found".

### D14. `SymbolTable` is a `notation` and a `symbols` mapping

**Decision.** `load_symbol_table("ipa")` returns a
`SymbolTable` with `.notation` (a string) and `.symbols` (a
mapping from notation-specific string to canonical phone).

**Rationale.** The tokenizer needs exactly this: given a notation,
look up strings and get canonicals. A flat mapping is the simplest
representation.

### D15. Two-pass validation: structural, then referential

**Decision.** The loader checks:

1. **Structural:** required keys present, types correct, no
   unknown keys at the top level.
2. **Referential:** every feature value keys a declared feature,
   every `ipa` field is canonical, every `type` is in `{consonant,
   vowel, other}`.

**Rationale.** The two kinds of errors are different. Structural
problems mean the file is malformed. Referential problems mean
the file is well-formed but describes something inconsistent. The
loader reports both clearly, but the two-pass model keeps the
error messages focused.

### D16. Compound grid tags split into components

**Decision.** A grid cell header like `"sib frc"` splits into
`["sib", "frc"]` — two tags, both manner.

**Rationale.** The definitions sheet only defines single-token
abbreviations. Compound headers were producing
"no classifier" warnings for every phone with a compound tag
(`s`, `z`, `ʃ`, `ʒ`, `l`, `t͡s`, `t͡ʃ`, `ɬ`, `ɮ`, `w`, `ɥ`, `ʍ`,
and dozens more). Splitting them makes each component map to its
classifier, and it's semantically correct: `s` really is both
sibilant and fricative.

---

## 2026-10-29 (classification refactor)

### D17. `characteristics` becomes `classification_tags`

**Decision.** The YAML field `characteristics` (a list of compound
phrases like `sib frc`) is replaced by `classification_tags` (a
list of single abbreviations like `sib`, `frc`). The change is
paired with D16.

**Rationale.** The field was previously renamed as a small change;
this is the entry that actually specifies what changed. See D18
for how the schema version handles the transition.

### D18. Schema version bumped from 1.0 to 1.1

**Decision.** The data-format schema version is now `1.1`.
`CURRENT_SCHEMA_VERSION = "1.1"` in `storage.py`. Files
declaring a different version (present or future) are rejected
with a helpful message.

**Rationale.** D17 is a breaking change. Users with files written
against 1.0 will get "schema_version: got '1.0', expected
'1.1'. Regenerate the file with scripts/ods_to_yaml.py", which
tells them exactly what to do. Silent acceptance of 1.0 files
would mean missing the classification field entirely, which is
worse.

### D19. `Segment.classification` stays empty; tags go in metadata

**Decision.** `lingcore.Segment.classification` is a
`Mapping[str, Value]` — one value per classifier. In `phonfeat`,
we leave `classification` empty and store tags in
`Segment.metadata["classification_tags"]`.

**Rationale.** A phone can have multiple tags under the same
classifier (`s` is both `sib` and `frc`, both manner). `lingcore`
models `classification` as single-valued, which would force us to
pick one and drop the other. Metadata is free-form and
unhashable-friendly; it's the right home for tags that don't fit
the "one value per classifier" model. We considered changing
`lingcore` to support tuple-valued classifiers and rejected it:
the change is semantically loaded, and `phonfeat` is the only
consumer that would benefit.

### D20. `FeatureModel.classification_tags()` and `.classifications()`

**Decision.** `FeatureModel` exposes:

- `classification_tags(symbol) -> tuple[str, ...]` — the tags,
  in source order.
- `classifications(symbol) -> dict[str, tuple[str, ...]]` — the
  tags grouped by classifier, using the classifier mapping from
  the `definitions` sheet.

**Rationale.** The first accessor is the raw data; the second is
the convenience for users who want structured classification. The
grouping is done at call time, not stored, so it doesn't bloat
the YAML.

### D21. `_CLASSIFIER_BY_ABBREVIATION` is duplicated between script and loader

**Decision.** `scripts/ods_to_yaml.py` and `src/phonfeat/storage.py`
both have a mapping from abbreviation to classifier. The maps are
not shared (scripts aren't shipped in the wheel).

**Rationale.** The duplication is a real cost. The alternative is
moving the map into `phonfeat.data` (so both script and loader can
import it) or shipping `scripts/` in the wheel (so `storage.py`
could import from it). Either fix adds a dependency we don't want
right now. The duplication is visible: if the maps drift,
`classifications()` will group unmapped tags under `"_unmapped"`,
which is an obvious signal.

---

## 2026-11-02 (documentation audit at handover)

### D22. Documentation corrected against the tree after handover

**Decision.** The handover document's factual claims were audited
against the code, and the documentation in this repository was
corrected where it disagreed with the tree. No decision recorded in
this log was reversed; only factual claims were fixed.

**Corrections.** D4's feature count for Hayes is 28, not 30 (the
generated `hayes.feature.yaml` has 28 features across 140 phones).
`design.md` now cites D19 of *this* file for the multi-valued
classifier decision, not `lingcore`'s D19 (which is about `value_sets`
validation). `design.md` no longer claims that unknown keys are
rejected — they are ignored — and `data_format_spec.md` §2.1, §4.1,
§5 now distinguish what is specified from what `storage.py` enforces,
with the gaps listed in a new §5.1. `canonicalize.py`'s module
docstring no longer lists "tie bar normalization" as a separate step:
ligature affricates reach the tie-barred form through
`deprecations.yaml`.

**Rationale.** A specification that describes behavior the loader does
not have is worse than no specification, because it makes a passing
test look like proof of compliance. The gaps are recorded rather than
closed because closing them changes behavior and needs its own tests.

---

## 2026-11-02 (tokenizer)

### D23. The tokenizer stacks diacritics and types segments from a model

**Decision.** `phonfeat.tokenize(text, notation, *, model=None)`
returns a tuple of `lingcore.Segment`, one per phone.

- Matching is maximal munch over the notation's symbol table, sorted
  by descending symbol length and then by symbol, so ties are
  deterministic. This is what makes `t͡ʃ` and `tS` come out whole.
- Modifiers — single characters that are combining marks or modifier
  letters (Unicode category `Lm`) — attach to the phone they follow
  and become part of its `symbol`. `kʰ` is one segment. This resolves
  Q5.
- The stress marks (`ˈ ˌ`, and `" %` in X-SAMPA) are exempt and come
  out as their own segments, because they precede the syllable they
  apply to.
- Tone bars (`˥˦˧˨˩`) also stay separate. They are category `Sk`, so
  the modifier test excludes them, but the reason is that PanPhon
  models tone as its own segment: no PanPhon phone carries a
  combining tone mark, so folding a tone bar into a vowel would
  produce a symbol the feature data cannot describe. This is the
  practical half of Q4.
- Types come from an optional `FeatureModel`. Without one, every
  segment is typed `"other"`. A modified phone takes its *base's*
  type, because a diacritic does not change whether a phone is a
  consonant or a vowel.

**Rationale.** Stacking was chosen because it is the only reading the
shipped data supports (Q5). Types are not resolved by default because
PanPhon takes ~4 s to load the first time and adds ~200 MB of resident
memory; making that an implicit cost of calling a tokenizer would
violate the project's preference for explicit behavior.
`model="hayes"` costs ~0.1 s where it covers the inventory.

**Known limitation, recorded rather than fixed.** The symbol tables
carry no types, and the feature models do not cover every symbol.
Of the 173 IPA symbol-table canonicals, 124 are in PanPhon and 99 in
Hayes; 8 real entries (`ɚ ɝ ʜ ʡ ʢ ɠ̥ ŋ͡m .`) are in neither, and the
remaining 41 are diacritics, which under D23 never become segments of
their own. The two systems also disagree on the type of 4 of their
134 shared phones: `ɦ`, `h` (consonant in PanPhon, other in Hayes) and
`ʔ`, `ɻ` (the reverse). `Segment.type` is therefore system-relative
at the margins, which is a further reason to keep it out of the
symbol tables until it is needed there.

### D24. `canonicalize_ipa` is a single-phone operation

**Decision.** `canonicalize_ipa` is documented, and now relied upon,
as operating on one phone. A new function,
`canonicalize.normalize_for_matching(text, notation)`, applies only
the boundary-preserving steps — NFC and deprecation replacement — to
an arbitrary string. The tokenizer calls it before matching, then
canonicalizes each token once it is known to be a single phone.

**Rationale.** The diacritic-reordering step treats everything after
the first character of a tie-bar-separated chunk as a modifier, so on
a multi-phone string it moves marks across phone boundaries:
`canonicalize_ipa("baːd")` returns `"bːad"`, and `"qaˤː"` returns
`"qˤːa"`. Nothing in the package relied on the multi-phone behavior —
the loader passes one `ipa` field at a time — but a tokenizer that
canonicalized its whole input would have been silently wrong for
every word longer than one phone. The behavior is now pinned by
`test_diacritics_do_not_move_across_phone_boundaries`.

Whether `canonicalize_ipa` should *reject* multi-phone input, rather
than merely being documented as single-phone, is left open: it would
need a way to recognize a phone boundary before reordering, which is
what the tokenizer is for.

---

## Deferred / open questions

These are decisions we discussed but did not resolve. They should
be revisited before the corresponding code is written.

### Q1. Should `characteristics` (pre-rename) have stored multi-valued classifiers?

**Status.** Resolved in the negative. D19 records the outcome: use
`metadata["classification_tags"]` instead. Recorded here because
the discussion was substantive and someone reading only the
decisions log might not know we considered the alternative.

### Q2. Should `phonfeat` merge `panphon` and `hayes`?

**Status.** Deferred. D4 says they're kept separate. A merge
function might appear later, using a bridge table that doesn't
exist yet. Not on the critical path.

### Q3. What to do about the 1135 undistinguished groups?

**Status.** Deferred. Some are intrinsic to PanPhon (no features
distinguish `q̟` from `q`). Others might be fixable by adding
features to a custom `panphon` variant. Either way, it's a
research project, not a code change. The diagnostics file
(`diagnostics/panphon_undistinguished.yaml`) is the record.

### Q4. What to do about the `_B`/`_L`/`_M`/`_H`/`_T` symbol-table collisions?

**Status.** Resolved by D23, in the practical sense. The collision is
typographic, not semantic: a combining tone diacritic (e.g. `U+030F`)
and a tone letter (e.g. `U+02E9`) denote the same tone level, and
X-SAMPA has one spelling for both. Tokenization therefore attaches
`_X` to the preceding base and uses the combining form; the lossiness
lands in `convert.py`, where `IPA → X-SAMPA → IPA` is stable but
`X-SAMPA → IPA → X-SAMPA` is not. Distinguishing the two readings
with features would be a different feature system — future work, not
a tokenizer task.

### Q5. Should the tokenizer handle diacritic stacking?

**Status.** Resolved by D23: stacked. Diacritics become part of the
segment's `symbol`; they are not promoted to `values`. PanPhon models
tone as its own segment and has no phone carrying a combining tone
mark, so stacking is the only reading consistent with the shipped
data.

### Q6. Should `phonfeat` include a `Phoneme` concept?

**Status.** Deferred, per the original design doc. `lingcore` has
no `Phoneme`; `phonfeat` doesn't either. Allophony is a
research-grade feature; we don't model it yet.

---

## Implementation decisions (continued)

### D24. Matching happens on decomposed text

**Context.** The IPA symbol table lists bases (`a`) and combining
marks (`U+0303`) as separate entries, because D23 stacks a diacritic
onto the phone it follows. `normalize_for_matching` was normalizing
IPA to NFC, which *composes* `a` + `U+0303` into the single character
`ã` — a string that is no symbol in the table. The tokenizer
therefore rejected every combining-mark phone, in either spelling:
`ã`, `a` + `U+0303`, `é` and `e` + acute all raised
`TokenizationError`. Nothing caught it because X-SAMPA writes
nasalization and tone as ASCII (`a~`, `a_H`), so the test corpus
never exercised the IPA path, and because composed and decomposed
input fail identically — there is no error to notice, only a refusal.

**Decision.** `normalize_for_matching` decomposes IPA to NFD instead
of composing it. Bases and marks then match separately and stack as
designed; `canonicalize_ipa` composes each assembled token back to
NFC, so the `symbol` on the resulting segment is still composed.
Composed and decomposed input now produce identical segments, which
is what "two spellings of the same phone" is supposed to mean.

**Consequences.** Matching text and segment symbols are in different
normalization forms; that is intentional and documented at both ends.
Deprecation rules are unaffected, because all of them are keyed on
non-combining characters.

### D25. A corpus is a list of strings; a profile is the user's, not ours

**Context.** Two real corpora arrived as examples of a *class* of
file the packages will meet, not as canonical inputs: a list of
Austronesian cognate sets in practical orthography, and an incomplete
Chibchan Swadesh table in X-SAMPA. Encoding either file's layout
inside the package would have made its accidents into the project's
ontology. But the corpora also showed that a clean tokenization rate
is not a correct reading: every character of a practical orthography
is a valid IPA symbol, so `y`, `c`, `j` and `ñ` tokenize without
complaint and yield a plausible, wrong inventory.

**Decision.**

1. **phonfeat reads strings, not files.** `tokenize`, `survey`,
   `convert` and `inventory` take `Iterable[str]`. Extracting strings
   from a spreadsheet or a Python literal is the caller's job. The
   package therefore knows nothing about `Hoja1`, column headers, or
   one-list-per-line layout, and cannot misrepresent a future file.
2. **No corpus type.** Not in `phonfeat`, and not in `lingcore` yet.
   `lingcore` has no data-loading concept at all and its classes earn
   their place by having invariants worth enforcing; a corpus has
   none beyond "a form is a sequence of segments", which is
   `tuple[Segment, ...]`. The grouping that *is* linguistic —
   cognate set, translation row — is deferred to the third package,
   which knows what a cognate set must support. A second real
   consumer is what would promote it into `lingcore`.
3. **The package does not guess the notation.** `survey()` reports
   measurable facts — blockers ranked with examples, characters the
   symbol table cannot consume, the inventory with frequencies,
   feature coverage split into described / base-only / undescribed,
   the type distribution — and stops there. Deciding that `c` means
   `t͡ʃ` in an Austronesian wordlist requires knowing the family; a
   package that inferred it would be wrong exactly where it mattered.
4. **The conclusion is recorded in a profile.** A `Profile` is a
   user-authored YAML document declaring notation, textual
   substitutions, a split pattern and characters to strip. It is
   validated strictly (unknown keys are errors, unlike the bundled
   data loader, because a hand-written typo is a mistake rather than
   a forward-compatibility case). `phonfeat` ships the schema and
   the validator, and **no corpus profiles**; the two worked
   examples live under `examples/profiles/` and are labelled as
   readings, not facts.

**Consequences.** The procedure for turning an unknown file into an
inventory is now: survey it as-is, read the blockers and the
base-only list, write a profile, survey again, compare. The two real
corpora are regression fixtures (`tests/fixtures/`) rather than
shipped data. Swadesh's 23.8% undescribed share turned out to be a
conversion gap, not a data gap, which is why `convert.py` precedes
`inventory.py` in the plan. A precomposed `ñ` is read as n + tilde
after D24 and shows up under base-only rather than as a blocker; that
is the survey working, not failing.

### D26. An `Inventory` binds the pieces; it does not compute

**Context.** Consumers need one object that answers "what does this
study consider a sound, and what is known about each one?" The parts
existed scattered across the package: a symbol table, a feature model,
a profile, a tokenizer. Assembling them was left to the caller, and
every caller assembled them differently.

**Decision.** `phonfeat.Inventory` holds segments, an optional feature
matrix, optional categories, the notation, an optional profile and the
model it came from, and it tokenizes. It holds no distances and knows
no corpora. Two ways in: the plain constructor, and
`from_feature_model(model, group_by_type=...)`.

Feature values are encoded `+ -> 1.0`, `- -> 0.0`, everything else
`NaN`. This differs from `lingcore`'s encoder, which raises on a value
it does not know: the strict encoder is right for the bundled data
files, where an unexpected token is a bug, and wrong for an inventory
assembled from somebody's spreadsheet, where a third state such as `±`
has to become undefined rather than abort the build. The cost is that
a typo becomes a `NaN` instead of an exception; `describe()` counts
undefined cells per feature so the typo is visible as a number.

`group_by_type` is off by default. An inventory that declares
categories makes a claim about which features apply to which class, and
the distance is entitled to act on that claim; an inventory that
declares none makes no claim. Defaulting to none keeps the package from
asserting a partition on the caller's behalf.

**Consequences.** `Inventory` is what `lingaligner` receives through
its `InventoryLike` protocol, so the two packages meet at a contract
rather than at a class. `inventory_from_corpus` — deriving the segment
set from the data — is still absent, and now has an obvious home.

## Note on `design.md`

`phonfeat/docs/design.md` (if it exists) covers the *why* from a
reader-oriented perspective. This file covers the *what and when*
from a maintainer-oriented perspective. The two overlap; neither
replaces the other. If they drift, `decisions.md` is the record of
what was actually decided; `design.md` is the explanation.
