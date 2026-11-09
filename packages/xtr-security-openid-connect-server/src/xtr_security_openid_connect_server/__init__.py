"""OpenID Connect for the xtr OAuth 2.0 authorization server.

:data:`AUTH_TIME_LISTENER_PRIORITY` is the priority the provider records the
sign-in time at, on the authorization server's consent event; an application's
consent listener runs below it.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .event_listener.auth_time_listener import AUTH_TIME_LISTENER_PRIORITY

__all__ = ["AUTH_TIME_LISTENER_PRIORITY", "__version__"]

try:
    __version__ = version("xtr-security-openid-connect-server")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"
