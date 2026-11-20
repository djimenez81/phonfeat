"""Loading phonfeat data files into lingcore objects.

This module reads the YAML files under ``phonfeat/data`` (or a
user-supplied path) and produces the objects the rest of phonfeat
operates on:

- :class:`FeatureModel` bundles a :class:`lingcore.FeatureSystem`
  with the phones it describes.
- :class:`SymbolTable` maps notation-specific strings to canonical
  forms, for the tokenizer.

The on-disk format is specified in ``docs/data_format_spec.md``. The
loader validates the file against that spec and raises
:class:`phonfeat.errors.DataFormatError` on any violation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files as _resource_files
from pathlib import Path
from typing import Any, Mapping

import yaml

from lingcore import (
    Feature,
    FeatureKind,
    FeatureSystem,
    Segment,
    Value,
)

from .canonicalize import canonicalize_ipa, canonicalize_xsampa
from .errors import DataFormatError

__all__ = [
    "BUILTIN_FEATURE_SYSTEMS",
    "BUILTIN_SYMBOL_TABLES",
    "CURRENT_SCHEMA_VERSION",
    "FeatureModel",
    "SymbolTable",
    "load_feature_model",
    "load_symbol_table",
]


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------


#: The schema version this loader accepts.
CURRENT_SCHEMA_VERSION = "1.1"

#: Names of the feature systems bundled with phonfeat.
BUILTIN_FEATURE_SYSTEMS: tuple[str, ...] = ("panphon", "hayes")

#: Names of the symbol tables bundled with phonfeat.
BUILTIN_SYMBOL_TABLES: tuple[str, ...] = ("ipa", "xsampa")

_VALID_TYPES: frozenset[str] = frozenset(
    {"consonant", "vowel", "other"}
)

# Classifier names for every abbreviation used in the
# ``definitions`` sheet of the source ODS. This duplicates the
# mapping in scripts/ods_to_yaml.py because scripts are not
# shipped in the wheel. If the two drift, ``classifications()``
# will group unmapped tags under ``"_unmapped"``, a visible sign.
_CLASSIFIER_BY_ABBREVIATION: dict[str, str] = {
    # Manner of Articulation
    "nas": "manner",
    "stp": "manner",
    "afr": "manner",
    "sib": "manner",
    "frc": "manner",
    "flp": "manner",
    "trl": "manner",
    "apr": "manner",
    "clk": "manner",
    "ejc": "manner",
    "imp": "manner",
    "vwl": "manner",
    "lat": "manner",
    # Place of Articulation
    "blb": "place",
    "lbd": "place",
    "bld": "place",
    "dnt": "place",
    "alv": "place",
    "pla": "place",
    "rfx": "place",
    "alp": "place",
    "pal": "place",
    "vel": "place",
    "lbv": "place",
    "uvl": "place",
    "phr": "place",
    "glt": "place",
    # Voice
    "vls": "voicing",
    "vcd": "voicing",
    # Diacritic
    "lgl": "diacritic",
    "idt": "diacritic",
    "apc": "diacritic",
    "lmn": "diacritic",
    # Phonation
    "brv": "phonation",
    "slv": "phonation",
    "stv": "phonation",
    "crv": "phonation",
    "glc": "phonation",
    # Rounding and Labialization
    "ptr": "rounding",
    "cmp": "rounding",
    "mrd": "rounding",
    "lrd": "rounding",
    # Syllabicity
    "syl": "syllabicity",
    "nsy": "syllabicity",
    # Consonant Release
    "asp": "release",
    "nrs": "release",
    "lrs": "release",
    "unx": "release",
    # Coarticulation
    "pzd": "coarticulation",
    "vzd": "coarticulation",
    "fzd": "coarticulation",
    "nzd": "coarticulation",
    "rzd": "coarticulation",
    # Tongue Root
    "atr": "tongue_root",
    "rtr": "tongue_root",
    # Length
    "est": "length",
    "hlg": "length",
    "lng": "length",
    "elg": "length",
    # Height
    "hgh": "height",
    "smh": "height",
    "umd": "height",
    "mid": "height",
    "lmd": "height",
    "sml": "height",
    "low": "height",
    # Backness
    "fnt": "backness",
    "cnt": "backness",
    "bck": "backness",
    # Roundness
    "unr": "roundness",
    "rnd": "roundness",
}


# ---------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolTable:
    """A notation-specific symbol table for the tokenizer.

    Parameters
    ----------
    notation : str
        The notation this table is for, e.g. ``"ipa"``.
    symbols : Mapping of str to str
        Mapping from notation-specific string to canonical phone
        symbol.
    description : str, optional
        Human-readable description. Defaults to ``""``.
    """

    notation: str
    symbols: Mapping[str, str]
    description: str = ""

    def canonical_for(self, symbol: str) -> str:
        """Return the canonical phone for ``symbol``.

        Raises
        ------
        KeyError
            If ``symbol`` is not in the table.
        """
        return self.symbols[symbol]

    def __len__(self) -> int:
        return len(self.symbols)

    def __contains__(self, symbol: object) -> bool:
        if not isinstance(symbol, str):
            return False
        return symbol in self.symbols


@dataclass(frozen=True)
class FeatureModel:
    """A feature system bundled with the phones it describes.

    Parameters
    ----------
    system : lingcore.FeatureSystem
        The feature system (schema).
    phones : Mapping of str to lingcore.Segment
        Mapping from canonical phone symbol to Segment.

    Notes
    -----
    Constructed via :func:`load_feature_model`, not directly.
    """

    system: FeatureSystem
    phones: Mapping[str, Segment]

    def __getitem__(self, symbol: str) -> Segment:
        return self.phones[symbol]

    def __contains__(self, symbol: object) -> bool:
        if not isinstance(symbol, str):
            return False
        return symbol in self.phones

    def __len__(self) -> int:
        return len(self.phones)

    def __iter__(self):
        return iter(self.phones)

    def symbols(self) -> tuple[str, ...]:
        """Return phone symbols, sorted for determinism."""
        return tuple(sorted(self.phones))

    def classification_tags(
        self, symbol: str
    ) -> tuple[str, ...]:
        """Return the classification tags for a phone.

        Parameters
        ----------
        symbol : str
            Canonical phone symbol.

        Returns
        -------
        tuple of str
            The tags, in the order they appear in the YAML file.
            Empty if the phone has none.

        Raises
        ------
        KeyError
            If ``symbol`` is not in the model.
        """
        segment = self.phones[symbol]
        return tuple(
            segment.metadata.get("classification_tags", ())
        )

    def classifications(
        self, symbol: str
    ) -> dict[str, tuple[str, ...]]:
        """Return the phone's classification tags grouped by
        classifier.

        Tags are grouped using the abbreviation-to-classifier
        mapping that the ODS→YAML script uses. Tags not present in
        that mapping are grouped under ``"_unmapped"``.

        Parameters
        ----------
        symbol : str
            Canonical phone symbol.

        Returns
        -------
        dict of str to tuple of str
            Mapping from classifier name to a (possibly empty)
            tuple of tags.

        Raises
        ------
        KeyError
            If ``symbol`` is not in the model.
        """
        tags = self.classification_tags(symbol)
        groups: dict[str, list[str]] = defaultdict(list)
        for tag in tags:
            classifier = _CLASSIFIER_BY_ABBREVIATION.get(
                tag, "_unmapped"
            )
            groups[classifier].append(tag)
        return {k: tuple(v) for k, v in groups.items()}


# ---------------------------------------------------------------------
# Low-level reading and validation
# ---------------------------------------------------------------------


def _read_yaml(path: Path) -> object:
    """Read a YAML file, raising ``DataFormatError`` on failure."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError as exc:
        raise DataFormatError(f"File not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise DataFormatError(
            f"Malformed YAML in {path}: {exc}"
        ) from exc


def _require_mapping(
    obj: object, context: str
) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise DataFormatError(
            f"{context}: expected a mapping, got "
            f"{type(obj).__name__}"
        )
    return obj


def _require_list(
    obj: object, context: str
) -> list[Any]:
    if not isinstance(obj, list):
        raise DataFormatError(
            f"{context}: expected a list, got "
            f"{type(obj).__name__}"
        )
    return obj


def _require_str(
    obj: object, context: str
) -> str:
    if not isinstance(obj, str):
        raise DataFormatError(
            f"{context}: expected a string, got "
            f"{type(obj).__name__}"
        )
    return obj


def _require_key(
    mapping: Mapping[str, Any], key: str, context: str
) -> Any:
    if key not in mapping:
        raise DataFormatError(
            f"{context}: missing required key {key!r}"
        )
    return mapping[key]


def _check_schema_version(
    root: Mapping[str, Any], context: str
) -> None:
    """Reject files declaring a non-current schema version.

    Parameters
    ----------
    root : Mapping
        The parsed YAML top-level mapping.
    context : str
        A description of the file, for error messages.

    Raises
    ------
    DataFormatError
        If ``schema_version`` is present and does not match
        :data:`CURRENT_SCHEMA_VERSION` exactly.
    """
    if "schema_version" not in root:
        return
    raw = root["schema_version"]
    if not isinstance(raw, str):
        raise DataFormatError(
            f"{context}:schema_version: expected string"
        )
    if raw != CURRENT_SCHEMA_VERSION:
        raise DataFormatError(
            f"{context}:schema_version: got {raw!r}, expected "
            f"{CURRENT_SCHEMA_VERSION!r}. Regenerate the file "
            f"with scripts/ods_to_yaml.py."
        )


# ---------------------------------------------------------------------
# Feature system loading
# ---------------------------------------------------------------------


def _path_for_builtin(name: str) -> Path:
    """Return the path to a bundled data file."""
    if name in BUILTIN_FEATURE_SYSTEMS:
        filename = f"{name}.feature.yaml"
    elif name in BUILTIN_SYMBOL_TABLES:
        filename = f"{name}.symbols.yaml"
    else:
        raise DataFormatError(
            f"Unknown builtin: {name!r}. Known: "
            f"{BUILTIN_FEATURE_SYSTEMS + BUILTIN_SYMBOL_TABLES}"
        )
    return Path(str(_resource_files("phonfeat") / "data" / filename))


def _parse_feature(
    entry: object, context: str
) -> Feature:
    """Parse one entry of the ``features`` list."""
    mapping = _require_mapping(entry, context)
    name = _require_str(
        _require_key(mapping, "name", context),
        f"{context}.name",
    )
    kind_raw = mapping.get("kind", "binary")
    if kind_raw not in ("binary", "multi", "scalar"):
        raise DataFormatError(
            f"{context}.kind: unknown kind {kind_raw!r}"
        )
    kind = FeatureKind(kind_raw)
    description = mapping.get("description", "")
    if not isinstance(description, str):
        raise DataFormatError(
            f"{context}.description: expected string"
        )
    aliases_raw = mapping.get("aliases", [])
    if isinstance(aliases_raw, str):
        aliases: tuple[str, ...] = (aliases_raw,)
    elif isinstance(aliases_raw, list):
        aliases = tuple(
            _require_str(a, f"{context}.aliases[{i}]")
            for i, a in enumerate(aliases_raw)
        )
    else:
        raise DataFormatError(
            f"{context}.aliases: expected string or list"
        )
    return Feature(
        name=name,
        kind=kind,
        description=description,
        aliases=aliases,
    )


def _parse_phone(
    entry: object,
    context: str,
    system: FeatureSystem,
) -> Segment:
    """Parse one entry of the ``phones`` list."""
    mapping = _require_mapping(entry, context)
    raw_ipa = _require_str(
        _require_key(mapping, "ipa", context),
        f"{context}.ipa",
    )
    canonical = canonicalize_ipa(raw_ipa)
    if canonical != raw_ipa:
        raise DataFormatError(
            f"{context}.ipa: not in canonical form. "
            f"Got {raw_ipa!r}, expected {canonical!r}. "
            f"Run scripts/ods_to_yaml.py to produce "
            f"canonical data."
        )
    type_ = _require_str(
        _require_key(mapping, "type", context),
        f"{context}.type",
    )
    if type_ not in _VALID_TYPES:
        raise DataFormatError(
            f"{context}.type: unknown type {type_!r}. "
            f"Expected one of {sorted(_VALID_TYPES)}."
        )
    tags_raw = mapping.get("classification_tags", [])
    if not isinstance(tags_raw, list):
        raise DataFormatError(
            f"{context}.classification_tags: expected list"
        )
    tags: list[str] = []
    for i, tag in enumerate(tags_raw):
        if not isinstance(tag, str):
            raise DataFormatError(
                f"{context}.classification_tags[{i}]: "
                f"expected string, got {type(tag).__name__}"
            )
        tags.append(tag)
    values: dict[str, Value] = {}
    features_raw = mapping.get("features", {})
    if not isinstance(features_raw, dict):
        raise DataFormatError(
            f"{context}.features: expected mapping"
        )
    for feature_name, raw_value in features_raw.items():
        try:
            feature = system.resolve(feature_name)
        except KeyError as exc:
            raise DataFormatError(
                f"{context}.features: {feature_name!r} is "
                f"not a declared feature"
            ) from exc
        if raw_value is True:
            values[feature.name] = Value("+")
        elif raw_value is False:
            values[feature.name] = Value("-")
        else:
            raise DataFormatError(
                f"{context}.features[{feature_name!r}]: "
                f"expected true or false, got "
                f"{type(raw_value).__name__}"
            )
    metadata: dict[str, object] = {}
    if tags:
        metadata["classification_tags"] = tuple(tags)
    return Segment(
        symbol=canonical,
        type=type_,
        classification={},
        values=values,
        metadata=metadata,
    )


def _load_feature_model_from_path(path: Path) -> FeatureModel:
    """Load and validate a feature-system YAML file."""
    raw = _read_yaml(path)
    root = _require_mapping(raw, str(path))
    _check_schema_version(root, str(path))
    name = _require_str(
        _require_key(root, "name", str(path)),
        f"{path}:name",
    )
    version = _require_str(
        _require_key(root, "version", str(path)),
        f"{path}:version",
    )
    description = root.get("description", "")
    if not isinstance(description, str):
        raise DataFormatError(
            f"{path}:description: expected string"
        )
    features_raw = _require_list(
        _require_key(root, "features", str(path)),
        f"{path}:features",
    )
    features: list[Feature] = []
    for i, entry in enumerate(features_raw):
        features.append(
            _parse_feature(entry, f"{path}:features[{i}]")
        )
    system = FeatureSystem(
        name=name,
        version=version,
        features=tuple(features),
        metadata={"description": description} if description
        else {},
    )
    phones_raw = _require_list(
        _require_key(root, "phones", str(path)),
        f"{path}:phones",
    )
    phones: dict[str, Segment] = {}
    for i, entry in enumerate(phones_raw):
        segment = _parse_phone(
            entry, f"{path}:phones[{i}]", system
        )
        if segment.symbol in phones:
            raise DataFormatError(
                f"{path}:phones[{i}]: duplicate phone "
                f"{segment.symbol!r}"
            )
        phones[segment.symbol] = segment
    return FeatureModel(system=system, phones=phones)


@lru_cache(maxsize=None)
def _load_builtin_feature_model(name: str) -> FeatureModel:
    """Load a builtin feature model, cached.

    The cache is unbounded because there are only a handful of
    builtin systems; caching them is safe and cheap.
    """
    if name not in BUILTIN_FEATURE_SYSTEMS:
        raise DataFormatError(
            f"Unknown builtin feature system: {name!r}. "
            f"Known: {BUILTIN_FEATURE_SYSTEMS}"
        )
    return _load_feature_model_from_path(_path_for_builtin(name))


def load_feature_model(
    name_or_path: str | Path,
) -> FeatureModel:
    """Load a feature model by name or from a path.

    Parameters
    ----------
    name_or_path : str or Path
        If a string matching a builtin name (``"panphon"``,
        ``"hayes"``), loads the bundled file and caches the
        result. If a :class:`Path` (or a string that looks like a
        path, i.e. contains ``/`` or ends in ``.yaml``), loads
        that file without caching. A string that is neither a
        builtin name nor a path raises ``DataFormatError``
        reporting the unknown builtin.

    Returns
    -------
    FeatureModel
        The loaded model.

    Raises
    ------
    DataFormatError
        If the file cannot be read, violates the data format
        spec, or the name is neither a builtin nor a plausible
        path.
    """
    if isinstance(name_or_path, Path):
        return _load_feature_model_from_path(name_or_path)
    name = str(name_or_path)
    if name in BUILTIN_FEATURE_SYSTEMS:
        return _load_builtin_feature_model(name)
    if "/" in name or name.endswith(".yaml"):
        return _load_feature_model_from_path(Path(name))
    raise DataFormatError(
        f"Unknown builtin feature system: {name!r}. "
        f"Known: {BUILTIN_FEATURE_SYSTEMS}"
    )


# ---------------------------------------------------------------------
# Symbol table loading
# ---------------------------------------------------------------------


def _load_symbol_table_from_path(path: Path) -> SymbolTable:
    raw = _read_yaml(path)
    root = _require_mapping(raw, str(path))
    _check_schema_version(root, str(path))
    notation = _require_str(
        _require_key(root, "notation", str(path)),
        f"{path}:notation",
    )
    description = root.get("description", "")
    if not isinstance(description, str):
        raise DataFormatError(
            f"{path}:description: expected string"
        )
    symbols_raw = _require_list(
        _require_key(root, "symbols", str(path)),
        f"{path}:symbols",
    )
    symbols: dict[str, str] = {}
    for i, entry in enumerate(symbols_raw):
        context = f"{path}:symbols[{i}]"
        mapping = _require_mapping(entry, context)
        symbol = _require_str(
            _require_key(mapping, "symbol", context),
            f"{context}.symbol",
        )
        canonical = _require_str(
            _require_key(mapping, "canonical", context),
            f"{context}.canonical",
        )
        # Validate canonicalization.
        if notation == "ipa":
            normalized = canonicalize_ipa(symbol)
        elif notation == "xsampa":
            normalized = canonicalize_xsampa(symbol)
        else:
            raise DataFormatError(
                f"{path}:notation: unknown notation {notation!r}"
            )
        if normalized != symbol:
            raise DataFormatError(
                f"{context}.symbol: not in canonical form. "
                f"Got {symbol!r}, expected {normalized!r}."
            )
        if symbol in symbols and symbols[symbol] != canonical:
            raise DataFormatError(
                f"{context}.symbol: duplicate symbol "
                f"{symbol!r} with different canonical "
                f"{canonical!r} (already {symbols[symbol]!r})"
            )
        symbols[symbol] = canonical
    return SymbolTable(
        notation=notation,
        symbols=symbols,
        description=description,
    )


@lru_cache(maxsize=None)
def _load_builtin_symbol_table(notation: str) -> SymbolTable:
    if notation not in BUILTIN_SYMBOL_TABLES:
        raise DataFormatError(
            f"Unknown builtin symbol table: {notation!r}. "
            f"Known: {BUILTIN_SYMBOL_TABLES}"
        )
    return _load_symbol_table_from_path(
        _path_for_builtin(notation)
    )


def load_symbol_table(
    notation_or_path: str | Path,
) -> SymbolTable:
    """Load a symbol table by notation name or from a path.

    Parameters
    ----------
    notation_or_path : str or Path
        If a string matching a builtin notation (``"ipa"``,
        ``"xsampa"``), loads the bundled file and caches the
        result. If a string that looks like a path (contains
        ``/`` or ends in ``.yaml``), loads that file without
        caching. A string that is neither raises
        ``DataFormatError``.

    Returns
    -------
    SymbolTable
        The loaded table.
    """
    if isinstance(notation_or_path, Path):
        return _load_symbol_table_from_path(notation_or_path)
    name = str(notation_or_path)
    if name in BUILTIN_SYMBOL_TABLES:
        return _load_builtin_symbol_table(name)
    if "/" in name or name.endswith(".yaml"):
        return _load_symbol_table_from_path(Path(name))
    raise DataFormatError(
        f"Unknown builtin symbol table: {name!r}. "
        f"Known: {BUILTIN_SYMBOL_TABLES}"
    )
