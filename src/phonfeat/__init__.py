"""phonfeat: IPA and X-SAMPA tokenization, conversion, and features.

phonfeat is the notation-specific layer on top of lingcore. It
provides tokenization, conversion between IPA and X-SAMPA,
inventory extraction from corpora, feature attachment from
PanPhon-style and Hayes-style tables, and computation of minimal
distinguishing feature sets.

Public API
----------
Notation:
    :func:`canonicalize_ipa`, :func:`canonicalize_xsampa`

Tokenization:
    :func:`tokenize`

Conversion:
    :func:`ipa_to_xsampa`, :func:`xsampa_to_ipa`

Features:
    :func:`load_feature_system`, :func:`attach_features`

Inventories:
    :func:`inventory_from_corpus`

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

__version__ = "0.1.0"

# Not yet implemented; listed here as placeholders so the intended
# public surface is visible from the package root.
# from .convert import ipa_to_xsampa, xsampa_to_ipa
# from .inventory import attach_features, inventory_from_corpus
# from .solver import minimal_feature_set
# from .storage import load_feature_system
# from .tokenize import tokenize

__all__ = [
    "DataFormatError",
    "NotationError",
    "PhonfeatError",
    "TokenizationError",
    "UnknownSegmentError",
    "canonicalize_ipa",
    "canonicalize_xsampa",
    "__version__",
]
