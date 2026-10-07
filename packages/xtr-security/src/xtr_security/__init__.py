"""The xtr security bundle: the family facade and the container wiring.

This is the bundle package of the xtr security family. It holds the
:class:`Security` facade, and the :class:`~xtr_security.bundle.SecurityBundle`
that configures :mod:`xtr_security_core`, :mod:`xtr_security_http` and
:mod:`xtr_password_hasher` from one :class:`~xtr_security.bundle.SecurityConfig`.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .security import Security

__all__ = ["Security", "__version__"]

try:
    __version__ = version("xtr-security")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"
