"""The token document a client is handed at the end of a successful flow."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

from typing_extensions import override
from xtr_clock import (
    ClockInterface,  # noqa: TC002 -- container hydrates this constructor at runtime
)

from .abstract_response_type import AbstractResponseType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface

    from xtr_security_oauth2_server.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )

__all__ = ["BearerTokenResponse"]

#: What the answer calls the scheme a client presents the token with: RFC 6750's
#: ``Authorization: Bearer <token>``.
_BEARER: Final[str] = "Bearer"


class BearerTokenResponse(AbstractResponseType):
    """Answers an access token a client presents by simply holding it.

    This is the answer nearly every deployment hands out: the signed access
    token, the scheme to present it with, how long it has left, and — when the
    flow issued one — a refresh token to buy the next pair with.

    The refresh token a client receives is not the refresh token's identifier.
    It is a sealed payload naming the client, the pair of tokens and the
    expiry, so the refresh grant can read everything it needs back out of what
    the client hands over and the server keeps no state between the two
    requests. Sealing it is what stops a client editing the scopes or the
    resource owner it names.

    The clock is taken rather than read from the system because the answer says
    how many seconds the token has left, and a deployment that freezes or
    offsets time must have that answer follow.

    A deployment with something more to say overrides
    :meth:`get_extra_params` rather than the whole answer, so the fields the
    flow defines keep being built here — and keep winning, because a client
    reads ``access_token`` and ``token_type`` by name and an answer that let
    them be replaced would be unreadable.
    """

    def __init__(self, clock: ClockInterface) -> None:
        """Answer against ``clock``, which decides how long the token has left."""
        self._clock: ClockInterface = clock

    def get_extra_params(self, access_token: AccessTokenEntityInterface) -> Mapping[str, object]:
        """Return the fields this answer carries besides the ones the flow defines.

        Nothing by default. The token is passed in rather than read off this
        object because that is what an override has something to say about —
        the client it was issued to, the scopes it carries.
        """
        del access_token

        return {}

    @override
    def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        """Answer the token, the scheme, the lifetime and the refresh token.

        Nothing may cache it: the document carries a credential, and a cached
        one would be handed to whoever asked next.

        Raises:
            InvalidArgumentError: When no access token was set, which would
                otherwise answer a request that earned nothing.
        """
        access_token = self._access_token_or_fail()
        left = access_token.get_expiry_date_time().timestamp() - self._clock.now().timestamp()
        params: dict[str, object] = dict(self.get_extra_params(access_token))
        params.update(
            {
                "token_type": _BEARER,
                "expires_in": int(left),
                "access_token": access_token.to_string(),
            },
        )
        if self._refresh_token is not None:
            params["refresh_token"] = self.encrypt(
                {
                    "client_id": access_token.get_client().get_identifier(),
                    "refresh_token_id": self._refresh_token.get_identifier(),
                    "access_token_id": access_token.get_identifier(),
                    "scopes": [scope.get_identifier() for scope in access_token.get_scopes()],
                    "user_id": access_token.get_user_identifier(),
                    "expire_time": int(
                        self._refresh_token.get_expiry_date_time().timestamp(),
                    ),
                },
            )

        answer = (
            response.with_status(200)
            .with_header("pragma", "no-cache")
            .with_header("cache-control", "no-store")
            .with_header("content-type", "application/json; charset=UTF-8")
        )
        _ = answer.get_body().write(json.dumps(params).encode())

        return answer
