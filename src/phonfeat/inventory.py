"""An inventory: segments, categories, features and a tokenizer.

An inventory answers one question: what does this study consider a
sound, and what is known about each one? It bundles the segments a
feature table describes, the categories they fall into when the table
is class-structured, the numeric feature matrix, and the tokenizer that
turns a written form into segments.

It deliberately stops there. It does not know which corpora exist, how
far apart two segments are, or what to do with a symbol it cannot
describe: those are the caller's questions, and in this family of
packages they are ``lingaligner``'s.

Encoding of feature values
--------------------------
Cells are floats, and ``+`` is 1.0, ``-`` is 0.0, and anything else --
a missing value, ``0``, a third state such as ``±`` -- is ``NaN``. The
choice is deliberate: a feature table assembled from someone's
spreadsheet may carry a value this package has no reading for, and
aborting the whole inventory over one cell would be worse than marking
it undefined and counting it in :meth:`describe`. ``lingcore``'s
encoder raises instead, which is right for the bundled data files and
wrong here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import numpy as np
from lingcore import FeatureMatrix, Segment

from .errors import DataFormatError
from .profile import Profile
from .storage import FeatureModel
from .tokenize import tokenize as tokenize_text

__all__ = ["Inventory"]

_ENCODING = {"+": 1.0, "-": 0.0}


@dataclass(frozen=True, slots=True)
class Inventory:
    """The segments of one study, with their features and a tokenizer.

    Parameters
    ----------
    segments : sequence of Segment or str, optional
        The inventory's segments. A bare string becomes a segment typed
        ``"other"``. When omitted, the segments are the phones of
        ``model``, or the row labels of ``features``.
    features : lingcore.FeatureMatrix, optional
        Segments by features. When omitted and ``model`` is given, it
        is built from the model.
    categories : mapping, optional
        ``{category_name: symbols}``. Empty means a single undivided
        inventory. Symbols must be segments of this inventory and may
        appear in at most one category.
    notation : str, optional
        ``"ipa"`` (the default) or ``"xsampa"``; the notation in which
        forms are written.
    profile : Profile, optional
        How the strings of a corpus are rewritten and split before
        tokenizing.
    model : FeatureModel, optional
        The feature system the inventory was built from. Kept so that
        tokenizing can type its segments, and so a caller can ask which
        features exist.

    Raises
    ------
    DataFormatError
        If symbols repeat, if ``categories`` names a symbol the
        inventory does not hold, if a symbol appears in two categories,
        or if ``features`` rows do not match the segments.

    Notes
    -----
    Instances are immutable, and the nested mappings are read-only
    views. Nothing here is loaded from disk: build an inventory with
    :meth:`from_feature_model`, or hand one the pieces already loaded.
    """

    segments: Sequence[Segment | str] = ()
    features: FeatureMatrix | None = None
    categories: Mapping[str, Sequence[str]] = field(default_factory=dict)
    notation: str = "ipa"
    profile: Profile | None = None
    model: FeatureModel | None = None

    def __post_init__(self) -> None:
        segments: list[Segment] = [
            segment
            if isinstance(segment, Segment)
            else Segment(symbol=str(segment), type="other")
            for segment in self.segments
        ]
        if not segments:
            if self.model is not None:
                segments = [
                    self.model[symbol] for symbol in self.model.symbols()
                ]
            elif self.features is not None:
                segments = [
                    Segment(symbol=symbol, type="other")
                    for symbol in self.features.segment_ids
                ]
        symbols = tuple(segment.symbol for segment in segments)
        duplicates = sorted(
            {symbol for symbol in symbols if symbols.count(symbol) > 1}
        )
        if duplicates:
            raise DataFormatError(
                f"duplicate segment symbols in the inventory: {duplicates}"
            )
        features = self.features
        if features is None and self.model is not None:
            features = _feature_matrix(segments, self.model)
        elif features is not None and tuple(features.segment_ids) != symbols:
            raise DataFormatError(
                "feature matrix rows do not match the segments: "
                f"{list(features.segment_ids)} against {list(symbols)}"
            )
        object.__setattr__(self, "segments", tuple(segments))
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "categories", _freeze_categories(
            self.categories, symbols
        ))

    @classmethod
    def from_feature_model(
        cls,
        model: FeatureModel,
        *,
        notation: str = "ipa",
        profile: Profile | None = None,
        group_by_type: bool = False,
    ) -> Inventory:
        """Build an inventory from a feature model.

        Parameters
        ----------
        model : FeatureModel
            The feature table, with its phones.
        notation : str, optional
            ``"ipa"`` (the default) or ``"xsampa"``.
        profile : Profile, optional
            How to read a corpus's strings.
        group_by_type : bool, optional
            When true, each segment type the model uses becomes a
            category, so a distance can treat classes differently.
            Defaults to false: one undivided inventory, which is the
            state that claims least.

        Returns
        -------
        Inventory
            Segments, features and, if asked, categories.
        """
        categories: Mapping[str, Sequence[str]] = {}
        if group_by_type:
            grouped: dict[str, list[str]] = {}
            for symbol in model.symbols():
                grouped.setdefault(model[symbol].type, []).append(symbol)
            categories = {name: tuple(v) for name, v in grouped.items()}
        return cls(
            notation=notation,
            profile=profile,
            model=model,
            categories=categories,
        )

    def __len__(self) -> int:
        return len(self.segments)

    @property
    def symbols(self) -> tuple[str, ...]:
        """The segment symbols, in inventory order."""
        return tuple(segment.symbol for segment in self.segments)

    def tokenize(self, text: str) -> tuple[Segment, ...]:
        """Split one written form into segments.

        Parameters
        ----------
        text : str
            A form in this inventory's notation.

        Returns
        -------
        tuple of lingcore.Segment
            One segment per phone, in order, typed from the model when
            there is one.

        Raises
        ------
        TokenizationError
            If some part of ``text`` does not match any symbol.
        """
        if self.profile is None:
            return tokenize_text(text, self.notation, model=self.model)
        segments: list[Segment] = []
        for form in self.profile.expand(text):
            segments.extend(
                tokenize_text(form, self.notation, model=self.model)
            )
        return tuple(segments)

    def describe(self) -> dict[str, Any]:
        """Return what this inventory holds.

        Returns
        -------
        dict
            Segment count and type counts, categories, feature count,
            and how many cells are undefined -- in total and per
            feature, because a feature that is undefined for most
            segments is either a class-specific feature or a mistake,
            and the count is what tells them apart.
        """
        types: dict[str, int] = {}
        for segment in self.segments:
            types[segment.type] = types.get(segment.type, 0) + 1
        described: dict[str, Any] = {
            "segments": len(self.segments),
            "types": types,
            "categories": {
                name: len(symbols)
                for name, symbols in self.categories.items()
            },
            "notation": self.notation,
            "profile": (
                self.profile.description if self.profile is not None else None
            ),
            "features": None,
            "undefined_cells": None,
            "undefined_by_feature": None,
        }
        if self.features is not None:
            data = self.features.data
            undefined = np.isnan(data)
            described["features"] = len(self.features.feature_names)
            described["undefined_cells"] = int(undefined.sum())
            described["undefined_by_feature"] = {
                name: int(column.sum())
                for name, column in zip(
                    self.features.feature_names, undefined.T, strict=True
                )
            }
        return described

    def render(self) -> str:
        """Return :meth:`describe` as a short readable report."""
        report = self.describe()
        shapes = ", ".join(
            f"{name} {count}" for name, count in report["types"].items()
        )
        lines = [
            f"segments    {report['segments']} ({shapes or 'untyped'})",
            f"categories  {report['categories'] or 'none'}",
            f"notation    {report['notation']}",
        ]
        if report["features"] is None:
            lines.append("features    none")
        else:
            lines.append(
                f"features    {report['features']} columns, "
                f"{report['undefined_cells']} undefined cells"
            )
            undefined = report["undefined_by_feature"]
            worst = sorted(
                undefined.items(), key=lambda item: -item[1]
            )[:3]
            if worst and worst[0][1]:
                lines.append(
                    "  undefined "
                    + ", ".join(f"{name} {count}" for name, count in worst)
                )
        if report["profile"]:
            lines.append(f"profile     {report['profile']}")
        return "\n".join(lines)


def _feature_matrix(
    segments: Sequence[Segment],
    model: FeatureModel,
) -> FeatureMatrix:
    """Build the numeric feature matrix of ``segments`` under ``model``."""
    names = model.system.names()
    data = np.full((len(segments), len(names)), np.nan, dtype=float)
    for row, segment in enumerate(segments):
        for column, name in enumerate(names):
            value = segment.values.get(name)
            if value is not None:
                data[row, column] = _ENCODING.get(value.name, np.nan)
    return FeatureMatrix(
        segment_ids=tuple(segment.symbol for segment in segments),
        feature_names=names,
        data=data,
    )


def _freeze_categories(
    categories: Mapping[str, Sequence[str]],
    symbols: Sequence[str],
) -> Mapping[str, tuple[str, ...]]:
    """Validate and freeze a category mapping."""
    known = set(symbols)
    owner: dict[str, str] = {}
    frozen: dict[str, tuple[str, ...]] = {}
    for name, members in categories.items():
        members = tuple(members)
        unknown = sorted(set(members) - known)
        if unknown:
            raise DataFormatError(
                f"category {name!r} names symbols the inventory does "
                f"not hold: {unknown}"
            )
        for symbol in members:
            if symbol in owner:
                raise DataFormatError(
                    f"symbol {symbol!r} is in both {owner[symbol]!r} "
                    f"and {name!r}"
                )
            owner[symbol] = name
        frozen[name] = members
    return MappingProxyType(frozen)
