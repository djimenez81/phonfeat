# phonfeat

IPA and X-SAMPA tokenization, conversion, and distinctive feature
analysis for Python.

`phonfeat` is the notation-specific layer on top of
[`lingcore`](https://github.com/<your-user>/lingcore). It provides:

- **Tokenization** of IPA and X-SAMPA strings into phones.
- **Conversion** between IPA and X-SAMPA.
- **Inventory extraction** from corpora.
- **Feature attachment** from PanPhon-style and Hayes-style tables.
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

## Documentation

- [`docs/summary.md`](docs/summary.md) — what this project is and
  where it is going.
- [`docs/data_format_spec.md`](docs/data_format_spec.md) — the on-disk
  data format.
- [`docs/tutorial.md`](docs/tutorial.md) — a worked example.
- [`docs/api.md`](docs/api.md) — reference.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
