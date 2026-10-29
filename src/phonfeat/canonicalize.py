"""Canonicalization of IPA and X-SAMPA symbols.

Two symbols that denote the same phone must canonicalize to the same
string. This module defines those transformations.

IPA canonicalization applies, in order:

1. NFC normalization.
2. Deprecation replacement (``g`` -> ``ɡ``, ligature affricates ->
   tie-barred forms).
3. Diacritic reordering per the diacritic order table.
4. Tie bar normalization.

X-SAMPA canonicalization is simpler:

1. Deprecation replacement.
2. Underscore-diacritic normalization.

The transformation tables live in ``phonfeat/data`` as YAML files.
They are loaded lazily on first use and cached.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files as _resource_files
from pathlib import Path
from typing import Iterable, Sequence

import yaml

from .errors import DataFormatError

__all__ = [
    "DeprecationRule",
    "DiacriticCategory",
    "canonicalize_ipa",
    "canonicalize_xsampa",
    "load_deprecations",
    "load_diacritic_order",
]


# ---------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeprecationRule:
    """A single deprecation replacement.

    Parameters
    ----------
    from_ : str
        The string to replace.
    to : str
        The replacement.
    reason : str, optional
        Human-readable justification. Defaults to ``""``.
    """

    from_: str
    to: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class DiacriticCategory:
    """A named group of diacritics in canonical order.

    Parameters
    ----------
    category : str
        Identifier, e.g. ``"phonation"``.
    symbols : tuple of str
        Diacritic codepoints in this category, in canonical order.
    """

    category: str
    symbols: tuple[str, ...]


# ---------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------


def _data_path(name: str) -> Path:
    """Return the path to a bundled data file."""
    return Path(str(_resource_files("phonfeat") / "data" / name))


def _read_yaml(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError as exc:
        raise DataFormatError(f"Data file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise DataFormatError(
            f"Malformed YAML in {path}: {exc}"
        ) from exc


def load_deprecations(
    path: Path | None = None,
) -> tuple[DeprecationRule, ...]:
    """Load deprecation rules from a YAML file.

    Parameters
    ----------
    path : Path, optional
        Path to a deprecations YAML file. If ``None``, uses the
        file bundled with phonfeat.

    Returns
    -------
    tuple of DeprecationRule
        The rules, in the order they should be applied.
    """
    if path is None:
        path = _data_path("deprecations.yaml")
    raw = _read_yaml(path)
    if not isinstance(raw, list):
        raise DataFormatError(
            f"{path}: top level must be a list of rules"
        )
    rules: list[DeprecationRule] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise DataFormatError(
                f"{path}: entry {i} is not a mapping"
            )
        try:
            from_ = entry["from"]
            to = entry["to"]
        except KeyError as exc:
            raise DataFormatError(
                f"{path}: entry {i} missing key {exc.args[0]!r}"
            ) from exc
        reason = entry.get("reason", "")
        rules.append(
            DeprecationRule(from_=from_, to=to, reason=reason)
        )
    return tuple(rules)


def load_diacritic_order(
    path: Path | None = None,
) -> tuple[DiacriticCategory, ...]:
    """Load the diacritic ordering table from a YAML file.

    Parameters
    ----------
    path : Path, optional
        Path to a diacritic order YAML file. If ``None``, uses the
        file bundled with phonfeat.

    Returns
    -------
    tuple of DiacriticCategory
        The categories, in canonical order.
    """
    if path is None:
        path = _data_path("diacritic_order.yaml")
    raw = _read_yaml(path)
    if not isinstance(raw, list):
        raise DataFormatError(
            f"{path}: top level must be a list of categories"
        )
    categories: list[DiacriticCategory] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise DataFormatError(
                f"{path}: entry {i} is not a mapping"
            )
        try:
            category = entry["category"]
            symbols = entry["symbols"]
        except KeyError as exc:
            raise DataFormatError(
                f"{path}: entry {i} missing key {exc.args[0]!r}"
            ) from exc
        if not isinstance(symbols, list):
            raise DataFormatError(
                f"{path}: entry {i} 'symbols' must be a list"
            )
        categories.append(
            DiacriticCategory(
                category=category,
                symbols=tuple(symbols),
            )
        )
    return tuple(categories)


# ---------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------


@lru_cache(maxsize=1)
def _cached_deprecations() -> tuple[DeprecationRule, ...]:
    return load_deprecations()


@lru_cache(maxsize=1)
def _cached_diacritic_order() -> tuple[DiacriticCategory, ...]:
    return load_diacritic_order()


@lru_cache(maxsize=1)
def _diacritic_rank() -> dict[str, int]:
    """Return a mapping from diacritic codepoint to sort rank."""
    rank: dict[str, int] = {}
    for category_index, category in enumerate(
        _cached_diacritic_order()
    ):
        for symbol_index, symbol in enumerate(category.symbols):
            rank[symbol] = category_index * 100 + symbol_index
    return rank


# ---------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------


def _apply_deprecations(
    symbol: str, rules: Sequence[DeprecationRule]
) -> str:
    """Apply deprecation rules left to right, longest match first.

    Rules are sorted by descending ``from_`` length so that a longer
    deprecated form (``ʧ``) is replaced before a shorter form that
    might be a prefix.
    """
    ordered = sorted(rules, key=lambda r: -len(r.from_))
    result = symbol
    for rule in ordered:
        result = result.replace(rule.from_, rule.to)
    return result


def _reorder_diacritics(symbol: str) -> str:
    """Reorder diacritics into the canonical sequence.

    A phone is decomposed into one or more "segments" separated by
    tie bars. Each segment has a base character followed by a
    sequence of modifiers (combining marks and modifier letters).
    Within each segment, modifiers are reordered by their position
    in the diacritic order table.

    Tie bars (U+0361, U+035C) are preserved between segments; they
    are not treated as modifiers and are never moved.
    """
    if not symbol:
        return symbol

    tie_bars = ("\u0361", "\u035c")
    rank = _diacritic_rank()

    # Split into segments at tie bars, keeping the tie bars as
    # separate tokens so we can reattach them in place.
    segments: list[list[str]] = [[]]
    tie_bar_tokens: list[str] = []
    for char in symbol:
        if char in tie_bars:
            tie_bar_tokens.append(char)
            segments.append([])
        else:
            segments[-1].append(char)

    reordered: list[str] = []
    for i, segment in enumerate(segments):
        reordered.append(_reorder_segment(segment, rank))
        if i < len(tie_bar_tokens):
            reordered.append(tie_bar_tokens[i])
    return "".join(reordered)


def _is_modifier(char: str) -> bool:
    """Return True if ``char`` is a diacritic-like character.

    This covers combining marks (Unicode combining class > 0) and
    modifier letters (Unicode general category ``Lm``), which
    includes length marks, nasalization superscripts, and other
    spacing diacritics.
    """
    if unicodedata.combining(char):
        return True
    return unicodedata.category(char) == "Lm"


def _reorder_segment(
    segment: list[str], rank: dict[str, int]
) -> str:
    """Reorder one tie-bar-separated segment.

    The first character is the nucleus and stays in place. The
    remaining characters are modifiers and are sorted by rank;
    characters not in the rank table keep their original relative
    order and are placed after all ranked ones.
    """
    if not segment:
        return ""
    nucleus = segment[0]
    modifiers = segment[1:]
    if not modifiers:
        return nucleus
    indexed = list(enumerate(modifiers))
    # Modifiers not in the rank table are not reordered; they keep
    # their original position, which we encode by giving them the
    # index as a tiebreak and a large rank.
    indexed.sort(
        key=lambda pair: (
            rank.get(pair[1], 10_000),
            pair[0],
        )
    )
    ordered = [char for _, char in indexed]
    return nucleus + "".join(ordered)

def canonicalize_ipa(symbol: str) -> str:
    """Return the canonical IPA form of ``symbol``.

    Applies NFC normalization, deprecation replacement, and
    diacritic reordering. Two symbols denoting the same phone
    canonicalize to the same string.

    Parameters
    ----------
    symbol : str
        The IPA symbol to canonicalize.

    Returns
    -------
    str
        The canonical form.
    """
    if not isinstance(symbol, str):
        raise TypeError(
            f"canonicalize_ipa expects str, got "
            f"{type(symbol).__name__}"
        )
    result = unicodedata.normalize("NFC", symbol)
    result = _apply_deprecations(result, _cached_deprecations())
    result = _reorder_diacritics(result)
    result = unicodedata.normalize("NFC", result)
    return result


def canonicalize_xsampa(symbol: str) -> str:
    """Return the canonical X-SAMPA form of ``symbol``.

    Applies deprecation replacement only. X-SAMPA is ASCII, so no
    Unicode normalization is performed, and diacritics are already
    in a single canonical form (``_X`` suffixes) by construction.

    Parameters
    ----------
    symbol : str
        The X-SAMPA symbol to canonicalize.

    Returns
    -------
    str
        The canonical form.
    """
    if not isinstance(symbol, str):
        raise TypeError(
            f"canonicalize_xsampa expects str, got "
            f"{type(symbol).__name__}"
        )
    result = _apply_deprecations(symbol, _cached_deprecations())
    return result
