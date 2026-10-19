"""The marker every error that refuses a login link wears."""

from __future__ import annotations

__all__ = ["InvalidLoginLinkErrorInterface"]


class InvalidLoginLinkErrorInterface(Exception):  # noqa: N818 -- the upstream name of the marker, kept so the refused errors read as their counterparts elsewhere; the Interface suffix is this repo's convention for a base others implement
    """An error saying a login link does not check out.

    A handler refuses a link for more than one reason — a parameter it
    cannot read, a hash no secret signs, a moment that has passed — and
    each refusal raises its own error; the authenticator that hands the
    link to the handler catches them all with this one base and answers
    with the single authentication error of its own.

    The marker is a class the refused errors inherit, not a ``Protocol``
    a runtime check would answer ``True`` for regardless: it is caught,
    and a catch must name a base the errors actually derive from.
    """

    __slots__: tuple[str, ...] = ()
