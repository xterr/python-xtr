"""Where an authorize request may be answered.

A client registers the uris it is willing to receive an authorization response
at, and the server answers at none other. What lives here is the comparison
that decides it.
"""

from __future__ import annotations

from .redirect_uri_validator import RedirectUriValidator
from .redirect_uri_validator_interface import RedirectUriValidatorInterface

__all__ = [
    "RedirectUriValidator",
    "RedirectUriValidatorInterface",
]
