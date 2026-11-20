"""Tokenizing IPA and X-SAMPA strings into segments.

The tokenizer splits a string into phones, each returned as a
:class:`lingcore.Segment`. Matching is maximal munch over the notation's
symbol table: at every position the longest listed symbol wins, which is
what makes multi-character symbols (``t͡ʃ`` in IPA, ``tS`` in X-SAMPA)
come out whole rather than as a base plus stray characters.

Diacritics are *stacked*: a modifier attaches to the phone it follows
and becomes part of that segment's ``symbol``. ``kʰ`` is one segment,
not two. This matches the decision recorded as Q5 in ``decisions.md``
and matches how the shipped data is organized — PanPhon carries no
phone with a combining tone mark, and models tone as its own segment,
so stacking is the only reading that keeps both notations consistent.

Two marks are exempt from stacking: the stress marks, which precede
the syllable they apply to rather than modifying the phone before
them. They come out as their own segments of type ``"other"``.

Tone bars (``˥˦˧˨˩``) also stay separate. They are Unicode category
``Sk``, not modifier letters, so the modifier test excludes them; but
the reason is not typographic. PanPhon models tone as its own segment
of type ``"other"`` and has no phone carrying a combining tone mark,
so attaching a tone bar to a vowel would produce a symbol the feature
data cannot describe.

Segment types come from a feature model, not from the symbol table,
because the symbol table does not carry types. Pass ``model=`` to
resolve them; without a model every segment is typed ``"other"``.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from lingcore import Segment

from .canonicalize import (
    _is_modifier,
    canonicalize_ipa,
    canonicalize_xsampa,
    normalize_for_matching,
)
from .errors import NotationError, TokenizationError
from .storage import FeatureModel, load_feature_model, load_symbol_table

__all__ = ["tokenize"]


# ---------------------------------------------------------------------
# Matching tables
# ---------------------------------------------------------------------


#: Marks that precede their syllable and so never attach to the phone
#: before them. Keyed by notation.
_PROSODIC: dict[str, frozenset[str]] = {
    "ipa": frozenset({"ˈ", "ˌ"}),
    "xsampa": frozenset({'"', "%"}),
}

#: The segment type given when no feature model can supply one.
_UNKNOWN_TYPE = "other"


@lru_cache(maxsize=None)
def _matching_tables(
    notation: str,
) -> tuple[tuple[tuple[str, str], ...], frozenset[str]]:
    """Return the symbol table flattened for matching, plus modifiers.

    The first element is the table's ``(symbol, canonical)`` pairs
    sorted by descending symbol length then by symbol, so that
    maximal munch is a linear scan and ties are broken
    deterministically. The second is the set of canonical forms that
    act as modifiers: single characters that are combining marks or
    modifier letters (Unicode category ``Lm``).
    """
    table = load_symbol_table(notation)
    pairs = tuple(
        sorted(
            table.symbols.items(),
            key=lambda item: (-len(item[0]), item[0]),
        )
    )
    modifiers = frozenset(
        canonical
        for _, canonical in pairs
        if len(canonical) == 1 and _is_modifier(canonical)
    )
    return pairs, modifiers


def _match(
    pairs: tuple[tuple[str, str], ...], text: str, position: int
) -> tuple[str, str] | None:
    """Return the longest ``(symbol, canonical)`` matching at position."""
    for symbol, canonical in pairs:
        if text.startswith(symbol, position):
            return symbol, canonical
    return None


# ---------------------------------------------------------------------
# Type resolution
# ---------------------------------------------------------------------


def _resolve_model(
    model: str | FeatureModel | None,
) -> FeatureModel | None:
    """Accept a model, a builtin name, or ``None``."""
    if model is None:
        return None
    if isinstance(model, str):
        return load_feature_model(model)
    return model


def _segment_type(
    model: FeatureModel | None,
    canonical: str,
    base: str,
) -> str:
    """Return the type of a segment, preferring the full symbol.

    A modified phone (``aː``) is usually absent from a feature model
    even when its base (``a``) is present, so the lookup falls back to
    the base. A modifier does not change whether a phone is a
    consonant, a vowel, or neither.
    """
    if model is None:
        return _UNKNOWN_TYPE
    for candidate in (canonical, base):
        segment = model.phones.get(candidate)
        if segment is not None:
            return segment.type
    return _UNKNOWN_TYPE


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


def tokenize(
    text: str,
    notation: str = "ipa",
    *,
    model: str | FeatureModel | None = None,
) -> tuple[Segment, ...]:
    """Split ``text`` into segments.

    Parameters
    ----------
    text : str
        The string to tokenize, in ``notation``.
    notation : str, optional
        Either ``"ipa"`` (the default) or ``"xsampa"``.
    model : str or FeatureModel, optional
        The feature model used to type the segments. Pass a builtin
        name (``"panphon"``, ``"hayes"``) or a loaded
        :class:`~phonfeat.storage.FeatureModel`. When omitted, every
        segment is typed ``"other"`` and the tokenizer does no data
        loading beyond the symbol table. Note that ``"panphon"`` takes
        a few seconds to load the first time and stays cached
        afterwards; ``"hayes"`` loads in about a tenth of a second.

    Returns
    -------
    tuple of lingcore.Segment
        One segment per phone, in order. Each has ``symbol`` set to
        the canonical form, ``type`` set from the model (or
        ``"other"``), and empty ``classification`` and ``values``;
        attaching features is a later step.

    Raises
    ------
    TypeError
        If ``text`` is not a string.
    NotationError
        If ``notation`` is not a known symbol table.
    TokenizationError
        If some part of ``text`` does not match any symbol.

    Notes
    -----
    The input is normalized with the boundary-preserving steps only
    (Unicode decomposition and deprecation replacement). Diacritic
    reordering cannot be applied to a whole string, because it assumes
    a single phone and would move marks across phone boundaries; it is
    applied per token instead, once the token is known to be one
    phone.

    A modifier at the start of the string, or one that follows nothing
    the table recognizes, becomes its own segment. That is how the
    stress marks behave: ``"ˈmata"`` tokenizes to four segments, the
    first being the stress mark itself.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"tokenize expects str, got {type(text).__name__}"
        )
    if notation not in _PROSODIC:
        raise NotationError(
            f"Unknown notation {notation!r}; expected 'ipa' or "
            f"'xsampa'"
        )

    resolved = _resolve_model(model)
    canonicalize = (
        canonicalize_ipa if notation == "ipa" else canonicalize_xsampa
    )
    pairs, modifiers = _matching_tables(notation)
    prosodic = _PROSODIC[notation]

    text = normalize_for_matching(text, notation)

    segments: list[Segment] = []
    position = 0
    while position < len(text):
        matched = _match(pairs, text, position)
        if matched is None:
            char = text[position]
            raise TokenizationError(
                f"No symbol in the {notation!r} table matches "
                f"{char!r} (U+{ord(char):04X}) at offset "
                f"{position} of {text!r}"
            )
        symbol, canonical = matched
        start = position
        position += len(symbol)

        base = canonical
        if canonical not in prosodic:
            while position < len(text):
                extra = _match(pairs, text, position)
                if extra is None:
                    break
                _, extra_canonical = extra
                if extra_canonical not in modifiers:
                    break
                if extra_canonical in prosodic:
                    break
                position += len(extra[0])

        token = text[start:position]
        canonical_token = canonicalize(token)
        segments.append(
            Segment(
                symbol=canonical_token,
                type=_segment_type(
                    resolved, canonical_token, base
                ),
            )
        )
    return tuple(segments)
