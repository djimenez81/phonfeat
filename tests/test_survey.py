"""Tests for phonfeat.survey."""

from __future__ import annotations

from pathlib import Path

import pytest

from phonfeat import (
    Blocker,
    NotationError,
    Profile,
    SurveyReport,
    load_profile,
    survey,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "profiles"


def lines(name: str) -> list[str]:
    """Read a fixture as a list of forms."""
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------
# Shape and counting
# ---------------------------------------------------------------------


def test_empty_corpus():
    report = survey([])
    assert report.forms == 0
    assert report.tokenized == 0
    assert report.tokens == 0
    assert report.coverage == 0.0
    assert report.blockers == ()
    assert report.segments == {}


def test_clean_corpus_is_fully_covered():
    report = survey(["mata", "pata"])
    assert report.source_forms == 2
    assert report.forms == 2
    assert report.tokenized == 2
    assert report.failed == 0
    assert report.coverage == 1.0
    assert report.tokens == 8


def test_failure_is_reported_not_raised():
    report = survey(["mata", "ma#ta"])
    assert report.forms == 2
    assert report.tokenized == 1
    assert report.failed == 1


def test_blocker_records_character_count_and_example():
    report = survey(["ma#ta"])
    assert len(report.blockers) == 1
    blocker = report.blockers[0]
    assert blocker.char == "#"
    assert blocker.count == 1
    assert blocker.examples == ("ma#ta",)


def test_blocker_codepoint():
    assert Blocker("ñ", 1).codepoint == "U+00F1"


def test_blockers_are_ranked_by_frequency():
    forms = ["a#a", "b#b", "c#c", "a%a"]
    report = survey(forms)
    assert [b.char for b in report.blockers] == ["#", "%"]
    assert report.blockers[0].count == 3


def test_blocker_examples_are_capped():
    report = survey(["a#a"] * 10, examples=2)
    assert report.blockers[0].count == 10
    assert len(report.blockers[0].examples) == 2


def test_segments_are_ordered_by_frequency():
    report = survey(["aaa", "b"])
    assert list(report.segments) == ["a", "b"]
    assert report.segments["a"] == 3


def test_accepts_an_iterator():
    report = survey(iter(["mata", "pata"]))
    assert report.tokenized == 2


def test_non_string_entry_raises():
    with pytest.raises(TypeError):
        survey(["mata", None])


def test_unknown_notation_raises():
    with pytest.raises(NotationError):
        survey(["mata"], "sampa")


def test_empty_strings_are_not_forms():
    report = survey(["", "mata", ""])
    assert report.source_forms == 3
    assert report.forms == 1


# ---------------------------------------------------------------------
# Unmatched characters
# ---------------------------------------------------------------------


def test_unmatched_lists_characters_the_table_cannot_consume():
    report = survey(["ba#ak"])
    assert report.unmatched == {"#": 1}


def test_unmatched_finds_every_offender_in_a_form():
    report = survey(["a#a$a"])
    assert set(report.unmatched) == {"#", "$"}


def test_unmatched_counts_forms_not_occurrences():
    report = survey(["$$$"])
    assert report.unmatched == {"$": 1}


def test_unmatched_is_empty_for_readable_text():
    assert survey(["mata"]).unmatched == {}


# ---------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------


def test_profile_expansion_changes_form_counts():
    profile = Profile(split=r"[\s,]+")
    report = survey(["bacok, bacuk"], profile=profile)
    assert report.source_forms == 1
    assert report.forms == 2
    assert report.tokenized == 2


def test_profile_changes_the_reading_it_declares():
    profile = Profile(substitutions={"ñ": "ɲ"})
    assert "ñ" in survey(["ñak"]).segments
    assert "ɲ" in survey(["ñak"], profile=profile).segments
    assert "ñ" not in survey(["ñak"], profile=profile).segments


def test_profile_supplies_the_notation():
    profile = Profile(notation="xsampa")
    report = survey(["paNka"], profile=profile)
    assert report.notation == "xsampa"


def test_conflicting_notation_raises():
    profile = Profile(notation="xsampa")
    with pytest.raises(NotationError):
        survey(["paNka"], "ipa", profile=profile)


# ---------------------------------------------------------------------
# Feature coverage
# ---------------------------------------------------------------------


def test_no_model_means_no_coverage_numbers():
    report = survey(["mata"])
    assert report.described is None
    assert report.base_only is None
    assert report.undescribed is None
    assert report.types is None


def test_described_base_only_and_undescribed():
    report = survey(["a", "ã", "ʜ"], "ipa", model="hayes")
    assert report.described == {"a": 1}
    assert report.base_only == {"ã": 1}
    assert report.undescribed == {"ʜ": 1}


def test_precomposed_nasal_is_read_as_base_plus_mark():
    """A decomposed letter is not automatically the letter it looks like.

    ``ñ`` decomposes to n + combining tilde, so the tokenizer reads it
    as a nasalized alveolar nasal. In a corpus where ñ is the palatal
    nasal that is the wrong phone, and no error is raised — the
    survey's job is to make that visible, which it does by reporting
    the segment as base-only.
    """
    report = survey(["ñak"], "ipa", model="hayes")
    assert report.base_only == {"ñ": 1}
    assert report.undescribed == {}


def test_model_types_the_segments():
    report = survey(["ata"], "ipa", model="hayes")
    assert report.types == {"vowel": 2, "consonant": 1}


# ---------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------


def test_render_reports_counts_and_blockers():
    text = survey(["mata", "ma#ta"]).render()
    assert "survey: ipa" in text
    assert "tokenized 1 / 2 forms (50.0%)" in text
    assert "U+0023" in text


def test_render_suggests_a_profile_for_unmatched_characters():
    assert "declare them in a profile" in survey(["ba#ak"]).render()


def test_render_is_stable():
    forms = ["mata", "ma#ta", "ñak"]
    assert survey(forms).render() == survey(forms).render()


def test_render_shows_profile_effects():
    profile = Profile(substitutions={"ñ": "ɲ"}, split=r",")
    text = survey(["ña,ñi"], profile=profile).render()
    assert "2 strings" not in text
    assert "1 substitution(s)" in text
    assert "split=" in text


def test_render_omits_coverage_without_a_model():
    assert "feature coverage" not in survey(["mata"]).render()


def test_render_includes_coverage_with_a_model():
    assert "feature coverage" in survey(["mata"], model="hayes").render()


def test_report_str_is_render():
    report = survey(["mata"])
    assert str(report) == report.render()


# ---------------------------------------------------------------------
# The real corpora, as excerpts
# ---------------------------------------------------------------------


def test_cognado_excerpt_is_not_readable_raw():
    report = survey(lines("cognados-excerpt.txt"), "ipa")
    assert report.coverage < 0.9
    assert "-" in [b.char for b in report.blockers]


def test_cognado_excerpt_with_example_profile():
    profile = load_profile(EXAMPLES / "cognados-orthography.yaml")
    report = survey(lines("cognados-excerpt.txt"), profile=profile)
    assert report.coverage > 0.95
    # the profile declares ñ; the one character nobody has decided
    # about stays visible instead of being quietly read
    assert [b.char for b in report.blockers] == ["ᵬ"]


def test_cognado_excerpt_inventory_is_mostly_described_by_hayes():
    # Hayes is a 140-phone system and does not list engma, so the
    # cognate inventory lands at 38 of 39 described there; PanPhon
    # covers all of it. The gap belongs to the model, not the corpus.
    profile = load_profile(EXAMPLES / "cognados-orthography.yaml")
    report = survey(
        lines("cognados-excerpt.txt"), profile=profile, model="hayes"
    )
    assert report.described is not None
    assert list(report.undescribed) == ["ŋ"]


def test_swadesh_excerpt_has_undeclared_tone_marks():
    report = survey(lines("swadesh-excerpt.txt"), "xsampa")
    assert "_" in [b.char for b in report.blockers]


def test_swadesh_excerpt_with_example_profile_still_reports_contours():
    profile = load_profile(EXAMPLES / "swadesh-xsampa.yaml")
    report = survey(lines("swadesh-excerpt.txt"), profile=profile)
    # ñ is handled, the contour marks are deliberately still open
    assert "ñ" not in [b.char for b in report.blockers]
    assert "_" in [b.char for b in report.blockers]


def test_report_is_a_survey_report():
    assert isinstance(survey(["mata"]), SurveyReport)
