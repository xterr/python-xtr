"""Cross-site request forgery tokens, minted and checked by id.

A manager mints a value per token id, masks what it hands out, and checks
what comes back against what it stored; a storage keeps the values — in the
session a request carries, or wherever the application points them. This
module gathers the public surface so an application imports it from one
place.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .csrf_token import CsrfToken
from .csrf_token_manager import CsrfTokenManager
from .csrf_token_manager_interface import CsrfTokenManagerInterface
from .exception import CsrfError, InvalidArgumentError, TokenNotFoundError
from .token_generator import TokenGeneratorInterface, UriSafeTokenGenerator
from .token_storage import (
    ClearableTokenStorageInterface,
    SessionTokenStorage,
    TokenStorageInterface,
)

__all__ = [
    "ClearableTokenStorageInterface",
    "CsrfError",
    "CsrfToken",
    "CsrfTokenManager",
    "CsrfTokenManagerInterface",
    "InvalidArgumentError",
    "SessionTokenStorage",
    "TokenGeneratorInterface",
    "TokenNotFoundError",
    "TokenStorageInterface",
    "UriSafeTokenGenerator",
    "__version__",
]

try:
    __version__ = version("xtr-security-csrf")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"
