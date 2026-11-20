# phonfeat documentation

- [Project summary](summary.md) — what phonfeat is, its status, and
  its roadmap.
- [Concepts](concepts.md) — the mental model behind the API.
- [Tutorial](tutorial.md) — a worked example, from a messy wordlist to
  an inventory.
- [API reference](api.md) — the public classes and functions.
- [Design notes](design.md) — why things are the way they are.
- [Data format](data_format_spec.md) — the on-disk format of the
  symbol and feature tables.
- [Decisions](decisions.md) — the dated decision log, including the
  questions still open.

If you are new to phonfeat, read the summary first, then the
concepts, then the tutorial. The API reference is for lookup, not for
learning.

Two sections are worth reading before using the package on real data:
the part of **Concepts** on profiles, and the part on feature
coverage in `survey`. They contain the package's central difficulty --
that a corpus can tokenize perfectly and still be read wrongly.
