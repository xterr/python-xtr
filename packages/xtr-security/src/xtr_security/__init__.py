"""The xtr security bundle: the family facade and the container wiring.

This is the bundle package of the xtr security family. It holds the
:class:`Security` facade, and the :class:`~xtr_security.bundle.SecurityBundle`
that configures :mod:`xtr_security_core`, :mod:`xtr_security_http` and
:mod:`xtr_password_hasher` from one :class:`~xtr_security.bundle.SecurityConfig`.
"""

from __future__ import annotations

from .security import Security

__all__ = ["Security"]
