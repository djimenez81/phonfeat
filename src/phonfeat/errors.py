"""Exceptions raised by phonfeat.

All phonfeat exceptions inherit from :class:`PhonfeatError`, so
callers can catch the entire family with one except clause.
"""

from __future__ import annotations

__all__ = [
    "DataFormatError",
    "NotationError",
    "PhonfeatError",
    "TokenizationError",
    "UnknownSegmentError",
]


class PhonfeatError(Exception):
    """Base class for all phonfeat exceptions."""


class NotationError(PhonfeatError):
    """Raised when a notation is unknown or not applicable."""


class TokenizationError(PhonfeatError):
    """Raised when a string cannot be tokenized."""


class DataFormatError(PhonfeatError):
    """Raised when a data file violates the data format spec."""


class UnknownSegmentError(PhonfeatError):
    """Raised when a token has no entry in the symbol or feature table."""
