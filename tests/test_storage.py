"""Tests for phonfeat.storage."""

import pytest

from lingcore import FeatureKind, Value

from phonfeat import errors
from phonfeat.storage import (
    BUILTIN_FEATURE_SYSTEMS,
    BUILTIN_SYMBOL_TABLES,
    FeatureModel,
    SymbolTable,
    load_feature_model,
    load_symbol_table,
)


class TestLoadBuiltinFeatureModel:
    @pytest.mark.parametrize("name", BUILTIN_FEATURE_SYSTEMS)
    def test_loads(self, name: str) -> None:
        model = load_feature_model(name)
        assert isinstance(model, FeatureModel)
        assert model.system.name == name
        assert len(model) > 0

    def test_panphon_specifics(self) -> None:
        model = load_feature_model("panphon")
        assert model.system.name == "panphon"
        assert len(model) >= 5000
        assert "p" in model
        assert "a" in model
        assert "qˤː" in model

    def test_hayes_specifics(self) -> None:
        model = load_feature_model("hayes")
        assert model.system.name == "hayes"
        assert len(model) >= 100
        assert "p" in model
        assert "a" in model

    def test_unknown_builtin_raises(self) -> None:
        with pytest.raises(errors.DataFormatError, match="Unknown"):
            load_feature_model("nonexistent")

    def test_cached(self) -> None:
        a = load_feature_model("panphon")
        b = load_feature_model("panphon")
        assert a is b

    def test_segment_has_values(self) -> None:
        model = load_feature_model("hayes")
        p = model["p"]
        # Hayes uses "voice" as canonical name.
        assert "voice" in p.values
        assert p.values["voice"] == Value("-")

    def test_segment_has_type(self) -> None:
        model = load_feature_model("hayes")
        assert model["p"].type == "consonant"
        assert model["a"].type == "vowel"


class TestLoadSymbolTable:
    @pytest.mark.parametrize("name", BUILTIN_SYMBOL_TABLES)
    def test_loads(self, name: str) -> None:
        table = load_symbol_table(name)
        assert isinstance(table, SymbolTable)
        assert table.notation == name
        assert len(table) > 0

    def test_ipa_lookup(self) -> None:
        table = load_symbol_table("ipa")
        assert table.canonical_for("p") == "p"
        assert table.canonical_for("t͡ʃ") == "t͡ʃ"

    def test_xsampa_lookup(self) -> None:
        table = load_symbol_table("xsampa")
        assert table.canonical_for("p") == "p"
        assert table.canonical_for("tS") == "t͡ʃ"

    def test_missing_symbol_raises(self) -> None:
        table = load_symbol_table("ipa")
        with pytest.raises(KeyError):
            table.canonical_for("not-a-symbol")

    def test_unknown_builtin_raises(self) -> None:
        with pytest.raises(errors.DataFormatError, match="Unknown"):
            load_symbol_table("nonexistent")

    def test_cached(self) -> None:
        a = load_symbol_table("ipa")
        b = load_symbol_table("ipa")
        assert a is b


class TestLoadFromPath:
    def test_minimal_feature_model(self, tmp_path) -> None:
        yaml_content = """
schema_version: '1.1'
name: toy
version: '0.1.0'
features:
  - name: voi
  - name: nas
phones:
  - ipa: p
    type: consonant
    features:
      voi: false
      nas: false
  - ipa: b
    type: consonant
    features:
      voi: true
      nas: false
""".strip()
        path = tmp_path / "toy.feature.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        model = load_feature_model(path)
        assert model.system.name == "toy"
        assert len(model) == 2
        assert model["p"].values["voi"] == Value("-")
        assert model["b"].values["voi"] == Value("+")

    def test_minimal_symbol_table(self, tmp_path) -> None:
        yaml_content = """
schema_version: '1.1'
notation: ipa
symbols:
  - symbol: p
    canonical: p
  - symbol: b
    canonical: b
""".strip()
        path = tmp_path / "toy.symbols.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        table = load_symbol_table(path)
        assert table.notation == "ipa"
        assert table.canonical_for("p") == "p"

    def test_undeclared_feature_raises(self, tmp_path) -> None:
        yaml_content = """
name: toy
version: '0.1.0'
features:
  - name: voi
phones:
  - ipa: p
    type: consonant
    features:
      voi: false
      nas: false
""".strip()
        path = tmp_path / "toy.feature.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(
            errors.DataFormatError, match="not a declared feature"
        ):
            load_feature_model(path)

    def test_non_canonical_ipa_raises(self, tmp_path) -> None:
        yaml_content = """
name: toy
version: '0.1.0'
features:
  - name: voi
phones:
  - ipa: g
    type: consonant
    features:
      voi: true
""".strip()
        path = tmp_path / "toy.feature.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(
            errors.DataFormatError, match="not in canonical form"
        ):
            load_feature_model(path)

    def test_unknown_type_raises(self, tmp_path) -> None:
        yaml_content = """
name: toy
version: '0.1.0'
features:
  - name: voi
phones:
  - ipa: p
    type: click
    features:
      voi: false
""".strip()
        path = tmp_path / "toy.feature.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(
            errors.DataFormatError, match="unknown type"
        ):
            load_feature_model(path)

    def test_missing_required_key_raises(self, tmp_path) -> None:
        yaml_content = """
name: toy
features:
  - name: voi
phones: []
""".strip()
        path = tmp_path / "toy.feature.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(
            errors.DataFormatError, match="missing required key"
        ):
            load_feature_model(path)


class TestClassificationTags:
    def test_panphon_has_tags(self) -> None:
        model = load_feature_model("panphon")
        tags = model.classification_tags("p")
        assert "vls" in tags
        assert "blb" in tags
        assert "stp" in tags

    def test_missing_symbol_raises(self) -> None:
        model = load_feature_model("panphon")
        with pytest.raises(KeyError):
            model.classification_tags("not-a-phone")

    def test_classifications_groups_by_classifier(self) -> None:
        model = load_feature_model("panphon")
        groups = model.classifications("p")
        assert "voicing" in groups
        assert "vls" in groups["voicing"]
        assert "place" in groups
        assert "blb" in groups["place"]
        assert "manner" in groups
        assert "stp" in groups["manner"]

    def test_multi_valued_manner(self) -> None:
        # [s] is both sibilant and fricative.
        model = load_feature_model("panphon")
        groups = model.classifications("s")
        assert "manner" in groups
        manner = groups["manner"]
        assert "sib" in manner
        assert "frc" in manner


class TestSchemaVersion:
    def test_future_version_rejected(self, tmp_path) -> None:
        yaml_content = """
schema_version: '99.0'
name: toy
version: '0.1.0'
features:
  - name: voi
phones: []
""".strip()
        path = tmp_path / "toy.feature.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(
            errors.DataFormatError, match="schema_version"
        ):
            load_feature_model(path)

    def test_past_version_rejected(self, tmp_path) -> None:
        yaml_content = """
schema_version: '1.0'
name: toy
version: '0.1.0'
features:
  - name: voi
phones: []
""".strip()
        path = tmp_path / "toy.feature.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(
            errors.DataFormatError, match="schema_version"
        ):
            load_feature_model(path)

    def test_absent_version_accepted(self, tmp_path) -> None:
        yaml_content = """
name: toy
version: '0.1.0'
features:
  - name: voi
phones: []
""".strip()
        path = tmp_path / "toy.feature.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        model = load_feature_model(path)
        assert model.system.name == "toy"
