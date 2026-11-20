# phonfeat

IPA and X-SAMPA tokenization, conversion, and distinctive feature
analysis for Python.

`phonfeat` is the notation-specific layer on top of
[`lingcore`](https://github.com/<your-user>/lingcore). It provides:

- **Tokenization** of IPA and X-SAMPA strings into phones.
- **Conversion** between IPA and X-SAMPA.
- **Inventory extraction** from corpora.
- **Feature attachment** from PanPhon-style and Hayes-style tables.
- **Inventories** — segments, categories, features and a tokenizer
  bound into one object.
- **Minimal distinguishing feature set** computation.

## Install

```
pip install phonfeat
```

Optional extras:

- `phonfeat[ods]` — to regenerate the bundled data from the source
  ODS spreadsheet.
- `phonfeat[pandas]` — for `FeatureMatrix.to_dataframe()`.
- `phonfeat[dev]` — to run the test suite.

## Quick example

```python
import phonfeat

# Tokenize an IPA string.
segments = phonfeat.tokenize("pat͡ʃka", notation="ipa")
for seg in segments:
    print(seg.symbol, seg.type)

# Convert to X-SAMPA.
xsampa = phonfeat.ipa_to_xsampa("pat͡ʃka")
print(xsampa)

# Extract an inventory from a corpus.
corpus = ["pat͡ʃka", "kut͡ʃa", "mat͡ʃ"]
inventory = phonfeat.inventory_from_corpus(corpus, notation="ipa")

# Attach PanPhon-style features.
system = phonfeat.load_feature_system("panphon")
annotated = phonfeat.attach_features(inventory, system)

# Compute a minimal distinguishing feature set.
minimal = phonfeat.minimal_feature_set(annotated, system)
print(minimal.feature_names)
```

## An inventory

`Inventory` binds what a study needs: segments, optional categories,
the numeric feature matrix, and the tokenizer used to read forms.

```python
import phonfeat

model = phonfeat.load_feature_model("hayes")
inventory = phonfeat.Inventory.from_feature_model(model, notation="ipa")

inventory.describe()      # segments, types, undefined cells per feature
inventory.tokenize("ka")  # lingcore.Segment objects, typed from the model
```

`group_by_type=True` turns each segment type into a category, which is
how an inventory says that classes should be treated differently.

## Documentation

- [`docs/index.md`](docs/index.md) — entry point to all documentation.
- [`docs/summary.md`](docs/summary.md) — what the package is and
  where it is going.
- [`docs/concepts.md`](docs/concepts.md) — the mental model.
- [`docs/tutorial.md`](docs/tutorial.md) — a worked example on
  messy data.
- [`docs/api.md`](docs/api.md) — the public surface.
- [`docs/data_format_spec.md`](docs/data_format_spec.md) — the on-disk
  data format.
- [`docs/design.md`](docs/design.md) — why the package is shaped this
  way.
- [`docs/decisions.md`](docs/decisions.md) — the dated decision log and
  open questions.

> The quick example above shows the intended surface, not the current
> one. Implemented so far: `canonicalize_ipa`, `canonicalize_xsampa`,
> `tokenize`, `Profile` and `load_profile`, `survey`, `Inventory`, the
> data loaders, and the exception types. Not yet implemented:
> `ipa_to_xsampa`, `xsampa_to_ipa`, `inventory_from_corpus`,
> `attach_features`, `minimal_feature_set`.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
