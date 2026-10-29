# Design decisions

A running log of choices made during the development of `phonfeat`.
Entries are appended; old decisions are not edited when they become
obsolete — instead, a new entry supersedes them.

Format: date, decision, rationale. If a decision is later reversed,
add a new entry that references the old one.

---

## 2026-10-15 (before `phonfeat` code began)

### D1. Separate `lingcore` package for abstract structures

**Decision.** `phonfeat` depends on `lingcore`; it does not duplicate
`Segment`, `FeatureSystem`, `Inventory`, etc.

**Rationale.** The abstractions are reusable across linguistic
projects (sign language, conlangs, future packages). Keeping them
separate forces `lingcore` to be notation-agnostic and lets
`phonfeat` focus on notation-specific work.

### D2. Function-first public API

**Decision.** `phonfeat.tokenize(...)`, `phonfeat.ipa_to_xsampa(...)`,
`phonfeat.inventory_from_corpus(...)`, `phonfeat.minimal_feature_set(...)`.

**Rationale.** Functions are simpler to learn, simpler to test, and
match what most users want from a library. Internally we still use
`lingcore` classes; the function API is a thin layer over them.

### D3. ODS→YAML pipeline is a script, not a module

**Decision.** The converter lives in `scripts/ods_to_yaml.py`, is
not part of the shipped wheel, and requires the optional
`phonfeat[ods,pandas]` extra to run.

**Rationale.** The ODS is development data, not user data. The YAML
is the interface to the code. Users never need to run the script.

### D4. PanPhon and Hayes feature systems kept separate

**Decision.** `phonfeat` ships two feature systems, `panphon` and
`hayes`, as separate YAML files. They are not merged.

**Rationale.** They differ in coverage (~5700 vs 140 phones),
feature inventory (24 vs 30 features), and distinctiveness (PanPhon
is not distinctive; Hayes is). Merging them creates one of two bad
outcomes: lose PanPhon's coverage, or invent features Hayes never
had. A future `phonfeat.merge_feature_systems` can produce a merged
system on demand, with the bridge table supplying feature-name
correspondences.

### D5. Canonical forms are data-driven

**Decision.** The `deprecations.yaml` and `diacritic_order.yaml`
files drive IPA and X-SAMPA canonicalization. Neither the rules nor
the order is hardcoded in Python.

**Rationale.** Linguists disagree about canonical order, deprecated
glyphs, and dialectal variants. Making these data lets users adjust
without editing code.

### D6. Canonicalization is strict, not lenient

**Decision.** The loader rejects files whose `ipa` fields are not
already in canonical form. Canonicalization is the producer's job
(the script), not the consumer's (the loader).

**Rationale.** Silent auto-correction hides bugs. If a producer's
output is non-canonical, that's a bug in the producer, and it should
fail loudly.

### D7. Characteristics are inherited from base symbols

**Decision.** A phone not directly present in the grid sheets
inherits characteristics from its longest matching prefix, plus
extra tags for recognized diacritics.

**Rationale.** The grid sheets only contain base symbols. A phone
like `tˤ` is not in `consonants_ipa` directly, but it's clearly
`t` + pharyngealization. Inheriting gives it useful characteristics
without requiring the producer to spell out every variant.

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
data or a bug in the extractor. Either way, they need investigation.

### D10. `Segment.metadata` is for annotations, not structure

**Decision.** Metadata is excluded from equality and hashing on
`lingcore.Segment`. It holds application-specific annotations
(source citations, external IDs, notes), not structural data.

**Rationale.** Keeping metadata out of identity means two segments
that differ only in metadata are the same segment. Structural data
belongs in typed fields, not metadata.
