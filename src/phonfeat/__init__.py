"""phonfeat: IPA and X-SAMPA tokenization, conversion, and features.

phonfeat is the notation-specific layer on top of lingcore. It
provides tokenization, conversion between IPA and X-SAMPA,
inventory extraction from corpora, feature attachment from
PanPhon-style and Hayes-style tables, and computation of minimal
distinguishing feature sets.

A corpus, for this package, is a list of strings. Reading a file —
spreadsheet, Python literal, text dump — is the caller's business;
what phonfeat owes the caller is an accurate reading of the strings
and an honest account of what it could not read.

Public API
----------
Notation:
    :func:`canonicalize_ipa`, :func:`canonicalize_xsampa`

Tokenization:
    :func:`tokenize`

Corpora:
    :class:`Profile`, :func:`load_profile`, :func:`survey`,
    :class:`SurveyReport`

Conversion:
    :func:`ipa_to_xsampa`, :func:`xsampa_to_ipa`

Features:
    :func:`load_feature_model`, :func:`attach_features`

Inventories:
    :class:`Inventory`, :func:`inventory_from_corpus`

Solver:
    :func:`minimal_feature_set`
"""

from .canonicalize import canonicalize_ipa, canonicalize_xsampa
from .errors import (
    DataFormatError,
    NotationError,
    PhonfeatError,
    TokenizationError,
    UnknownSegmentError,
)
from .inventory import Inventory
from .profile import Profile, load_profile
from .storage import load_feature_model, load_symbol_table
from .survey import Blocker, SurveyReport, survey
from .tokenize import tokenize

__version__ = "0.1.0"

# Not yet implemented; listed here as placeholders so the intended
# public surface is visible from the package root.
# from .convert import ipa_to_xsampa, xsampa_to_ipa
# from .features import attach_features
# from .inventory_extraction import inventory_from_corpus
# from .solver import minimal_feature_set

__all__ = [
    "Blocker",
    "DataFormatError",
    "Inventory",
    "NotationError",
    "PhonfeatError",
    "Profile",
    "SurveyReport",
    "TokenizationError",
    "UnknownSegmentError",
    "canonicalize_ipa",
    "canonicalize_xsampa",
    "load_feature_model",
    "load_profile",
    "load_symbol_table",
    "survey",
    "tokenize",
    "__version__",
]
