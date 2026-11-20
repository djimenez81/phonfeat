"""Declarative transcription profiles.

A corpus rarely arrives in textbook notation. Real files carry
practical orthography, mixed alphabets, morpheme hyphens, multi-word
cells and one-off characters no symbol table lists. :func:`tokenize`
can only be as right as the string it is given, and guessing what a
character *probably* means is exactly the kind of assumption this
package refuses to make: a wrong guess produces a clean tokenization
of a wrong inventory, with no error anywhere.

A :class:`Profile` is the place where such knowledge is declared
explicitly, by the user, in data rather than in code. It records
three things:

1. **Substitutions** — a textual rewrite applied before matching,
   e.g. ``{"ñ": "ɲ", "c": "t͡ʃ"}``. This is how a character the
   symbol table does not know at all gets read, and how a symbol
   that is valid IPA but is being used with its orthographic value
   gets re-read.
2. **Splitting** — a regular expression that separates independent
   forms inside one string (``"[\\\\s,;]+"`` turns a cell holding
   ``"bacok, bacuk"`` into two forms).
3. **Stripping** — characters removed from each form after
   splitting, for material that is orthographic rather than
   phonological (``"-"`` for morpheme boundaries).

Nothing is inferred. A profile with no substitutions, no splitting
and no stripping is the default, and it means "read this file
literally".

Why data and not arguments
--------------------------
A profile is a document the corpus owner can read, diff and
withdraw. An ``if`` in a loader is none of those, and a later reader
cannot tell a considered decision from a bug.

Limits worth knowing
--------------------
Because substitutions rewrite text, they are context-free: a symbol
used two different ways inside one file cannot be resolved by a
profile alone. Files that mix transcription systems per language
need one profile per language and, therefore, language labels in the
data. Where those labels are absent, no profile can tell the
readings apart, and that is a property of the corpus, not of this
module.

Strict validation
-----------------
Unlike the bundled data loader, which ignores unknown keys so that
newer data files stay readable by older code (see
``data_format_spec.md`` §5.1), a profile rejects unknown keys. A
mistyped key in a configuration file that the user wrote by hand is
a mistake, not a forward-compatibility case: silently ignoring it
would yield a silently wrong inventory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

from .errors import DataFormatError, NotationError

__all__ = ["Profile", "load_profile"]


_KNOWN_KEYS = frozenset(
    {"notation", "description", "substitutions", "split", "strip_chars"}
)

_NOTATIONS = ("ipa", "xsampa")


@dataclass(frozen=True)
class Profile:
    """How to read the strings of one corpus.

    Parameters
    ----------
    notation : str, optional
        ``"ipa"`` (the default) or ``"xsampa"``.
    substitutions : Mapping of str to str, optional
        Textual rewrites applied before matching, in longest-key-first
        order. Keys and values must be non-empty and must differ.
    split : str, optional
        Regular expression separating independent forms inside one
        string. ``None`` (the default) keeps each string whole.
    strip_chars : str, optional
        Characters removed from each form after splitting.
    description : str, optional
        Free-text note recorded with the profile and echoed in
        reports. Defaults to ``""``.

    Raises
    ------
    NotationError
        If ``notation`` is not a known notation.
    DataFormatError
        If any field has the wrong type or a substitution is
        degenerate.

    Notes
    -----
    The instance is frozen and the substitution mapping is wrapped in
    a read-only view, so a profile cannot drift after it has been
    used to read a corpus.
    """

    notation: str = "ipa"
    substitutions: Mapping[str, str] = field(default_factory=dict)
    split: str | None = None
    strip_chars: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if self.notation not in _NOTATIONS:
            raise NotationError(
                f"Unknown notation {self.notation!r}; expected one of "
                f"{_NOTATIONS}"
            )
        if not isinstance(self.strip_chars, str):
            raise DataFormatError(
                f"strip_chars must be a string, got "
                f"{type(self.strip_chars).__name__}"
            )
        if self.split is not None:
            if not isinstance(self.split, str) or not self.split:
                raise DataFormatError(
                    "split must be a non-empty regular expression or None"
                )
            try:
                re.compile(self.split)
            except re.error as exc:
                raise DataFormatError(
                    f"split is not a valid regular expression: {exc}"
                ) from exc
        if not isinstance(self.substitutions, Mapping):
            raise DataFormatError(
                f"substitutions must be a mapping, got "
                f"{type(self.substitutions).__name__}"
            )
        subs: dict[str, str] = {}
        for key, value in self.substitutions.items():
            if not isinstance(key, str) or not key:
                raise DataFormatError(
                    f"substitution keys must be non-empty strings, "
                    f"got {key!r}"
                )
            if not isinstance(value, str) or not value:
                raise DataFormatError(
                    f"substitution for {key!r} must be a non-empty "
                    f"string, got {value!r}"
                )
            if key == value:
                raise DataFormatError(
                    f"substitution for {key!r} maps it to itself"
                )
            subs[key] = value
        object.__setattr__(
            self, "substitutions", MappingProxyType(subs)
        )
        object.__setattr__(self, "description", str(self.description))

    # -- construction --------------------------------------------------

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Profile:
        """Build a profile from a mapping, rejecting unknown keys.

        Raises
        ------
        DataFormatError
            If ``data`` is not a mapping or contains keys this class
            does not define.
        """
        if not isinstance(data, Mapping):
            raise DataFormatError(
                f"a profile must be a mapping, got "
                f"{type(data).__name__}"
            )
        unknown = sorted(set(data) - _KNOWN_KEYS)
        if unknown:
            raise DataFormatError(
                f"Unknown profile key(s) {unknown}; known keys are "
                f"{sorted(_KNOWN_KEYS)}"
            )
        return cls(
            notation=data.get("notation", "ipa"),
            substitutions=data.get("substitutions") or {},
            split=data.get("split"),
            strip_chars=data.get("strip_chars", ""),
            description=data.get("description", ""),
        )

    def to_mapping(self) -> dict[str, Any]:
        """Return a plain, YAML-serializable mapping."""
        return {
            "notation": self.notation,
            "description": self.description,
            "substitutions": dict(self.substitutions),
            "split": self.split,
            "strip_chars": self.strip_chars,
        }

    # -- reading -------------------------------------------------------

    def _ordered_substitutions(self) -> tuple[tuple[str, str], ...]:
        """Return substitutions longest-key-first, then alphabetically.

        Longest-first is what keeps a multi-character key from being
        shadowed by a shorter one that happens to be its prefix.
        """
        return tuple(
            sorted(
                self.substitutions.items(),
                key=lambda kv: (-len(kv[0]), kv[0]),
            )
        )

    def _substitute(self, text: str) -> str:
        """Apply the substitutions, longest key first."""
        for key, value in self._ordered_substitutions():
            if key in text:
                text = text.replace(key, value)
        return text

    def _strip(self, text: str) -> str:
        """Remove the declared non-phonological characters."""
        if not self.strip_chars:
            return text
        return text.translate(str.maketrans("", "", self.strip_chars))

    def rewrite(self, text: str) -> str:
        """Apply the substitutions and strip characters from ``text``.

        Used for single strings; :meth:`expand` is the one to call
        for corpus cells, because it also splits.
        """
        if not isinstance(text, str):
            raise TypeError(
                f"rewrite expects str, got {type(text).__name__}"
            )
        return self._strip(self._substitute(text))

    def expand(self, text: str) -> tuple[str, ...]:
        """Return the independent forms contained in ``text``.

        Substitutions are applied first, over the whole string, so
        that a rewrite cannot be defeated by a split boundary.
        Splitting comes next, and stripping last, per piece — so that
        a character declared both as a separator and as strippable
        separates forms rather than fusing them.

        Returns
        -------
        tuple of str
            Zero or more forms. An empty string, or a string that is
            nothing but separators, yields ``()``.
        """
        if not isinstance(text, str):
            raise TypeError(
                f"expand expects str, got {type(text).__name__}"
            )
        text = self._substitute(text)
        pieces = (
            re.split(self.split, text) if self.split else [text]
        )
        out: list[str] = []
        for piece in pieces:
            piece = self._strip(piece).strip()
            if piece:
                out.append(piece)
        return tuple(out)


def load_profile(path: str | Path) -> Profile:
    """Read a profile from a YAML file.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to a YAML document describing a profile.

    Raises
    ------
    DataFormatError
        If the file is missing, is not valid YAML, does not hold a
        mapping, or contains unknown keys.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DataFormatError(
            f"Cannot read profile {path}: {exc}"
        ) from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise DataFormatError(
            f"Profile {path} is not valid YAML: {exc}"
        ) from exc
    if data is None:
        raise DataFormatError(f"Profile {path} is empty")
    return Profile.from_mapping(data)
