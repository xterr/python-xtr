"""The two conversions across the seam between the protocol and what is stored.

Scopes exist on both sides and travel both ways; a user arrives from the
security family and is narrowed down to the identifier a token carries. Each
conversion is a service with a contract, so an application that brings its own
scope entity or its own notion of a token subject replaces one small thing
instead of reimplementing a repository.
"""

from __future__ import annotations

from .scope_converter import ScopeConverter
from .scope_converter_interface import ScopeConverterInterface
from .user_converter import UserConverter
from .user_converter_interface import UserConverterInterface

__all__ = [
    "ScopeConverter",
    "ScopeConverterInterface",
    "UserConverter",
    "UserConverterInterface",
]
