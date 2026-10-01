"""Prepend a token-handler factory onto the security configuration.

A bundle that adds a kind of access-token handler registers its factory by
handing this to ``builder.prepend_extension_config("security", ...)`` from its
``prepend_extension`` hook — the seam an introspection handler plugs into (S-2).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_security.bundle.security_config import SecurityConfig

    from .token_handler_factory_interface import TokenHandlerFactoryInterface

__all__ = ["add_token_handler_factory"]


def add_token_handler_factory(
    factory: TokenHandlerFactoryInterface,
) -> Callable[[object], object]:
    """Return a transform appending ``factory`` to the token-handler factories."""

    def transform(config: object) -> object:
        current = cast("SecurityConfig", config)
        return replace(
            current,
            token_handler_factories=(*current.token_handler_factories, factory),
        )

    return transform
