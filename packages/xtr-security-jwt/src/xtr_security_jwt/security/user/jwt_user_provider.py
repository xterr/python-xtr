"""The stateless user provider that rebuilds a user from a token's claims."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.user.attributes_based_user_provider_interface import (
    AttributesBasedUserProviderInterface,
)

from .jwt_user import JwtUser

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_core.user.user_interface import UserInterface

    from .jwt_user_interface import JwtUserInterface

__all__ = ["JwtUserProvider"]


@final
class JwtUserProvider(AttributesBasedUserProviderInterface):
    """Builds a user from a token's own claims, keeping no store of its own.

    The provider a stateless firewall names: it takes a user class that can be
    built from a payload, and rebuilds a user from the claims the authenticator
    hands it — no database, no lookup. It holds no state, so it builds a fresh
    user from each token's own claims every time: two tokens for the same subject
    carrying different roles yield users with different roles, and a worker
    reusing the provider across messages never serves a stale user.
    """

    __slots__ = ("_user_class",)

    def __init__(self, user_class: type[JwtUserInterface] = JwtUser) -> None:
        """Build users of ``user_class`` from the claims of the tokens that name them."""
        self._user_class = user_class

    @override
    async def load_user_by_identifier(
        self,
        identifier: str,
        attributes: Mapping[str, object] | None = None,
    ) -> UserInterface:
        """Build the user ``identifier`` names from the token ``attributes``."""
        payload: Mapping[str, object] = attributes if attributes is not None else {}
        return self._user_class.create_from_payload(identifier, payload)

    @override
    def supports_class(self, user_class: type) -> bool:
        """Tell whether this provider builds users of ``user_class``.

        Anything that is not a class is supported by nobody, and is reported so
        rather than let ``issubclass`` raise a ``TypeError`` out of a question.
        """
        # The annotation says class; a caller asking the question is not held to
        # it, and a question is answered rather than raised at.
        return isinstance(user_class, type) and issubclass(  # pyright: ignore[reportUnnecessaryIsInstance]
            user_class,
            self._user_class,
        )
