"""The token answer of a deployment running the add-on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

# Both names the constructor below reads are imported at runtime: the container
# evaluates those annotations when it builds this answer.
from xtr_clock import ClockInterface
from xtr_security_oauth2_server_core.response_types.bearer_token_response import BearerTokenResponse

from .stamp import NonceStamp

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )

__all__ = ["NONCE_FIELD", "NonceTokenResponse"]

#: The one field the add-on adds to the token answer.
NONCE_FIELD: Final[str] = "nonce_handshake"


@final
class NonceTokenResponse(BearerTokenResponse):
    """The bearer answer plus one field, built from what the code carried.

    Put in place of the shipped answer by the add-on prepending
    ``authorization_server.response_type_class``, and built by the container,
    so the add-on's own service reaches it as a constructor argument.

    The field is set per request, on the copy of this answer the server hands
    the grant: one request's carried parameter must never reach another
    request's answer.
    """

    def __init__(self, clock: ClockInterface, stamp: NonceStamp) -> None:
        """Answer against ``clock``, publishing what ``stamp`` makes of the parameter."""
        super().__init__(clock)
        self._stamp: NonceStamp = stamp
        self._nonce: str | None = None

    def set_nonce(self, nonce: str | None) -> None:
        """Carry ``nonce`` in this answer, or nothing when the code carried none."""
        self._nonce = nonce

    @override
    def get_extra_params(self, access_token: AccessTokenEntityInterface) -> Mapping[str, object]:
        """Return the add-on's field, when the code the token was earned with carried one."""
        del access_token
        if self._nonce is None:
            return {}

        return {NONCE_FIELD: self._stamp.stamp(self._nonce)}
