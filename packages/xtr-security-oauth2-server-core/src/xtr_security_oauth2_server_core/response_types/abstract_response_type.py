"""What every response type is handed, whatever answer it goes on to build."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_oauth2_server_core.crypt_trait import CryptTrait
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from .response_type_interface import ResponseTypeInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )

__all__ = ["AbstractResponseType"]

_NOTHING_ISSUED_YET = (
    "This response type holds no access token; a grant sets one with set_access_token() "
    "before the answer is built."
)


class AbstractResponseType(CryptTrait, ResponseTypeInterface, ABC):
    """Keeps what a grant issued, and seals whatever the answer has to carry.

    Every shipped response type starts here: the two setters a grant calls and
    the key its own payloads are sealed with are the same whatever document is
    produced, so a subclass is left with one job — saying what the answer looks
    like.

    An access token is always issued, so asking for one that was never set is a
    wiring mistake and says so. A refresh token is not: a deployment may issue
    none, and a client-credentials token never comes with one, so
    :attr:`_refresh_token` is simply absent and a subclass reads it as ``None``.
    """

    #: Set by the grant that issued it; absent until then, which is a mistake
    #: rather than a state an answer can be built from.
    _access_token: AccessTokenEntityInterface | None = None

    #: Set only when one was issued, which is why a subclass reads it directly
    #: rather than through an accessor that would refuse.
    _refresh_token: RefreshTokenEntityInterface | None = None

    @override
    def set_access_token(self, access_token: AccessTokenEntityInterface) -> None:
        """Carry ``access_token`` in the answer."""
        self._access_token = access_token

    @override
    def set_refresh_token(self, refresh_token: RefreshTokenEntityInterface) -> None:
        """Carry ``refresh_token`` in the answer, beside the access token."""
        self._refresh_token = refresh_token

    @abstractmethod
    @override
    async def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        """Build the answer this response type has to make, on top of ``response``."""
        ...

    def _access_token_or_fail(self) -> AccessTokenEntityInterface:
        """Return the access token a grant set.

        Raises:
            InvalidArgumentError: When none was set, which means an answer is
                being built for a request that issued nothing.
        """
        if self._access_token is None:
            raise InvalidArgumentError(_NOTHING_ISSUED_YET)

        return self._access_token
