"""Measuring what a corpus requires before trusting anything derived from it.

``phonfeat`` does not read files. A corpus, for this package, is a
list of strings; how those strings were extracted from a spreadsheet,
a Python literal or a text dump is the caller's business. What the
package does owe the caller is an honest account of what happened when
they were tokenized, because the failure mode here is quiet: a corpus
written in practical orthography tokenizes cleanly — every character
is a valid IPA symbol — and yields a plausible, wrong inventory with
no error raised anywhere.

:func:`survey` produces that account and nothing more. It reports
measurable facts:

* how many forms were given, and how many were produced after a
  :class:`~phonfeat.profile.Profile` was applied,
* how many tokenized, and, for the rest, the character and examples
  that stopped them, ranked by frequency,
* which characters the symbol table cannot consume at all, which is
  the list a profile needs to address,
* the inventory that came out, with frequencies,
* and, when a feature model is supplied, how much of it the model can
  describe — split into exact matches, base-only matches (the stacked
  form is absent, its base is present — what happens to every tone-
  bearing vowel) and nothing at all.

It does not judge the transcription. Deciding that ``c`` in an
Austronesian wordlist means ``t͡ʃ`` needs to know the family; a package
that guessed would be wrong exactly when it mattered. The survey puts
the evidence in front of the reader — the full inventory, the rare
segments, the type distribution — and the :class:`Profile` records
the conclusion. See ``docs/decisions.md`` D25.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Mapping

from .canonicalize import normalize_for_matching
from .errors import NotationError, TokenizationError
from .profile import Profile
from .storage import FeatureModel, load_feature_model

# ``_PROSODIC``, ``_match`` and ``_matching_tables`` are the
# tokenizer's own matching machinery. Survey reuses them on purpose: a
# second, independent matcher could disagree with ``tokenize`` about
# what a corpus contains, which would make the report a description of
# the wrong algorithm.
from .tokenize import _PROSODIC, _match, _matching_tables, tokenize

__all__ = ["Blocker", "SurveyReport", "survey"]


#: Unicode categories treated as marks rather than as the base of a
#: phone. ``Lm`` matters as much as ``Mn``: length (``ː``),
#: aspiration (``ʰ``) and tone letters written as letters are all
#: modifier letters, and a feature table lists none of them.
_MARK_CATEGORIES = frozenset({"Mn", "Me", "Lm"})


def _plural(count: int, word: str) -> str:
    """Return ``"1 form"`` / ``"2,000 forms"``."""
    return f"{count:,} {word}" + ("" if count == 1 else "s")


@lru_cache(maxsize=None)
def _base(symbol: str) -> str:
    """Return ``symbol`` with its marks and modifier letters removed.

    Used only to ask a feature model a second question: "you do not
    list this segment, but do you list its base?". The answer is
    cached because it is asked once per distinct segment, not once
    per token.
    """
    stripped = "".join(
        char
        for char in unicodedata.normalize("NFD", symbol)
        if unicodedata.category(char) not in _MARK_CATEGORIES
    )
    stripped = unicodedata.normalize("NFC", stripped)
    return stripped or symbol


@dataclass(frozen=True)
class Blocker:
    """One character that stopped tokenization, and how often.

    Parameters
    ----------
    char : str
        The character that matched no symbol in the table.
    count : int
        Number of forms in which it was the first such character.
    examples : tuple of str
        Up to a few forms containing it, verbatim, for inspection.
    """

    char: str
    count: int
    examples: tuple[str, ...] = ()

    @property
    def codepoint(self) -> str:
        """Return the character's code point, e.g. ``"U+00F1"``."""
        return f"U+{ord(self.char):04X}"


@dataclass(frozen=True)
class SurveyReport:
    """What a corpus looks like once tokenized.

    Parameters
    ----------
    notation : str
        The notation the forms were read in.
    source_forms : int
        Number of strings given to :func:`survey`.
    forms : int
        Number of forms after the profile expanded them. Equal to
        ``source_forms`` when no profile splits anything.
    tokenized : int
        Number of forms that tokenized without error.
    tokens : int
        Total segments produced.
    blockers : tuple of Blocker
        Characters that stopped tokenization, most frequent first.
    segments : Mapping of str to int
        Segment symbol to token count.
    unmatched : Mapping of str to int
        Characters the symbol table cannot consume, with the number
        of forms containing them. A superset of ``blockers``: it also
        lists characters appearing in forms that failed earlier or
        later.
    described : Mapping of str to int, optional
        Segments the feature model lists, with token counts. ``None``
        when no model was supplied.
    base_only : Mapping of str to int, optional
        Segments the model does not list but whose base it does.
    undescribed : Mapping of str to int, optional
        Segments with no row in the model at all, neither directly
        nor through their base.
    types : Mapping of str to int, optional
        Segment type to token count, as assigned during tokenization.
    profile : Profile, optional
        The profile applied, if any.
    """

    notation: str
    source_forms: int
    forms: int
    tokenized: int
    tokens: int
    blockers: tuple[Blocker, ...] = ()
    segments: Mapping[str, int] = field(default_factory=dict)
    unmatched: Mapping[str, int] = field(default_factory=dict)
    described: Mapping[str, int] | None = None
    base_only: Mapping[str, int] | None = None
    undescribed: Mapping[str, int] | None = None
    types: Mapping[str, int] | None = None
    profile: Profile | None = None

    @property
    def failed(self) -> int:
        """Number of forms that did not tokenize."""
        return self.forms - self.tokenized

    @property
    def coverage(self) -> float:
        """Fraction of forms that tokenized, in ``[0, 1]``."""
        return self.tokenized / self.forms if self.forms else 0.0

    def render(self) -> str:
        """Return a human-readable report, stable across runs."""
        lines: list[str] = []
        header = f"survey: {self.notation}"
        if self.profile is not None:
            header += f" · profile: {self._describe_profile()}"
        lines.append(header)

        if self.forms != self.source_forms:
            lines.append(
                f"  {self.source_forms:,} strings given "
                f"→ {self.forms:,} forms after expansion"
            )
        lines.append(
            f"  tokenized {self.tokenized:,} / {self.forms:,} forms "
            f"({100 * self.coverage:.1f}%), {self.tokens:,} tokens"
        )

        if self.blockers:
            lines.append(f"  blockers ({len(self.blockers)}):")
            for blocker in self.blockers:
                examples = ", ".join(
                    repr(e) for e in blocker.examples
                )
                lines.append(
                    f"    {blocker.char!r} {blocker.codepoint}  "
                    f"{_plural(blocker.count, 'form')}   "
                    f"e.g. {examples}"
                )
        elif self.forms:
            lines.append("  blockers: none")

        if self.unmatched:
            listed = ", ".join(
                f"{char!r}({count:,})"
                for char, count in sorted(
                    self.unmatched.items(),
                    key=lambda kv: (-kv[1], kv[0]),
                )
            )
            lines.append(
                f"  characters the {self.notation} table cannot "
                f"consume: {listed}"
            )
            lines.append(
                "    → declare them in a profile's substitutions to "
                "read them"
            )

        lines.append(
            f"  inventory: {len(self.segments)} distinct segments"
        )
        if self.segments:
            top = ", ".join(
                f"{symbol}({count:,})"
                for symbol, count in self._ranked(self.segments)[:25]
            )
            lines.append(f"    {top}")

        if self.described is not None:
            lines.extend(self._render_feature_coverage())

        return "\n".join(lines)

    def __str__(self) -> str:
        return self.render()

    # -- internals -----------------------------------------------------

    @staticmethod
    def _ranked(
        mapping: Mapping[str, int], limit: int | None = None
    ) -> list[tuple[str, int]]:
        """Sort a frequency mapping by count, then symbol."""
        items = sorted(mapping.items(), key=lambda kv: (-kv[1], kv[0]))
        return items if limit is None else items[:limit]

    def _describe_profile(self) -> str:
        profile = self.profile
        if profile is None:
            return ""
        parts = []
        if profile.substitutions:
            parts.append(
                f"{len(profile.substitutions)} substitution(s)"
            )
        if profile.split:
            parts.append(f"split=/{profile.split}/")
        if profile.strip_chars:
            parts.append(f"strip={profile.strip_chars!r}")
        if not parts:
            parts.append("read literally")
        return ", ".join(parts)

    def _render_feature_coverage(self) -> list[str]:
        described = self.described or {}
        base_only = self.base_only or {}
        undescribed = self.undescribed or {}
        total = self.tokens or 1
        lines = [
            "  feature coverage:",
            f"    described   {sum(described.values()):,} tokens "
            f"({100 * sum(described.values()) / total:.1f}%)",
            f"    base-only   {sum(base_only.values()):,} tokens "
            f"({100 * sum(base_only.values()) / total:.1f}%)",
            f"    undescribed {sum(undescribed.values()):,} tokens "
            f"({100 * sum(undescribed.values()) / total:.1f}%)",
        ]
        if base_only:
            # Where tone, nasalization and misread letters land: the
            # marked form is not in the table, its base is. A large
            # share here is worth reading before anything is claimed.
            top = ", ".join(
                f"{symbol}({count:,})"
                for symbol, count in self._ranked(base_only)[:15]
            )
            lines.append(f"    base-only: {top}")
        if undescribed:
            top = ", ".join(
                f"{symbol}({count:,})"
                for symbol, count in self._ranked(undescribed)[:15]
            )
            lines.append(f"    missing: {top}")
        if self.types:
            listed = ", ".join(
                f"{kind} {100 * count / total:.0f}%"
                for kind, count in self._ranked(self.types)
            )
            lines.append(f"    types: {listed}")
        return lines


def _resolve_model(model: str | FeatureModel | None) -> FeatureModel | None:
    """Accept a model, a builtin name, or ``None``."""
    if model is None:
        return None
    if isinstance(model, str):
        return load_feature_model(model)
    return model


def _unmatched_in(text: str, pairs: tuple[tuple[str, str], ...]) -> list[str]:
    """Return the characters of ``text`` the table cannot consume.

    A greedy longest-match walk, the same one the tokenizer performs,
    except that a character which matches nothing is recorded and
    skipped instead of raising. This finds every offender in a form,
    not just the first — which matters because a profile has to
    address all of them at once.
    """
    found: list[str] = []
    position = 0
    while position < len(text):
        matched = _match(pairs, text, position)
        if matched is None:
            found.append(text[position])
            position += 1
        else:
            position += len(matched[0])
    return found


def _rank_dict(counter: Counter[str]) -> dict[str, int]:
    """Return a frequency counter as a dict, most frequent first."""
    return {
        symbol: count
        for symbol, count in sorted(
            counter.items(), key=lambda kv: (-kv[1], kv[0])
        )
    }


def survey(
    forms: Iterable[str],
    notation: str | None = None,
    *,
    profile: Profile | None = None,
    model: str | FeatureModel | None = None,
    examples: int = 3,
) -> SurveyReport:
    """Tokenize a corpus and report what happened.

    Parameters
    ----------
    forms : Iterable of str
        The corpus. Each string is one entry; splitting a cell that
        holds several forms is the profile's job.
    notation : str, optional
        ``"ipa"`` or ``"xsampa"``. May be omitted when ``profile``
        is given, in which case the profile's notation is used.
    profile : Profile, optional
        How to read the corpus. Without one, every string is read
        literally.
    model : str or FeatureModel, optional
        Feature model used both to type the segments and to measure
        coverage. Pass a builtin name (``"panphon"``, ``"hayes"``) or
        a loaded model. Omitted means no typing and no coverage
        numbers. Note that ``"panphon"`` costs a few seconds and a
        couple of hundred megabytes on first load.
    examples : int, optional
        How many verbatim examples to keep per blocker. Defaults to
        3.

    Returns
    -------
    SurveyReport

    Raises
    ------
    TypeError
        If a form is not a string.
    NotationError
        If the notation is unknown, or if ``notation`` and
        ``profile.notation`` disagree.

    Notes
    ------
    Failures are data here, not exceptions: a corpus with a stray
    quote in one row and an unknown character in sixty cells produces
    a report, so that the report can be read before anything is
    decided. Use :func:`~phonfeat.tokenize` directly when a single
    string must either tokenize or raise.
    """
    if profile is not None:
        if notation is not None and notation != profile.notation:
            raise NotationError(
                f"survey was given notation={notation!r} and a "
                f"profile for {profile.notation!r}"
            )
        notation = profile.notation
    if notation is None:
        notation = "ipa"
    if notation not in _PROSODIC:
        raise NotationError(
            f"Unknown notation {notation!r}; expected 'ipa' or "
            f"'xsampa'"
        )

    pairs, _ = _matching_tables(notation)
    resolved = _resolve_model(model)

    given = 0
    expanded: list[str] = []
    for form in forms:
        if not isinstance(form, str):
            raise TypeError(
                f"survey expects str entries, got "
                f"{type(form).__name__}"
            )
        given += 1
        pieces = profile.expand(form) if profile is not None else (form,)
        expanded.extend(piece for piece in pieces if piece)

    blockers: Counter[str] = Counter()
    blocker_examples: dict[str, list[str]] = {}
    unmatched: Counter[str] = Counter()
    segments: Counter[str] = Counter()
    types: Counter[str] = Counter()
    described: Counter[str] = Counter()
    base_only: Counter[str] = Counter()
    undescribed: Counter[str] = Counter()
    tokenized = 0
    tokens = 0

    for form in expanded:
        text = normalize_for_matching(form, notation)
        offenders = _unmatched_in(text, pairs)
        for char in set(offenders):
            unmatched[char] += 1
        try:
            found = tokenize(text, notation, model=resolved)
        except TokenizationError:
            if not offenders:
                # The scan and the tokenizer use the same matcher, so
                # this cannot happen; if it ever does, the report
                # would be describing the wrong algorithm.
                raise
            char = offenders[0]
            blockers[char] += 1
            kept = blocker_examples.setdefault(char, [])
            if len(kept) < examples:
                kept.append(form)
            continue
        tokenized += 1
        tokens += len(found)
        for segment in found:
            segments[segment.symbol] += 1
            if resolved is None:
                types[segment.type] += 1
                continue
            types[segment.type] += 1
            if segment.symbol in resolved:
                described[segment.symbol] += 1
            elif _base(segment.symbol) in resolved:
                base_only[segment.symbol] += 1
            else:
                undescribed[segment.symbol] += 1

    order = sorted(blockers.items(), key=lambda kv: (-kv[1], kv[0]))
    return SurveyReport(
        notation=notation,
        source_forms=given,
        forms=len(expanded),
        tokenized=tokenized,
        tokens=tokens,
        blockers=tuple(
            Blocker(char, count, tuple(blocker_examples.get(char, ())))
            for char, count in order
        ),
        segments=_rank_dict(segments),
        unmatched=_rank_dict(unmatched),
        described=_rank_dict(described) if resolved is not None else None,
        base_only=_rank_dict(base_only) if resolved is not None else None,
        undescribed=(
            _rank_dict(undescribed) if resolved is not None else None
        ),
        types=_rank_dict(types) if resolved is not None else None,
        profile=profile,
    )
