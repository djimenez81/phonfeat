#!/usr/bin/env python3
"""Convert the phonfeat source ODS spreadsheet to YAML data files.

Usage
-----
    python scripts/ods_to_yaml.py --ods data/data.ods \
                                 --out src/phonfeat/data \
                                 --diagnostics diagnostics

Reads the following sheets from the ODS:

- ``ipa_all_panphon``: the PanPhon-style feature table.
- ``ipa_hayes``: the Hayes-style feature table.
- ``ipa_xsampa``: IPA <-> X-SAMPA symbol correspondence.
- ``consonants_ipa``: grid of consonants by place and manner.
- ``vowels_ipa``: grid of vowels by height and backness-roundness.
- ``others_ipa``: grid of other symbols (clicks, coarticulations).
- ``definitions``: abbreviation definitions used by grid sheets.

Writes:

- ``panphon.feature.yaml``
- ``hayes.feature.yaml``
- ``ipa.symbols.yaml``
- ``xsampa.symbols.yaml``

And a set of diagnostic files in the diagnostics directory.

This script is development tooling, not part of the shipped package.
It requires ``pandas`` and ``odfpy``.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from phonfeat.canonicalize import (
    canonicalize_ipa,
    canonicalize_xsampa,
)


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------


PANPHON_SHEET = "ipa_all_panphon"
HAYES_SHEET = "ipa_hayes"
IPA_XSAMPA_SHEET = "ipa_xsampa"
CONSONANTS_SHEET = "consonants_ipa"
VOWELS_SHEET = "vowels_ipa"
OTHERS_SHEET = "others_ipa"
DEFINITIONS_SHEET = "definitions"


# ---------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------

class _IndentedDumper(yaml.SafeDumper):
    """SafeDumper that indents sequences under their parent key.

    PyYAML's default dumper produces::

        features:
        - name: syl

    which is valid YAML but visually awkward. This dumper
    overrides ``increase_indent`` to produce::

        features:
          - name: syl
    """

    def increase_indent(
        self, flow: bool = False, indentless: bool = False
    ) -> None:
        return super().increase_indent(flow, False)


def read_sheet(ods_path: Path, sheet: str) -> pd.DataFrame:
    """Read a single sheet from an ODS file.

    Parameters
    ----------
    ods_path : Path
        The ODS file.
    sheet : str
        The sheet name.

    Returns
    -------
    pandas.DataFrame
        The sheet's contents, header row included.

    Raises
    ------
    SystemExit
        If the sheet does not exist or the file cannot be read.
    """
    try:
        return pd.read_excel(
            ods_path,
            sheet_name=sheet,
            engine="odf",
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:
        sys.exit(
            f"Failed to read sheet {sheet!r} from {ods_path}: {exc}"
        )


# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------


def clean(value: Any) -> str:
    """Normalize a cell value to a stripped string."""
    if value is None:
        return ""
    s = str(value).strip()
    return s


def is_feature_value(value: str) -> bool:
    """Return True if ``value`` is a recognized feature value."""
    return value in ("+", "-", "0")


def feature_value_to_python(value: str) -> bool | None:
    """Convert a raw feature cell to a Python value.

    ``"+"`` becomes ``True``, ``"-"`` becomes ``False``, and
    ``"0"`` (or an empty cell) becomes ``None`` (undefined).
    """
    if value == "+":
        return True
    if value == "-":
        return False
    return None


# ---------------------------------------------------------------------
# Feature systems
# ---------------------------------------------------------------------


@dataclass
class Phone:
    """A phone extracted from a feature sheet."""

    ipa: str
    feature_values: dict[str, bool | None] = field(
        default_factory=dict
    )
    source_rows: list[str] = field(default_factory=list)
    characteristics: list[str] = field(default_factory=list)
    type: str = "consonant"
    name: str = ""


@dataclass
class FeatureSystemData:
    """The data needed to write a feature-system YAML."""

    name: str
    version: str
    description: str
    feature_names: list[str]
    feature_descriptions: dict[str, str]
    phones: list[Phone]
    duplicates: list[dict[str, Any]] = field(
        default_factory=list
    )
    undistinguished: list[dict[str, Any]] = field(
        default_factory=list
    )
    all_undefined: list[dict[str, Any]] = field(
        default_factory=list
    )


def extract_feature_system(
    df: pd.DataFrame, *, name: str, version: str
) -> FeatureSystemData:
    """Extract a feature system from a feature sheet.

    Parameters
    ----------
    df : pandas.DataFrame
        The feature sheet. Row 0 is a header whose columns after
        the first are feature names; column 0 is IPA. Subsequent
        rows are phones.
    name : str
        System name for the output YAML.
    version : str
        System version for the output YAML.

    Returns
    -------
    FeatureSystemData
        The extracted data, with duplicates and diagnostics filled
        in but not yet written.
    """
    if df.empty:
        raise ValueError(f"Empty sheet for {name!r}")
    feature_names = [clean(c) for c in df.columns[1:]]
    feature_names = [n for n in feature_names if n]
    ipa_col = df.columns[0]

    phones: dict[str, Phone] = {}
    duplicates: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        raw_ipa = clean(row[ipa_col])
        if not raw_ipa:
            continue
        try:
            canonical = canonicalize_ipa(raw_ipa)
        except Exception as exc:
            print(
                f"WARN: {name}: failed to canonicalize "
                f"{raw_ipa!r}: {exc}"
            )
            continue
        values: dict[str, bool | None] = {}
        for feature in feature_names:
            cell = clean(row[feature]) if feature in row else ""
            values[feature] = feature_value_to_python(cell)
        if canonical in phones:
            existing = phones[canonical]
            if existing.feature_values != values:
                duplicates.append(
                    {
                        "canonical": canonical,
                        "sources": [
                            *existing.source_rows,
                            raw_ipa,
                        ],
                        "features_agree": False,
                        "differing_features": _diff_features(
                            existing.feature_values, values
                        ),
                    }
                )
            else:
                existing.source_rows.append(raw_ipa)
        else:
            phones[canonical] = Phone(
                ipa=canonical,
                feature_values=values,
                source_rows=[raw_ipa],
            )

    # Classify phones by their feature values, so we can set
    # `type`. In PanPhon, vowels are [+syl, +son, -cons] and
    # consonants are [-syl, -cons-nonzero].
    _classify_phones(phones, name)

    system = FeatureSystemData(
        name=name,
        version=version,
        description=f"Feature system extracted from {name}.",
        feature_names=feature_names,
        feature_descriptions={},
        phones=list(phones.values()),
        duplicates=duplicates,
    )
    system.undistinguished = _detect_undistinguished(
        system.phones
    )
    system.all_undefined = _detect_all_undefined(system.phones)
    return system


def _diff_features(
    a: dict[str, bool | None], b: dict[str, bool | None]
) -> dict[str, tuple[bool | None, bool | None]]:
    """Return feature values that differ between two dicts."""
    diff: dict[str, tuple[bool | None, bool | None]] = {}
    for key in a:
        if a[key] != b.get(key):
            diff[key] = (a[key], b.get(key))
    return diff


def _classify_phones(
    phones: dict[str, Phone], system: str
) -> None:
    """Assign ``type`` to each phone based on its features."""
    for phone in phones.values():
        f = phone.feature_values
        # Vowels: [+syl] and not [-cons]. In PanPhon, vowels have
        # syl="+", son="+", cons="-"; in Hayes, syllabic="+",
        # consonantal="-".
        is_syllabic = (
            f.get("syl") is True
            or f.get("syllabic") is True
        )
        is_consonantal = (
            f.get("cons") is True
            or f.get("consonantal") is True
        )
        if is_syllabic and not is_consonantal:
            phone.type = "vowel"
        elif not is_syllabic and is_consonantal:
            phone.type = "consonant"
        else:
            # Fallback: everything else is `other`. This catches
            # tones (all features None), and rare coarticulated
            # segments that PanPhon doesn't classify cleanly.
            phone.type = "other"


def _detect_undistinguished(
    phones: list[Phone],
) -> list[dict[str, Any]]:
    """Find phones whose feature vectors are identical.

    Two phones are "undistinguished" if every feature they both
    define has the same value, and at least one pair has an
    identical *full* vector (including Nones).

    The output reports groups of phones that share a vector.
    """
    groups: dict[
        tuple[tuple[str, bool | None], ...], list[Phone]
    ] = defaultdict(list)
    for phone in phones:
        key = tuple(sorted(phone.feature_values.items()))
        groups[key].append(phone)
    collisions = []
    for _, group in groups.items():
        if len(group) > 1:
            collisions.append(
                {
                    "phones": sorted(p.ipa for p in group),
                    "feature_vector": dict(group[0].feature_values),
                }
            )
    return collisions


def _detect_all_undefined(
    phones: list[Phone],
) -> list[dict[str, Any]]:
    """Find phones whose every feature is undefined."""
    undefined = []
    for phone in phones:
        if all(v is None for v in phone.feature_values.values()):
            undefined.append(
                {
                    "phone": phone.ipa,
                    "type": phone.type,
                }
            )
    return undefined


# ---------------------------------------------------------------------
# Symbol tables
# ---------------------------------------------------------------------


def extract_symbol_table(
    df: pd.DataFrame, *, side: str
) -> dict[str, Any]:
    """Extract a symbol table from the ``ipa_xsampa`` sheet.

    Parameters
    ----------
    df : pandas.DataFrame
        The sheet. Expected columns: ``ipa``, ``xsampa``, ``name``.
    side : str
        ``"ipa"`` or ``"xsampa"``; the notation this table is for.

    Returns
    -------
    dict
        A YAML-ready structure with ``notation`` and ``symbols``.
    """
    if side not in ("ipa", "xsampa"):
        raise ValueError(
            f"side must be 'ipa' or 'xsampa'; got {side!r}"
        )
    if df.empty:
        raise ValueError("Empty ipa_xsampa sheet")
    ipa_col = df.columns[0]
    xsampa_col = df.columns[1]

    entries: dict[str, str] = {}
    for _, row in df.iterrows():
        raw_ipa = clean(row[ipa_col])
        raw_xsampa = clean(row[xsampa_col])
        if not raw_ipa:
            continue
        try:
            if side == "ipa":
                symbol = canonicalize_ipa(raw_ipa)
                canonical = canonicalize_ipa(raw_ipa)
            else:
                symbol = canonicalize_xsampa(raw_xsampa)
                canonical = canonicalize_ipa(raw_ipa)
        except Exception as exc:
            print(
                f"WARN: failed to canonicalize {raw_ipa!r} / "
                f"{raw_xsampa!r}: {exc}"
            )
            continue
        if symbol in entries and entries[symbol] != canonical:
            print(
                f"WARN: symbol {symbol!r} maps to multiple "
                f"canonicals: {entries[symbol]!r} and "
                f"{canonical!r}"
            )
            continue
        entries[symbol] = canonical

    return {
        "notation": side,
        "description": (
            f"{side.upper()} symbol table, extracted from "
            f"{IPA_XSAMPA_SHEET}."
        ),
        "symbols": [
            {"symbol": symbol, "canonical": canonical}
            for symbol, canonical in sorted(entries.items())
        ],
    }


# ---------------------------------------------------------------------
# Characteristics from grid sheets
# ---------------------------------------------------------------------


def parse_grid_headers(
    df: pd.DataFrame,
) -> tuple[list[str], list[tuple[str, ...]]]:
    """Parse grid sheet headers into per-row and per-column tags.

    The grid sheets have a first column of row headers and a first
    row of column headers. Row headers like ``stp`` are single
    tags; column headers like ``blb vls`` are space-separated lists
    of tags.

    Parameters
    ----------
    df : pandas.DataFrame
        A grid sheet.

    Returns
    -------
    tuple
        ``(row_headers, column_headers)``. Row headers are a list
        of strings; column headers are a list of tuples of strings.
    """
    row_headers: list[str] = []
    for value in df.iloc[1:, 0]:
        row_headers.append(clean(value))
    column_headers: list[tuple[str, ...]] = []
    for value in df.columns[1:]:
        column_headers.append(
            tuple(clean(value).split())
        )
    return row_headers, column_headers


def extract_characteristics(
    grids: dict[str, pd.DataFrame],
) -> dict[str, list[str]]:
    """Extract characteristic tags per canonical IPA phone.

    Merges tags from all grid sheets. If a phone appears in
    multiple cells, tags are combined and deduplicated.

    Parameters
    ----------
    grids : dict
        Mapping from grid sheet name to DataFrame.

    Returns
    -------
    dict
        Mapping from canonical IPA symbol to list of characteristic
        tags, sorted for determinism.
    """
    result: dict[str, set[str]] = defaultdict(set)
    for sheet_name, df in grids.items():
        if df.empty:
            continue
        row_headers, column_headers = parse_grid_headers(df)
        for row_index, row_header in enumerate(row_headers):
            if not row_header:
                continue
            row_cells = df.iloc[row_index + 1, 1:]
            for col_index, raw_cell in enumerate(row_cells):
                cell = clean(raw_cell)
                if not cell:
                    continue
                try:
                    canonical = canonicalize_ipa(cell)
                except Exception as exc:
                    print(
                        f"WARN: {sheet_name}: failed to "
                        f"canonicalize {cell!r}: {exc}"
                    )
                    continue
                tags = {row_header}
                if col_index < len(column_headers):
                    tags.update(column_headers[col_index])
                result[canonical].update(tags)
    return {
        ipa: sorted(tags)
        for ipa, tags in sorted(result.items())
    }


def apply_characteristics(
    system: FeatureSystemData,
    characteristics: dict[str, list[str]],
) -> None:
    """Attach characteristics to phones, inheriting from bases.

    For a phone not directly in the grid, the longest canonical
    prefix that *is* in the grid supplies the base characteristics.
    Diacritics in the phone are then added as their own tags when
    recognizable (e.g. ``ˤ`` adds ``pzd``).

    Mutates ``system.phones`` in place.
    """
    diacritic_tags = {
        "\u02e4": "pzd",   # ˤ pharyngealized
        "\u02e0": "vzd",   # ˠ velarized
        "\u02b7": "ptr",   # ʷ labialized/protruded
        "\u02b2": "pzd",   # ʲ palatalized (reuse pzd tag)
        "\u0303": "nzd",   # combining tilde (nasalized)
        "\u0325": "vls",   # ring below (voiceless)
        "\u030a": "vls",   # ring above (voiceless)
        "\u02d0": "lng",   # length mark
        "\u031f": "atr",   # advanced
        "\u0320": "rtr",   # retracted
    }
    for phone in system.phones:
        if phone.ipa in characteristics:
            phone.characteristics = list(
                characteristics[phone.ipa]
            )
            continue
        # Inherit from longest prefix that has characteristics.
        for length in range(len(phone.ipa) - 1, 0, -1):
            prefix = phone.ipa[:length]
            if prefix in characteristics:
                inherited = set(characteristics[prefix])
                for char in phone.ipa[length:]:
                    tag = diacritic_tags.get(char)
                    if tag:
                        inherited.add(tag)
                phone.characteristics = sorted(inherited)
                break


# ---------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------


def write_feature_system(
    system: FeatureSystemData, path: Path
) -> None:
    """Write a feature-system YAML file."""
    features_block = []
    for feature_name in system.feature_names:
        entry: dict[str, Any] = {"name": feature_name}
        description = system.feature_descriptions.get(
            feature_name
        )
        if description:
            entry["description"] = description
        features_block.append(entry)

    phones_block = []
    for phone in sorted(system.phones, key=lambda p: p.ipa):
        entry = {"ipa": phone.ipa, "type": phone.type}
        if phone.name:
            entry["name"] = phone.name
        if phone.characteristics:
            entry["characteristics"] = phone.characteristics
        defined = {
            name: value
            for name, value in phone.feature_values.items()
            if value is not None
        }
        entry["features"] = defined
        phones_block.append(entry)

    data = {
        "schema_version": "1.0",
        "name": system.name,
        "version": system.version,
        "description": system.description,
        "features": features_block,
        "phones": phones_block,
    }
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(
            data,
            fh,
            Dumper=_IndentedDumper,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=79,
        )


def write_symbol_table(data: dict[str, Any], path: Path) -> None:
    """Write a symbol-table YAML file."""
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(
            data,
            fh,
            Dumper=_IndentedDumper,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=79,
        )


def write_diagnostics(
    system: FeatureSystemData, out_dir: Path
) -> None:
    """Write diagnostics for one feature system."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = system.name
    for name, items in [
        ("duplicates", system.duplicates),
        ("undistinguished", system.undistinguished),
        ("all_undefined", system.all_undefined),
    ]:
        path = out_dir / f"{stem}_{name}.yaml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(
                items,
                fh,
                Dumper=_IndentedDumper,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
                width=79,
            )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert the phonfeat ODS to YAML."
    )
    parser.add_argument(
        "--ods",
        type=Path,
        required=True,
        help="Path to data.ods.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Directory to write the YAML data files to.",
    )
    parser.add_argument(
        "--diagnostics",
        type=Path,
        default=Path("diagnostics"),
        help="Directory to write diagnostics to.",
    )
    args = parser.parse_args()

    if not args.ods.exists():
        sys.exit(f"ODS file not found: {args.ods}")

    args.out.mkdir(parents=True, exist_ok=True)

    print(f"Reading {args.ods}")

    panphon_df = read_sheet(args.ods, PANPHON_SHEET)
    hayes_df = read_sheet(args.ods, HAYES_SHEET)
    ipa_xsampa_df = read_sheet(args.ods, IPA_XSAMPA_SHEET)

    print(f"  {PANPHON_SHEET}: {len(panphon_df)} rows")
    print(f"  {HAYES_SHEET}: {len(hayes_df)} rows")
    print(f"  {IPA_XSAMPA_SHEET}: {len(ipa_xsampa_df)} rows")

    print("Extracting characteristics from grid sheets")
    grids = {
        CONSONANTS_SHEET: read_sheet(args.ods, CONSONANTS_SHEET),
        VOWELS_SHEET: read_sheet(args.ods, VOWELS_SHEET),
        OTHERS_SHEET: read_sheet(args.ods, OTHERS_SHEET),
    }
    characteristics = extract_characteristics(grids)
    print(f"  {len(characteristics)} symbols with characteristics")

    print("Extracting feature systems")
    panphon = extract_feature_system(
        panphon_df, name="panphon", version="0.1.0"
    )
    apply_characteristics(panphon, characteristics)
    print(
        f"  panphon: {len(panphon.phones)} unique phones after "
        f"canonicalization"
    )
    print(f"    {len(panphon.duplicates)} canonicalization merges")
    print(
        f"    {len(panphon.undistinguished)} undistinguished "
        f"groups"
    )
    print(
        f"    {len(panphon.all_undefined)} all-undefined phones"
    )

    hayes = extract_feature_system(
        hayes_df, name="hayes", version="0.1.0"
    )
    apply_characteristics(hayes, characteristics)
    print(f"  hayes: {len(hayes.phones)} unique phones")
    print(f"    {len(hayes.duplicates)} canonicalization merges")
    print(f"    {len(hayes.undistinguished)} undistinguished groups")
    print(f"    {len(hayes.all_undefined)} all-undefined phones")

    print("Extracting symbol tables")
    ipa_symbols = extract_symbol_table(
        ipa_xsampa_df, side="ipa"
    )
    xsampa_symbols = extract_symbol_table(
        ipa_xsampa_df, side="xsampa"
    )
    print(
        f"  ipa: {len(ipa_symbols['symbols'])} entries"
    )
    print(
        f"  xsampa: {len(xsampa_symbols['symbols'])} entries"
    )

    print(f"Writing to {args.out}")
    write_feature_system(
        panphon, args.out / "panphon.feature.yaml"
    )
    write_feature_system(
        hayes, args.out / "hayes.feature.yaml"
    )
    write_symbol_table(
        ipa_symbols, args.out / "ipa.symbols.yaml"
    )
    write_symbol_table(
        xsampa_symbols, args.out / "xsampa.symbols.yaml"
    )

    print(f"Writing diagnostics to {args.diagnostics}")
    write_diagnostics(panphon, args.diagnostics)
    write_diagnostics(hayes, args.diagnostics)

    print("Done.")


if __name__ == "__main__":
    main()
