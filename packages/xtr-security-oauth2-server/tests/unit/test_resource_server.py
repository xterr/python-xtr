"""What an API puts in front of its routes to find out who is calling."""

from __future__ import annotations

from typing import final

import pytest
from xtr_http_message_contracts import ServerRequestInterface

from tests.support.messages import server_request
from tests.support.repositories import InMemoryAccessTokenRepository
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.resource_server import ResourceServer


@final
class _AnnotatingValidator:
    """A validator that accepts, naming the token it read."""

    async def validate_authorization(
        self,
        request: ServerRequestInterface,
    ) -> ServerRequestInterface:
        return request.with_attribute("oauth_access_token_id", "access-1")


@final
class _RefusingValidator:
    """A validator that refuses everything it is handed."""

    async def validate_authorization(
        self,
        request: ServerRequestInterface,
    ) -> ServerRequestInterface:
        del request

        raise OAuthServerError.access_denied("Access token has been revoked")


def _request() -> ServerRequestInterface:
    return server_request("GET", "https://api.example.com/me")


@pytest.mark.anyio
async def test_it_answers_the_request_the_validator_annotated() -> None:
    server = ResourceServer(InMemoryAccessTokenRepository(), _AnnotatingValidator())

    annotated = await server.validate_authenticated_request(_request())

    assert annotated.get_attribute("oauth_access_token_id") == "access-1"


@pytest.mark.anyio
async def test_the_validators_refusal_is_what_the_caller_sees() -> None:
    server = ResourceServer(InMemoryAccessTokenRepository(), _RefusingValidator())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await server.validate_authenticated_request(_request())

    assert refusal.value.get_error_type() == "access_denied"
