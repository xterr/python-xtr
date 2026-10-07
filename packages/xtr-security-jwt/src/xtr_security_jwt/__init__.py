"""Self-issued JSON Web Tokens for xtr security: encoder, token manager and authenticator."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .services.jwt_token_manager_interface import JwtTokenManagerInterface

__all__ = ["JwtTokenManagerInterface", "__version__"]

try:
    __version__ = version("xtr-security-jwt")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"
