"""Prepend a user-provider factory onto the security configuration.

A bundle that adds a kind of user provider registers its factory by handing this
to ``builder.prepend_extension_config("security", ...)`` from its
``prepend_extension`` hook.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_security.bundle.security_config import SecurityConfig

    from .user_provider_factory_interface import UserProviderFactoryInterface

__all__ = ["add_user_provider_factory"]


def add_user_provider_factory(
    factory: UserProviderFactoryInterface,
) -> Callable[[object], object]:
    """Return a transform appending ``factory`` to the user-provider factories."""

    def transform(config: object) -> object:
        current = cast("SecurityConfig", config)
        return replace(
            current,
            user_provider_factories=(*current.user_provider_factories, factory),
        )

    return transform
