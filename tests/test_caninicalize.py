# Canonical order of IPA diacritics.
#
# Combining marks are reordered to appear in the order in which
# their categories appear in this list. Within a category, marks
# are ordered by their position in the `symbols` list.
#
# Marks not listed here are placed after all listed marks, in
# their original relative order.

- category: phonation
  symbols:
    - "\u030A"   # ring above (voiceless)
    - "\u0325"   # ring below (voiceless)
    - "\u030C"   # caron (falling tone)
    - "\u0301"   # acute (rising tone)
    - "\u0304"   # macron (mid tone)
    - "\u0300"   # grave (low tone)
    - "\u030B"   # double acute (extra high tone)
    - "\u030F"   # double grave (extra low tone)
    - "\u0303"   # tilde (nasalized)
    - "\u0330"   # tilde below (creaky)
    - "\u0308"   # diaeresis (centralized)
    - "\u0324"   # diaeresis below (breathy)
    - "\u0334"   # tilde overlay (velarized)
    - "\u031F"   # plus below (advanced)
    - "\u0320"   # minus below (retracted)
    - "\u0306"   # breve (extra short)

- category: place
  symbols:
    - "\u032A"   # bridge below (dental)
    - "\u033A"   # inverted bridge below (apical)
    - "\u033B"   # square below (laminal)
    - "\u033C"   # seagull below (linguolabial)

- category: rounding
  symbols:
    - "\u02B7"   # modifier small w
    - "\u02B2"   # modifier small j
    - "\u02E0"   # modifier small gamma
    - "\u02E4"   # modifier small reversed glottal stop
    - "\u1D63"   # modifier small w (alternative)

- category: syllabicity
  symbols:
    - "\u0329"   # vertical line below (syllabic)
    - "\u032F"   # inverted breve below (non-syllabic)

- category: release
  symbols:
    - "\u207F"   # superscript n (nasal release)
    - "\u02E1"   # modifier small l (lateral release)
    - "\u031A"   # corner above (no audible release)

- category: length
  symbols:
    - "\u02D0"   # triangular colon (long)
    - "\u02D1"   # half triangular colon (half long)"""Tests for phonfeat.canonicalize."""

import pytest

from phonfeat import canonicalize_ipa, canonicalize_xsampa
from phonfeat.errors import DataFormatError
from phonfeat.canonicalize import (
    DeprecationRule,
    DiacriticCategory,
    load_deprecations,
    load_diacritic_order,
)


class TestLoadDeprecations:
    def test_loads_bundled_file(self) -> None:
        rules = load_deprecations()
        assert len(rules) > 0
        assert all(isinstance(r, DeprecationRule) for r in rules)

    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(DataFormatError, match="not found"):
            load_deprecations(tmp_path / "nope.yaml")

    def test_malformed_file_raises(self, tmp_path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("not: a: list:\n", encoding="utf-8")
        with pytest.raises(DataFormatError):
            load_deprecations(path)

    def test_missing_key_raises(self, tmp_path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text(
            "- from: a\n  reason: missing 'to'\n",
            encoding="utf-8",
        )
        with pytest.raises(DataFormatError, match="'to'"):
            load_deprecations(path)


class TestLoadDiacriticOrder:
    def test_loads_bundled_file(self) -> None:
        cats = load_diacritic_order()
        assert len(cats) > 0
        assert all(isinstance(c, DiacriticCategory) for c in cats)

    def test_order_is_stable(self) -> None:
        cats = load_diacritic_order()
        names = [c.category for c in cats]
        assert names[0] == "phonation"
        assert names[-1] == "tone"


class TestCanonicalizeIpa:
    def test_identity(self) -> None:
        assert canonicalize_ipa("p") == "p"
        assert canonicalize_ipa("a") == "a"

    def test_latin_g_to_script_g(self) -> None:
        assert canonicalize_ipa("g") == "ɡ"

    def test_script_g_unchanged(self) -> None:
        assert canonicalize_ipa("ɡ") == "ɡ"

    def test_ligature_affricate(self) -> None:
        assert canonicalize_ipa("ʧ") == "t͡ʃ"
        assert canonicalize_ipa("ʤ") == "d͡ʒ"

    def test_diacritic_reordering(self) -> None:
        # Length mark followed by voiceless ring: canonical order
        # is phonation before length.
        assert canonicalize_ipa("qː̥") == "q̥ː"
        assert canonicalize_ipa("q̥ː") == "q̥ː"

    def test_diacritic_reordering_idempotent(self) -> None:
        once = canonicalize_ipa("t̪͡s̪ˤː")
        twice = canonicalize_ipa(once)
        assert once == twice

    def test_archaic_velar_implosive(self) -> None:
        assert canonicalize_ipa("ƙ") == "ɠ̥"

    def test_non_string_raises(self) -> None:
        with pytest.raises(TypeError):
            canonicalize_ipa(5)  # type: ignore[arg-type]


class TestCanonicalizeXsampa:
    def test_identity(self) -> None:
        assert canonicalize_xsampa("p") == "p"
        assert canonicalize_xsampa("tS") == "tS"

    def test_non_string_raises(self) -> None:
        with pytest.raises(TypeError):
            canonicalize_xsampa(5)  # type: ignore[arg-type]


class TestIdempotence:
    """Canonicalization must be idempotent."""

    @pytest.mark.parametrize(
        "symbol",
        [
            "p",
            "a",
            "ɡ",
            "g",
            "ʧ",
            "t͡ʃ",
            "qˤː",
            "qːˤ",
            "t̪͡s̪ˤː",
            "t̪͡s̪ːˤ",
            "n̥",
            "n̊",
            "ɳ̊",
            "ɳ̥",
            "ƙ",
            "ɠ̥",
        ],
    )
    def test_idempotent(self, symbol: str) -> None:
        once = canonicalize_ipa(symbol)
        twice = canonicalize_ipa(once)
        assert once == twice

    @pytest.mark.parametrize(
        "symbol",
        ["qˤː", "qːˤ"],
    )
    def test_diacritic_order_collapses(self, symbol: str) -> None:
        # Both orderings of the same diacritics must produce the
        # same canonical form.
        canonical = canonicalize_ipa(symbol)
        assert canonical == canonicalize_ipa("qˤː")
