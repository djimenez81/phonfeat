"""Inventories: segments, categories, features and a tokenizer."""

from __future__ import annotations

import numpy as np
import pytest
from lingcore import Feature, FeatureSystem, Segment, Value

from phonfeat import DataFormatError, Inventory, Profile
from phonfeat.storage import FeatureModel


def value(token: str) -> Value:
    return Value(token)


def model() -> FeatureModel:
    """Four phones over three features, with a class-structured hole."""
    system = FeatureSystem(
        name="test",
        version="0.1.0",
        features=(
            Feature("CLOSED"),
            Feature("ROUNDED"),
            Feature("VOICE"),
        ),
    )
    phones = {
        "a": Segment(
            symbol="a",
            type="vowel",
            values={
                "CLOSED": value("-"),
                "ROUNDED": value("-"),
                "VOICE": value("+"),
            },
        ),
        "i": Segment(
            symbol="i",
            type="vowel",
            values={
                "CLOSED": value("+"),
                "ROUNDED": value("-"),
                "VOICE": value("+"),
            },
        ),
        "k": Segment(
            symbol="k", type="consonant", values={"VOICE": value("-")}
        ),
        "t": Segment(
            symbol="t", type="consonant", values={"VOICE": value("-")}
        ),
    }
    return FeatureModel(system=system, phones=phones)


@pytest.fixture
def inventory():
    return Inventory.from_feature_model(model())


def test_segments_come_from_the_model(inventory):
    assert inventory.symbols == ("a", "i", "k", "t")
    assert len(inventory) == 4


def test_features_are_encoded(inventory):
    matrix = inventory.features
    assert matrix is not None
    assert matrix.feature_names == ("CLOSED", "ROUNDED", "VOICE")
    row = matrix.segment_ids.index("a")
    assert list(matrix.data[row]) == [0.0, 0.0, 1.0]


def test_a_missing_value_is_undefined(inventory):
    matrix = inventory.features
    assert matrix is not None
    row = matrix.segment_ids.index("k")
    assert np.isnan(matrix.data[row, 0])
    assert np.isnan(matrix.data[row, 1])
    assert matrix.data[row, 2] == 0.0


def test_a_value_the_package_cannot_read_is_undefined():
    system = FeatureSystem(
        name="test",
        version="0.1.0",
        features=(Feature("POSTERIOR"),),
    )
    phones = {
        "a": Segment(
            symbol="a", type="vowel", values={"POSTERIOR": value("±")}
        ),
        "o": Segment(
            symbol="o", type="vowel", values={"POSTERIOR": value("+")}
        ),
    }
    inventory = Inventory.from_feature_model(
        FeatureModel(system=system, phones=phones)
    )
    assert inventory.features is not None
    assert np.isnan(inventory.features.data[0, 0])
    assert inventory.features.data[1, 0] == 1.0
    assert inventory.describe()["undefined_cells"] == 1


def test_categories_are_absent_unless_asked_for(inventory):
    assert inventory.categories == {}


def test_categories_can_be_grouped_by_type():
    inventory = Inventory.from_feature_model(model(), group_by_type=True)
    assert dict(inventory.categories) == {
        "vowel": ("a", "i"),
        "consonant": ("k", "t"),
    }


def test_categories_naming_an_unknown_symbol_are_refused():
    with pytest.raises(DataFormatError, match="does not hold"):
        Inventory.from_feature_model(model()).__class__(
            segments=("a", "i"),
            categories={"C": ("zz",)},
        )


def test_a_symbol_may_not_be_in_two_categories():
    with pytest.raises(DataFormatError, match="both"):
        Inventory(segments=("a", "i"), categories={"A": ("a",), "B": ("a",)})


def test_duplicate_symbols_are_refused():
    with pytest.raises(DataFormatError, match="duplicate"):
        Inventory(segments=("a", "a"))


def test_features_must_match_the_segments(inventory):
    with pytest.raises(DataFormatError, match="do not match"):
        Inventory(segments=("a", "i"), features=inventory.features)


def test_tokenize_uses_the_model_for_types(inventory):
    segments = inventory.tokenize("ka")
    assert [segment.symbol for segment in segments] == ["k", "a"]
    assert [segment.type for segment in segments] == ["consonant", "vowel"]


def test_a_profile_rewrites_before_tokenizing():
    inventory = Inventory.from_feature_model(
        model(), profile=Profile(substitutions={"ñ": "ɲ"})
    )
    segments = inventory.tokenize("ña")
    assert [segment.symbol for segment in segments] == ["ɲ", "a"]


def test_a_profile_can_split_one_string_into_several_forms():
    inventory = Inventory.from_feature_model(
        model(), profile=Profile(split=r"[\s,]+")
    )
    segments = inventory.tokenize("ka, ta")
    assert [segment.symbol for segment in segments] == list("kata")


def test_an_inventory_without_features_still_tokenizes():
    inventory = Inventory(segments=("a", "i"))
    assert inventory.features is None
    symbols = [segment.symbol for segment in inventory.tokenize("ai")]
    assert symbols == ["a", "i"]


def test_describe_counts_what_is_undefined(inventory):
    described = inventory.describe()
    assert described["segments"] == 4
    assert described["types"] == {"vowel": 2, "consonant": 2}
    assert described["features"] == 3
    assert described["undefined_cells"] == 4
    assert described["undefined_by_feature"]["CLOSED"] == 2
    assert described["undefined_by_feature"]["VOICE"] == 0


def test_render_is_readable(inventory):
    text = inventory.render()
    assert "segments    4" in text
    assert "features    3 columns" in text


def test_the_inventory_is_immutable(inventory):
    with pytest.raises(AttributeError):
        inventory.notation = "xsampa"
    with pytest.raises(TypeError):
        inventory.categories["new"] = ()


def test_it_exposes_the_surface_the_aligner_needs(inventory):
    """The four members of lingaligner's InventoryLike protocol."""
    assert isinstance(inventory.segments, tuple)
    assert hasattr(inventory, "categories")
    assert hasattr(inventory, "features")
    assert callable(inventory.tokenize)
