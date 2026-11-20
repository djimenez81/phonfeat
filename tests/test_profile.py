"""Tests for phonfeat.profile."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from phonfeat import DataFormatError, NotationError, Profile, load_profile

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "profiles"


# ---------------------------------------------------------------------
# Defaults: a profile that reads the corpus literally
# ---------------------------------------------------------------------


def test_default_profile_is_literal():
    profile = Profile()
    assert profile.notation == "ipa"
    assert dict(profile.substitutions) == {}
    assert profile.split is None
    assert profile.strip_chars == ""
    assert profile.expand("ni-aʔ") == ("ni-aʔ",)


def test_default_profile_keeps_multi_word_cells_whole():
    assert Profile().expand("ikan abu-abu") == ("ikan abu-abu",)


def test_from_mapping_with_minimum_keys():
    profile = Profile.from_mapping({})
    assert profile.notation == "ipa"


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------


def test_unknown_notation_is_rejected():
    with pytest.raises(NotationError):
        Profile(notation="sampa")


def test_unknown_key_is_rejected():
    with pytest.raises(DataFormatError, match="Unknown profile key"):
        Profile.from_mapping({"notation": "ipa", "substitusions": {}})


def test_non_mapping_is_rejected():
    with pytest.raises(DataFormatError):
        Profile.from_mapping(["notation", "ipa"])


def test_substitution_to_itself_is_rejected():
    with pytest.raises(DataFormatError, match="to itself"):
        Profile(substitutions={"a": "a"})


def test_empty_substitution_value_is_rejected():
    with pytest.raises(DataFormatError):
        Profile(substitutions={"a": ""})


def test_empty_substitution_key_is_rejected():
    with pytest.raises(DataFormatError):
        Profile(substitutions={"": "a"})


def test_invalid_split_regex_is_rejected():
    with pytest.raises(DataFormatError, match="regular expression"):
        Profile(split="[unclosed")


def test_empty_split_is_rejected():
    with pytest.raises(DataFormatError):
        Profile(split="")


def test_strip_chars_must_be_a_string():
    with pytest.raises(DataFormatError):
        Profile(strip_chars=None)


def test_profile_is_frozen():
    profile = Profile()
    with pytest.raises(Exception):
        profile.notation = "xsampa"


def test_substitutions_are_read_only():
    profile = Profile(substitutions={"ñ": "ɲ"})
    with pytest.raises(TypeError):
        profile.substitutions["x"] = "y"


def test_substitutions_are_copied_out_of_the_caller_mapping():
    source = {"ñ": "ɲ"}
    profile = Profile(substitutions=source)
    source["ñ"] = "n"
    assert profile.substitutions["ñ"] == "ɲ"


# ---------------------------------------------------------------------
# Substitution
# ---------------------------------------------------------------------


def test_substitution_is_applied():
    profile = Profile(substitutions={"ñ": "ɲ"})
    assert profile.rewrite("ñak") == "ɲak"


def test_substitution_applies_everywhere_in_the_string():
    profile = Profile(substitutions={"ñ": "ɲ"})
    assert profile.rewrite("ñamñam") == "ɲamɲam"


def test_longest_substitution_key_wins():
    profile = Profile(substitutions={"a": "X", "ab": "Y"})
    assert profile.rewrite("ab") == "Y"


def test_shorter_key_does_not_shadow_longer_one_in_context():
    profile = Profile(substitutions={"a": "X", "ab": "Y"})
    assert profile.rewrite("zabz") == "zYz"


def test_no_substitution_leaves_text_alone():
    assert Profile().rewrite("mata") == "mata"


# ---------------------------------------------------------------------
# Expansion
# ---------------------------------------------------------------------


def test_split_separates_forms():
    profile = Profile(split=r"[\s,;]+")
    assert profile.expand("bacok, bacuk") == ("bacok", "bacuk")


def test_split_then_strip_keeps_forms_apart():
    profile = Profile(split=r"[\s,-]+", strip_chars="-")
    assert profile.expand("ni-a") == ("ni", "a")


def test_strip_only_fuses_hyphenated_forms():
    profile = Profile(strip_chars="-")
    assert profile.expand("ni-a") == ("nia",)


def test_empty_string_expands_to_nothing():
    assert Profile().expand("") == ()


def test_separator_only_string_expands_to_nothing():
    profile = Profile(split=r"[\s,;]+")
    assert profile.expand(" , ; ") == ()


def test_expand_rejects_non_string():
    with pytest.raises(TypeError):
        Profile().expand(None)


def test_substitution_applies_before_split():
    # a rewrite that introduces a separator must not be split apart:
    # the split runs on the rewritten text
    profile = Profile(split=r"\|", substitutions={"x": "|"})
    assert profile.expand("axb") == ("a", "b")


def test_expand_drops_surrounding_whitespace():
    profile = Profile(split=r",")
    assert profile.expand(" a , b ") == ("a", "b")


# ---------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------


def test_to_mapping_round_trips():
    profile = Profile(
        notation="xsampa",
        substitutions={"ñ": "J"},
        split=r"\s+",
        strip_chars="-",
        description="test",
    )
    assert Profile.from_mapping(profile.to_mapping()) == profile


def test_to_mapping_is_yaml_serializable():
    profile = Profile(substitutions={"ñ": "ɲ"}, split=r"\s+")
    assert yaml.safe_dump(profile.to_mapping())


# ---------------------------------------------------------------------
# Loading the shipped examples
# ---------------------------------------------------------------------


def test_load_example_cognado_profile():
    profile = load_profile(EXAMPLES / "cognados-orthography.yaml")
    assert profile.notation == "ipa"
    assert profile.substitutions["ñ"] == "ɲ"
    assert profile.strip_chars == "-"
    assert profile.expand("bacok, bacuk") == ("bacok", "bacuk")


def test_load_example_swadesh_profile():
    profile = load_profile(EXAMPLES / "swadesh-xsampa.yaml")
    assert profile.notation == "xsampa"
    assert profile.substitutions["ñ"] == "J"
    assert profile.expand("Kaxa:Ra Ku:tu iNa:Ne") == (
        "Kaxa:Ra",
        "Ku:tu",
        "iNa:Ne",
    )


def test_load_missing_profile_raises():
    with pytest.raises(DataFormatError, match="Cannot read profile"):
        load_profile(EXAMPLES / "absent.yaml")


def test_load_empty_profile_raises(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(DataFormatError, match="empty"):
        load_profile(path)


def test_load_malformed_yaml_raises(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("notation: [unclosed\n", encoding="utf-8")
    with pytest.raises(DataFormatError, match="not valid YAML"):
        load_profile(path)


def test_load_profile_with_unknown_key_raises(tmp_path):
    path = tmp_path / "extra.yaml"
    path.write_text("notation: ipa\ntones: keep\n", encoding="utf-8")
    with pytest.raises(DataFormatError, match="Unknown profile key"):
        load_profile(path)
