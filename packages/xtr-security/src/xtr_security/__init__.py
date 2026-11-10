"""The xtr security bundle: the family facade and the container wiring.

This is the bundle package of the xtr security family. It holds the
:class:`Security` facade, and the :class:`~xtr_security.bundle.SecurityBundle`
that configures :mod:`xtr_security_core`, :mod:`xtr_security_http` and
:mod:`xtr_password_hasher` from one :class:`~xtr_security.bundle.SecurityConfig`.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

# Loaded always: the factory and provider packages build from the
# configuration classes that live in ``xtr_security.bundle``, whose own module
# re-exports those packages' factories. Entered from the bundle the two load
# in order; entered from a factory package first, the bundle would ask that
# half-loaded package for a class it has not defined yet. Loading the bundle
# here makes the bundle the entry, whichever of them is imported first.
from . import (
    bundle,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- loaded for its import order, not its name
)
from .oidc_back_channel_logout_handler import OidcBackChannelLogoutHandler
from .security import Security

__all__ = ["OidcBackChannelLogoutHandler", "Security", "__version__"]

try:
    __version__ = version("xtr-security")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"
