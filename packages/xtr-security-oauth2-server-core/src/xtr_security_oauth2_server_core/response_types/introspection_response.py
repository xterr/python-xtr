"""The answer to a question about a token: whether it is live, and what it says."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Final, cast

from typing_extensions import override

from .introspection_response_type_interface import IntrospectionResponseTypeInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface

__all__ = ["IntrospectionResponse"]

#: What separates the scopes a token carries, in the one ``scope`` field a
#: document about a token names them in.
_SCOPE_DELIMITER: Final[str] = " "

#: The scheme an access token is presented with, the only token type a
#: document about an access token names (RFC 7662, Section 2.2).
_BEARER: Final[str] = "Bearer"

#: The two kinds of token this server issues, as the handler names them.
_ACCESS_TOKEN: Final[str] = "access_token"  # noqa: S105 -- a token kind, not a secret
_REFRESH_TOKEN: Final[str] = "refresh_token"  # noqa: S105 -- a token kind, not a secret


def _names(token_data: Mapping[str, object], name: str) -> tuple[str, ...]:
    """Read ``name`` out of what the token carries as names, empty when there are none."""
    value = token_data.get(name)
    if not isinstance(value, list):
        return ()

    # The cast says what narrowing cannot: a list of anything is a list of
    # objects, and every item is then asked what it is.
    return tuple(item for item in cast("list[object]", value) if isinstance(item, str))


def _timestamp(value: object) -> int | None:
    """Read ``value`` as a whole number of seconds since the epoch, or ``None``.

    A token's instants reach here as whatever recorded them: a claim read off a
    signed token is a number, a sealed payload carries one as text, and a
    deployment reading its own storage hands over a moment in time. Anything
    else is not an instant, and the field it would have filled is left out
    rather than published as nonsense.
    """
    if isinstance(value, datetime):
        return int(value.timestamp())
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None

    return None


def _published(named: Mapping[str, object | None]) -> Mapping[str, object]:
    """Return ``named`` without the fields nothing was known for."""
    return {name: value for name, value in named.items() if value is not None}


class IntrospectionResponse(IntrospectionResponseTypeInterface):
    """What a protected resource is told about a token it was presented with.

    A resource server that cannot read a token itself asks the authorization
    server about it. The answer is either ``active: false`` and nothing else,
    or ``active: true`` and what the token says — who holds it, who it acts
    for, what it may do, how long it has left.

    Which fields those are depends on the kind of token that was read, because
    an access token and a refresh token record the same things under different
    names: an access token carries the claims it was signed with, a refresh
    token the payload this server sealed. Each is mapped to the field names
    RFC 7662 Section 2.2 publishes, and a field nothing was known for is left
    out rather than sent as null.

    Nothing else is ever said. A token that is unknown, expired, revoked, or
    was issued to a different client than the one asking all get the same bare
    refusal, because telling them apart would turn this endpoint into an
    oracle a client could ask about tokens it does not hold.

    A deployment that publishes more than the named fields subclasses this and
    answers :meth:`get_extra_params`; what it returns is merged last, so it
    may also replace a field this would have published.
    """

    def __init__(self) -> None:
        """Start from a token this will say nothing about."""
        self._active: bool = False
        self._token_type: str | None = None
        self._token_data: Mapping[str, object] | None = None

    @override
    def set_active(self, active: bool) -> None:
        """Say whether the token is live."""
        self._active = active

    @override
    def set_token_type(self, token_type: str) -> None:
        """Say which kind of token was read, so its fields are named for it."""
        self._token_type = token_type

    @override
    def set_token_data(self, token_data: Mapping[str, object]) -> None:
        """Say what the token carries, as the kind of token it is records it."""
        self._token_data = token_data

    @override
    def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        """Answer the document on top of ``response``.

        Nothing may cache it: whether a token is live is true only at the
        moment it is asked, and a cached ``active: true`` would outlive a
        revocation.
        """
        params: dict[str, object] = {"active": self._active}
        if self._active and self._token_type is not None and self._token_data is not None:
            params.update(self._parse_params(self._token_type, self._token_data))
            params.update(self.get_extra_params(self._token_type, self._token_data))

        answer = (
            response.with_status(200)
            .with_header("cache-control", "no-store")
            .with_header("content-type", "application/json; charset=UTF-8")
        )
        _ = answer.get_body().write(json.dumps(params).encode())

        return answer

    def get_extra_params(
        self,
        token_type: str,
        token_data: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Return the fields this deployment publishes beyond the named ones.

        Nothing by default. A subclass answering something gets it merged after
        the named fields, so it may add to them or replace one of them.
        """
        del token_type, token_data

        return {}

    def _parse_params(
        self,
        token_type: str,
        token_data: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Return the named fields the kind of token that was read publishes.

        A kind this does not know publishes none of them: the liveness is
        still true, and whatever a deployment publishes for its own kind of
        token comes from :meth:`get_extra_params`.
        """
        if token_type == _ACCESS_TOKEN:
            return self._parse_access_token_params(token_data)
        if token_type == _REFRESH_TOKEN:
            return self._parse_refresh_token_params(token_data)

        return {}

    def _parse_access_token_params(
        self,
        token_data: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Return what a document about an access token says, off its claims.

        The scopes are read from the one ``scope`` claim this server stamps and
        from a ``scopes`` list for a deployment that records them apart, and
        the client is read from the ``client_id`` claim or, for a token that
        carries none, from the first audience it is addressed to.
        """
        scope = token_data.get("scope")
        audiences = _names(token_data, "aud")
        client_id = token_data.get("client_id")

        return _published(
            {
                "scope": (
                    scope
                    if scope is not None
                    else _SCOPE_DELIMITER.join(_names(token_data, "scopes"))
                ),
                "client_id": (
                    client_id if client_id is not None else (audiences[0] if audiences else None)
                ),
                "username": token_data.get("username"),
                "token_type": _BEARER,
                "exp": _timestamp(token_data.get("exp")),
                "iat": _timestamp(token_data.get("iat")),
                "nbf": _timestamp(token_data.get("nbf")),
                "sub": token_data.get("sub"),
                "aud": token_data.get("aud"),
                "iss": token_data.get("iss"),
                "jti": token_data.get("jti"),
            },
        )

    def _parse_refresh_token_params(
        self,
        token_data: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Return what a document about a refresh token says, off its sealed payload."""
        return _published(
            {
                "scope": _SCOPE_DELIMITER.join(_names(token_data, "scopes")),
                "client_id": token_data.get("client_id"),
                "exp": _timestamp(token_data.get("expire_time")),
                "sub": token_data.get("user_id"),
                "jti": token_data.get("refresh_token_id"),
            },
        )

    @override
    def __repr__(self) -> str:
        """Say whether the token is live, never a word of what it says.

        What the token carries names the resource owner, the client and the
        token itself; none of that belongs in a log line or a traceback.
        """
        return f"{type(self).__name__}(active={self._active!r})"
