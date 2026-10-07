"""Prepend an authenticator factory onto the security configuration.

A bundle that adds a kind of authenticator registers its factory by handing this
to ``builder.prepend_extension_config("security", ...)`` from its
``prepend_extension`` hook — the seam an OAuth2 server plugs its ``oauth2``
authenticator into (S-1).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_security.bundle.security_config import SecurityConfig

    from .authenticator_factory_interface import AuthenticatorFactoryInterface

__all__ = ["add_authenticator_factory"]


def add_authenticator_factory(
    factory: AuthenticatorFactoryInterface,
) -> Callable[[object], object]:
    """Return a transform appending ``factory`` to the authenticator factories.

    Raises:
        InvalidConfigurationError: When the transform runs and a factory with
            ``factory``'s ``key`` is already registered — two factories keyed the
            same would make the kind of authenticator they build ambiguous.
    """

    def transform(config: object) -> object:
        current = cast("SecurityConfig", config)
        if any(existing.key == factory.key for existing in current.authenticator_factories):
            raise InvalidConfigurationError(
                f'An authenticator factory keyed "{factory.key}" is already registered.',
            )
        return replace(
            current,
            authenticator_factories=(*current.authenticator_factories, factory),
        )

    return transform
