"""The mark of an authenticator factory whose authenticator can work without a user provider."""

from __future__ import annotations

from typing import Protocol

from .authenticator_factory_interface import AuthenticatorFactoryInterface

__all__ = ["StatelessAuthenticatorFactoryInterface"]


class StatelessAuthenticatorFactoryInterface(AuthenticatorFactoryInterface, Protocol):
    """An authenticator factory that accepts no user provider.

    A firewall that names no user provider, in an application that configures
    none, hands every other factory a placeholder provider that fails — naming
    the firewall — the first time it is used. A factory carrying this mark is
    handed ``None`` instead, because its authenticator can settle on a user
    without a provider: an access-token handler that builds the user from the
    token's claims, say.

    It adds nothing to :class:`AuthenticatorFactoryInterface`: it is a mark,
    declared by inheriting from it and read nominally —
    ``StatelessAuthenticatorFactoryInterface in type(factory).__mro__``. It is
    deliberately not runtime-checkable: with no member of its own, a structural
    check would match every factory.
    """
