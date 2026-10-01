"""What mints a self-issued token for a user and reads one back."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["JwtTokenManagerInterface"]


@runtime_checkable
class JwtTokenManagerInterface(Protocol):
    """Mints a signed token for a user, and reads a presented one back into claims.

    The manager assembles the payload — the user's roles and the claim naming who
    they are — enriches it, announces it for a listener to shape, signs it, and
    announces the finished token. Reading a token back verifies it and announces
    its payload, which a listener may reject.
    """

    async def create(self, user: UserInterface) -> str:
        """Mint a signed token for ``user``, carrying its roles and identity."""
        ...

    async def create_from_payload(
        self,
        user: UserInterface,
        payload: Mapping[str, object],
    ) -> str:
        """Mint a signed token for ``user``, starting from a caller's ``payload``."""
        ...

    async def decode(self, token: TokenInterface) -> Mapping[str, object] | bool:
        """Read the claims out of a security ``token``, or ``False`` when it has none."""
        ...

    async def parse(self, token: str) -> Mapping[str, object]:
        """Verify a compact ``token`` and return its claims.

        Raises:
            JwtDecodeFailureError: When the token cannot be read, has expired, or
                its signature does not verify.
        """
        ...

    def get_user_id_claim(self) -> str:
        """Return the claim the user's identifier is written into."""
        ...
