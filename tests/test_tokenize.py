"""Tests for phonfeat.tokenize."""

from __future__ import annotations

import pytest

from phonfeat import (
    NotationError,
    TokenizationError,
    canonicalize_ipa,
    tokenize,
)
from phonfeat.tokenize import _matching_tables


def symbols(text: str, notation: str = "ipa") -> list[str]:
    """Return the symbols of a tokenization, for compact assertions."""
    return [segment.symbol for segment in tokenize(text, notation)]


# ---------------------------------------------------------------------
# Basic splitting
# ---------------------------------------------------------------------


def test_empty_string_yields_no_segments():
    assert tokenize("") == ()


def test_single_phone():
    assert symbols("a") == ["a"]


def test_simple_word():
    assert symbols("mata") == ["m", "a", "t", "a"]


def test_returns_segment_objects():
    segments = tokenize("pa")
    assert all(hasattr(s, "symbol") for s in segments)
    assert [s.type for s in segments] == ["other", "other"]


def test_classification_and_values_are_empty():
    (segment,) = tokenize("a")
    assert dict(segment.classification) == {}
    assert dict(segment.values) == {}


def test_segments_are_hashable():
    assert len({segment for segment in tokenize("pata")}) == 3


# ---------------------------------------------------------------------
# Maximal munch
# ---------------------------------------------------------------------


def test_tie_barred_affricate_is_one_segment():
    assert symbols("pat͡ʃka") == ["p", "a", "t͡ʃ", "k", "a"]


def test_tie_barred_affricate_at_start():
    assert symbols("t͡ʃa") == ["t͡ʃ", "a"]


def test_ejective_multi_char_symbol_is_one_segment():
    assert symbols("kʼa") == ["kʼ", "a"]


def test_ligature_is_deprecated_to_tie_barred_form():
    assert symbols("ʧata") == ["t͡ʃ", "a", "t", "a"]


def test_longest_match_wins_over_prefix():
    # "cʼ" prefixes "c"; the longer entry must win.
    assert symbols("cʼ") == ["cʼ"]


def test_dotted_syllable_break_is_its_own_segment():
    assert symbols("a.ta") == ["a", ".", "t", "a"]


# ---------------------------------------------------------------------
# Stacking
# ---------------------------------------------------------------------


def test_aspiration_attaches_to_previous_phone():
    assert symbols("kʰa") == ["kʰ", "a"]


def test_length_attaches_to_previous_phone():
    assert symbols("aː") == ["aː"]


def test_multiple_modifiers_attach_in_order():
    assert symbols("kʰːa")[0] == canonicalize_ipa("kʰː")


def test_modifier_does_not_create_a_segment():
    assert len(tokenize("aː")) == 1


def test_tone_bar_stays_separate():
    # PanPhon models tone as its own segment; a tone bar must not be
    # folded into the preceding vowel.
    assert symbols("a˧") == ["a", "˧"]


def test_stress_mark_is_its_own_segment():
    assert symbols("ˈmata") == ["ˈ", "m", "a", "t", "a"]


def test_stress_mark_does_not_attach_to_preceding_phone():
    assert symbols("maˈta") == ["m", "a", "ˈ", "t", "a"]


def test_modifier_with_no_base_becomes_its_own_segment():
    assert symbols("ⁿa") == ["ⁿ", "a"]


# ---------------------------------------------------------------------
# Canonicalization behavior
# ---------------------------------------------------------------------


def test_script_g_is_canonicalized():
    assert symbols("gato") == ["ɡ", "a", "t", "o"]


def test_diacritic_order_is_canonical_per_token():
    # Written low-then-long, canonical high... the point is that the
    # token comes back in canonical order.
    assert symbols("aːˤ") == [canonicalize_ipa("aˤː")]


def test_diacritics_do_not_move_across_phone_boundaries():
    # The whole-string canonicalizer would turn this into "bːad";
    # tokenizing must not.
    assert symbols("baːd") == ["b", "aː", "d"]


def test_xsampa_tone_diacritic_attaches():
    assert symbols("a_M", "xsampa") == ["a_M"]


# ---------------------------------------------------------------------
# X-SAMPA
# ---------------------------------------------------------------------


def test_xsampa_multi_char_symbols():
    assert symbols("patSka", "xsampa") == ["p", "a", "tS", "k", "a"]


def test_xsampa_voiceless_diacritic_stacks():
    assert symbols("ma_0ta", "xsampa") == ["m", "a_0", "t", "a"]


def test_xsampa_stress_mark_stands_alone():
    assert symbols('"mata', "xsampa") == ['"', "m", "a", "t", "a"]


# ---------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------


def test_types_default_to_other():
    assert {segment.type for segment in tokenize("pata")} == {"other"}


def test_types_resolved_from_hayes():
    segments = tokenize("pata", model="hayes")
    assert [segment.type for segment in segments] == [
        "consonant",
        "vowel",
        "consonant",
        "vowel",
    ]


def test_modified_phone_takes_its_base_type():
    # "aː" is not a phone in the model, but "a" is.
    (segment,) = tokenize("aː", model="hayes")
    assert segment.type == "vowel"


def test_unknown_type_when_model_lacks_the_phone():
    (segment,) = tokenize(".", model="hayes")
    assert segment.type == "other"


# ---------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------


def test_unknown_character_raises():
    with pytest.raises(TokenizationError):
        tokenize("aZ")


def test_error_reports_position_and_character():
    with pytest.raises(TokenizationError) as excinfo:
        tokenize("pa#ta")
    message = str(excinfo.value)
    assert "offset 2" in message
    assert "U+0023" in message


def test_unknown_notation_raises():
    with pytest.raises(NotationError):
        tokenize("a", "shavian")


def test_non_string_input_raises():
    with pytest.raises(TypeError):
        tokenize(b"a")


# ---------------------------------------------------------------------
# Matching tables
# ---------------------------------------------------------------------


def test_matching_tables_sorted_by_descending_length():
    pairs, _ = _matching_tables("ipa")
    lengths = [len(symbol) for symbol, _ in pairs]
    assert lengths == sorted(lengths, reverse=True)


def test_modifier_set_excludes_tone_bars():
    _, modifiers = _matching_tables("ipa")
    assert "ː" in modifiers
    assert "ʰ" in modifiers
    assert "˧" not in modifiers


def test_matching_tables_are_cached():
    assert _matching_tables("ipa") is _matching_tables("ipa")


# ---------------------------------------------------------------------
# Combining marks
#
# The symbol table lists bases and combining marks separately, because
# a diacritic stacks onto the phone it follows. That only works if the
# input reaches the matcher decomposed: composing it first would turn
# "a" + U+0303 into the single character "ã", which is no symbol in
# the table, and every tone- or nasalization-bearing vowel in a corpus
# would fail to tokenize.
# ---------------------------------------------------------------------


def test_precomposed_vowel_tokenizes():
    assert symbols("\u00e3") == ["\u00e3"]


def test_decomposed_vowel_tokenizes():
    assert symbols("a\u0303") == ["\u00e3"]


def test_precomposed_and_decomposed_agree():
    assert tokenize("\u00e3") == tokenize("a\u0303")


def test_acute_accent_tokenizes():
    assert symbols("\u00e1") == ["\u00e1"]
    assert symbols("e\u0301") == ["\u00e9"]


def test_combining_mark_stacks_onto_preceding_phone_only():
    assert symbols("k\u00e3ta") == ["k", "\u00e3", "t", "a"]


def test_several_marks_on_one_phone():
    segments = tokenize("a\u0303\u0301")
    assert len(segments) == 1
    # composed where Unicode allows it: ã + combining acute
    assert segments[0].symbol == "\u00e3\u0301"


def test_mark_does_not_leak_across_a_boundary():
    # the tilde belongs to the vowel it follows, not to the next one
    assert symbols("a\u0303i") == ["\u00e3", "i"]


def test_precomposed_mark_does_not_break_a_word():
    assert symbols("pat\u00e3ka") == ["p", "a", "t", "\u00e3", "k", "a"]
