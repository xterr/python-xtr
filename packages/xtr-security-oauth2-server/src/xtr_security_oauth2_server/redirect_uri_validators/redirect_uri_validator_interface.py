"""What decides whether an authorize request may be answered to a given uri."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["RedirectUriValidatorInterface"]


@runtime_checkable
class RedirectUriValidatorInterface(Protocol):
    """Decides whether a uri is one the client registered to be answered at.

    This is the one thing standing between a registered client and an open
    redirect that leaks an authorization code, so a validator answers on the
    uri alone — never on a prefix, a host, or anything an attacker can extend.
    """

    def validate_redirect_uri(self, redirect_uri: str) -> bool:
        """Tell whether ``redirect_uri`` is one of the registered ones."""
        ...
