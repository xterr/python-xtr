"""The entry points that answer a request the firewall will not let through."""

from __future__ import annotations

from .authentication_entry_point_interface import AuthenticationEntryPointInterface
from .fallback_authentication_entry_point_interface import (
    FallbackAuthenticationEntryPointInterface,
)
from .re_authentication_entry_point_interface import ReAuthenticationEntryPointInterface

__all__ = [
    "AuthenticationEntryPointInterface",
    "FallbackAuthenticationEntryPointInterface",
    "ReAuthenticationEntryPointInterface",
]
