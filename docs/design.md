# Design notes

Why `phonfeat` looks the way it does. Read this if you are
considering using `phonfeat`, extending it, or contributing to it.

For the specific decisions (with dates and rationale) that shaped
the current state, see [`decisions.md`](decisions.md). This file
covers the underlying reasoning at a level of detail that doesn't
fit in a dated log.

---

## What `phonfeat` is

`phonfeat` provides four capabilities, in the order they build on
each other:

1. **Canonicalization.** Given a string in IPA or X-SAMPA,
   produce its canonical form. Canonical forms are the input to
   everything else.
2. **Tokenization.** Split a string into individual phones, each
   a `lingcore.Segment`. Handles maximal munch, diacritic
   stacking, and the ambiguities of both notations.
3. **Conversion.** Translate between IPA and X-SAMPA, via
   canonicalization and a symbol table.
4. **Analysis.** Load a feature system, attach features to an
   inventory, and compute a minimal distinguishing feature set.

Each layer depends on the previous one. The ordering is not
arbitrary: it's the order in which the pieces actually need to
exist.

## Why `phonfeat` and not just `lingcore`

`lingcore` provides the abstract structures — `Segment`,
`FeatureSystem`, `SegmentInventory`, `FeatureMatrix`. It
deliberately has no knowledge of IPA, X-SAMPA, or any specific
notation. That's the right design for a reusable core, but it
means `lingcore` can't answer the questions a user actually
has: "what are the phones in this IPA string?" or "what's the
minimal feature set for this inventory?"

`phonfeat` answers those questions. It sits on top of `lingcore`
and adds the notation-specific knowledge that `lingcore` refuses
to carry. The one-way dependency is important: `lingcore` doesn't
know `phonfeat` exists, so any project that uses `phonfeat` gets
`lingcore` for free, and any project that uses only `lingcore`
(without wanting IPA support) doesn't pay for it.

## Why canonicalization comes first

Every downstream operation — tokenization, conversion, feature
lookup — assumes that the phone string is in canonical form.
Without canonicalization:

- Two spellings of the same phone (`g` and `ɡ`, `t͡ʃ` and `ʧ`)
  wouldn't match.
- Diacritics in different orders (`qˤː` and `qːˤ`) would be
  distinct strings, even though they denote the same phone.
- The tokenizer would need to handle every variant separately,
  multiplying the symbol table entries.

Canonicalization is the operation that ensures "one phone, one
string". It's applied in two places:

1. **When the ODS→YAML script runs**, so the data files only
   contain canonical forms.
2. **When the loader reads a user-supplied file**, to reject
   non-canonical forms.

The second is a deliberate choice: the loader doesn't auto-fix
non-canonical input. Silently correcting `g` to `ɡ` would hide a
bug in the user's data; rejecting it forces them to regenerate
with the script, which is the correct workflow.

## Why the canonicalization tables are data

Three tables drive canonicalization:

- `deprecations.yaml`: replacements for deprecated or variant
  glyphs (`g` → `ɡ`, `ʧ` → `t͡ʃ`).
- `diacritic_order.yaml`: the order in which combining diacritics
  should appear.
- `canonicalize.py`: the logic that applies the tables.

The tables are hand-curated, versioned, and loaded at runtime.
They're not hardcoded in Python. There are two reasons:

**Linguistic.** There's no single correct canonical form.
Different traditions prefer different orderings; different
communities have different deprecation policies. Making the
tables data lets users override without editing code.

**Practical.** The tables will change. New IPA symbols get added;
old ones get deprecated; a user working on a specific language
might need to accommodate a specific notation. A data file is
easier to update than a Python module.

## Why diacritic reordering is tricky

Diacritic reordering is the hardest part of canonicalization, and
it's worth understanding why.

In Unicode, diacritics fall into two classes:

1. **Combining marks** (Unicode combining class > 0). These
   attach to the preceding character. `U+0325` (combining ring
   below) is an example: `a\u0325` displays as `ḁ`.
2. **Modifier letters** (Unicode general category `Lm`). These
   are separate characters that don't combine, but act as
   diacritics. `U+02D0` (modifier letter triangular colon) is an
   example: `aː` uses it for length.

The reorderer needs to handle both, and in the right way for
each:

- **Modifier letters** reorder among themselves, but never move
  past their base character.
- **Combining marks** reorder among themselves, and stay
  attached to their base.
- **Tie bars** (`U+0361`, `U+035C`) are combining marks, but
  they're *between* two base characters, not attached to one.

The implementation in `canonicalize._reorder_diacritics` splits
a phone into tie-bar-separated segments, then reorders modifiers
within each segment. This handles all three cases correctly, at
the cost of some complexity.

An earlier implementation tried a simpler approach — sort
combining marks by rank, keep base characters where they were —
and it produced `tʃ͡` instead of `t͡ʃ`. The tie bar ended up at the
end because it was treated as a combining mark on the second base
character. The current implementation splits at tie bars first,
which prevents this.

## Why the loader is strict

Three kinds of "strict":

**Strict about canonical form.** Non-canonical `ipa` fields are
rejected, not fixed. See above.

**Strict about the schema.** Missing required keys are rejected. Wrong
types are rejected. Unknown *keys within an entry* (a phone, a feature,
a symbol) are currently ignored rather than rejected; unknown
top-level keys are also ignored. The specification calls for both to
be rejected, so this is an open gap between `data_format_spec.md` and
`storage.py`, recorded in §5 of that file rather than papered over.

**Strict about the schema version.** A file declaring
`schema_version: "1.0"` when `CURRENT_SCHEMA_VERSION` is `"1.1"`
is rejected, with a message pointing to `scripts/ods_to_yaml.py`.

This strictness has a cost: users with hand-edited files will
encounter errors that a lenient loader would have silently
accepted. But it also has a benefit: users discover their
mistakes at the moment they make them, rather than later when a
feature lookup returns `None` for a phone they thought they'd
correctly entered.

The design principle is: *a loader should refuse to load data it
doesn't understand*. Lenient loaders accumulate silent
incompatibilities; strict loaders force the incompatibility to
the surface.

## Why `phonfeat` ships two feature systems

The ODS source has two feature tables:

- `ipa_all_panphon` (~5700 phones, 24 features, three-valued).
- `ipa_hayes` (~140 phones, 28 features, mostly binary).

They're different enough that merging them would be wrong (see
`decisions.md` D4). But they're not two *alternatives* to the same
problem — they serve different use cases:

- **PanPhon** has broad coverage. If a user has an inventory
  containing a rare phone (a click, a pharyngealized affricate, a
  tone), PanPhon likely has a feature vector for it. But PanPhon
  is not *distinctive*: many phones have identical feature
  vectors, because PanPhon's feature set doesn't distinguish every
  phonetic contrast.
- **Hayes** is distinctive, but has narrow coverage. If a user's
  inventory is within Hayes' scope, the feature vectors are clean
  and every phone is distinguished from every other. But Hayes
  doesn't have features for, say, `q͡χˤː`.

The right choice depends on the user's task:

- **"What are the features of `q͡χˤː`?"** → PanPhon.
- **"What's the minimal feature set for my Spanish inventory?"**
  → Hayes (or PanPhon if Hayes doesn't cover it).

Making this explicit — two systems, not one merged — lets users
choose. A future `phonfeat.merge_feature_systems` might produce a
merged system for users who want both coverage and distinctiveness,
but that's deferred.

## Why `classification_tags` lives in metadata

`lingcore.Segment.classification` is a mapping from classifier name
to a single value. That's the right model for many kinds of
classification: a vowel is "close" *or* "open", not both; a
consonant is "bilabial" *or* "alveolar", not both.

But some classifications are naturally multi-valued. A phone like
`s` is *both* a sibilant and a fricative, and both are manner
properties. `ʃ` is *both* a sibilant and a fricative. `l` is
*both* a lateral and an approximant. Modeling these as a single
manner value would force us to drop one.

`lingcore` doesn't support multi-valued classifiers (see
`decisions.md` D19). We considered changing it and
rejected the change as too semantically loaded for a single
consumer's need. Instead, `phonfeat` stores the full tag list in
`Segment.metadata["classification_tags"]`, where metadata is
free-form and unhashable-friendly.

The consequence is that `Segment.classification` is always empty
in `phonfeat`. Users who want structured classification should
call `FeatureModel.classifications(symbol)`, which groups tags by
classifier using the abbreviation map.

## Why the two `classifier` maps are duplicated

`scripts/ods_to_yaml.py` and `src/phonfeat/storage.py` both have a
mapping from classifier abbreviation (`vls`, `blb`, `stp`) to
classifier name (`voicing`, `place`, `manner`). The maps are
identical.

This duplication is ugly. It exists because `scripts/` is not
shipped in the wheel, and `storage.py` can't import from a
directory that might not exist in a user's installation.

The alternatives are worse:

- Move the map into `src/phonfeat/data/` as a YAML file. Both
  script and loader import it. This adds a data file for a map
  that isn't user-editable and never changes.
- Ship `scripts/` in the wheel. This pulls `pandas` and `odfpy`
  into every installation.
- Have the loader read the map from `definitions` at runtime.
  This requires the user's data file to include the definitions
  sheet content, which it doesn't.

The current compromise — duplicate the map, accept that it can
drift — is defensible because the drift is *visible*:
`FeatureModel.classifications(symbol)` groups unmapped tags under
`"_unmapped"`, which a user will notice the moment they look at
the result. That's a better signal than silence.

## Why the ODS→YAML pipeline is a script

The ODS file is the source of truth for the feature data. It's
edited by hand, in LibreOffice (or whatever spreadsheet tool),
because that's what the source data looks like — grid sheets,
definitions, ad-hoc notes in cells.

The script that converts ODS to YAML is one-time development
tooling, not part of the shipped package. It lives in
`scripts/ods_to_yaml.py` and requires `phonfeat[ods,pandas]` to
run.

This separation matters for two reasons:

**For users.** Users who `pip install phonfeat` never touch the
ODS. They get the YAML. They never need `pandas` or `odfpy`.

**For maintainers.** The ODS can change without releasing a new
version of `phonfeat`, as long as the YAML is regenerated and
committed. The YAML is the interface; the ODS is the source.

## Why diagnostics are honest, not fixed

The ODS→YAML script produces a diagnostics directory containing:

- `panphon_duplicates.yaml`: canonicalization collisions with
  disagreeing features (currently empty — every collision has
  agreeing features).
- `panphon_undistinguished.yaml`: groups of phones with identical
  feature vectors (~1135 groups).
- `panphon_all_undefined.yaml`: phones whose features are all
  undefined (1 phone: the mid tone).

The script *reports* these; it doesn't *fix* them. That's a
choice.

**Undistinguished groups** are a real property of PanPhon. `q`,
`q̟`, and `q̠` are three phones with identical PanPhon feature
vectors, because PanPhon doesn't distinguish advanced/retracted
among uvulars. Adding features to fix this is a research
project, not a script. Reporting the groups tells the user where
the feature system's limits are.

**Duplicates** with disagreeing features would be a data bug. The
script reports them as errors (aborts the run), not as warnings.

**All-undefined phones** are the honest encoding of PanPhon's
mid tone: `˧` is `[0, 0]` for `hitone`/`hireg`, meaning both
features are inapplicable. The feature matrix will have `NaN` for
that phone's row. That's correct, and the diagnostic tells the
user it's expected.

## What's not designed yet

Three things have decisions recorded but no implementation.

**Tokenization.** The strategy is settled: maximal munch against
the symbol table, tie-bar-aware, diacritic-aware. The
implementation isn't written. See `decisions.md` Q4 for the
unresolved question about symbol-table collisions.

**Conversion.** Built atop tokenization. Uses the symbol table to
map each token to its canonical form in the target notation. Not
written.

**Feature attachment and the solver.** `attach_features` will
look up each segment in the `FeatureModel` and build a new
`SegmentInventory` with the values attached. The solver is
described in the original design doc: greedy set-cover, then
redundancy elimination. Both are deferred until tokenization and
conversion exist, because they can't be tested without an
inventory to work on.

## The guiding principle

When in doubt, `phonfeat` prefers:

- **Strict over lenient.** Reject bad data; don't fix it silently.
- **Explicit over implicit.** Two feature systems, not one merged;
  a `.yaml` file's schema version is checked, not assumed.
- **Reported over fixed.** Undistinguished groups are
  diagnostics, not bugs to patch around.
- **Data over code.** The canonicalization tables, the classifier
  map, the symbol tables, and the feature tables are all data.
  The code applies them.

These aren't arbitrary. They're responses to specific failure
modes we encountered during development, and they're the reason
the code looks the way it does.
