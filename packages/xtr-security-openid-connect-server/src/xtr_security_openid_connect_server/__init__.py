"""OpenID Connect for the xtr OAuth 2.0 authorization server."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("xtr-security-openid-connect-server")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"
