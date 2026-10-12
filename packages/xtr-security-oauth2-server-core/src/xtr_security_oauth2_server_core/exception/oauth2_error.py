"""The root every error in this library derives from."""

from __future__ import annotations

__all__ = ["OAuth2Error"]


class OAuth2Error(Exception):
    """Base class for every error raised by this library.

    Catch this to handle anything the authorization server, the resource
    server or their wiring can go wrong with; catch a subclass to handle one
    cause. Every subclass carries the data a caller needs as typed attributes
    and composes its own message from them.

    It derives from :class:`Exception` rather than from the security family's
    base, because most of what this library raises is a protocol answer — a
    request naming an unknown grant, a code that was already redeemed — not a
    failure of the family's authentication machinery. The errors the firewall
    will have to answer will be the exception: they will mix the family's
    ``AuthenticationError`` in beside this base, so one ``except
    SecurityError`` will still catch those while one ``except OAuth2Error``
    catches everything from here.
    """
