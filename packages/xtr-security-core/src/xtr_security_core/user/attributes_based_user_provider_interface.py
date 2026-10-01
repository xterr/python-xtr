"""A provider that can read extra attributes while loading a user."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from typing_extensions import override

from .user_provider_interface import UserProviderInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["AttributesBasedUserProviderInterface"]


@runtime_checkable
class AttributesBasedUserProviderInterface(UserProviderInterface, Protocol):
    """Loads a user given an identifier and the attributes that came with it.

    A bearer token carries more than a ``sub`` — claims a provider may want
    while building the user. This is the ordinary provider contract
    (:class:`~xtr_security_core.user.user_provider_interface.UserProviderInterface`)
    with those attributes passed alongside the identifier; a provider that
    ignores them behaves exactly like a plain one.
    """

    @override
    async def load_user_by_identifier(
        self,
        identifier: str,
        attributes: Mapping[str, object] | None = None,
    ) -> UserInterface:
        """Load the user named by ``identifier``, given ``attributes``.

        Raises:
            UserNotFoundError: When no user matches ``identifier``.
        """
        ...
