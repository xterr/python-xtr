"""One SMTP session, driven command by command — the only package that imports aiosmtplib.

aiosmtplib speaks the protocol: it connects, switches to TLS and reads replies.
Everything it raises is turned here into a :class:`TransportError` or an
:class:`UnexpectedResponseError`, so the transports built on this client never
see one of its types.

The work is split by step: :mod:`._session` makes the aiosmtplib session and reads the
extensions it is offered, :mod:`._tls` switches it to TLS and checks the pinned
certificate, :mod:`._upload` writes a message, :mod:`._errors` names what aiosmtplib
raised, and :mod:`._client` drives them.
"""

from __future__ import annotations

from ._client import SmtpClient

__all__ = ["SmtpClient"]
