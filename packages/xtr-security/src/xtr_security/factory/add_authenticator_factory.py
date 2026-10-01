"""Prepend an authenticator factory onto the security configuration.

A bundle that adds a kind of authenticator registers its factory by handing this
to ``builder.prepend_extension_config("security", ...)`` from its
``prepend_extension`` hook — the seam an OAuth2 server plugs its ``oauth2``
authenticator into (S-1).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_security.bundle.security_config import SecurityConfig

    from .authenticator_factory_interface import AuthenticatorFactoryInterface

__all__ = ["add_authenticator_factory"]


def add_authenticator_factory(
    factory: AuthenticatorFactoryInterface,
) -> Callable[[object], object]:
    """Return a transform appending ``factory`` to the authenticator factories."""

    def transform(config: object) -> object:
        current = cast("SecurityConfig", config)
        return replace(
            current,
            authenticator_factories=(*current.authenticator_factories, factory),
        )

    return transform
