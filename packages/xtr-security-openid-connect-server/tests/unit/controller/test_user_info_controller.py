"""The userinfo controller, built by hand, answers only a signed-in end-user's own token.

No container and no firewall: the token a firewall would have settled on is put
in the storage directly, and the answer is read back as a client would.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_http_kernel.bridge import Response
from xtr_http_message import ServerRequest
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_oauth2_server.entity import Client
from xtr_security_oauth2_server.security.authentication.token.oauth2_token import OAuth2Token

from tests.support.identity_provider import ClaimsUser, InMemoryIdentityProvider
from tests.support.repositories import InMemoryClientRepository
from xtr_security_openid_connect_server.claim_extractor import ClaimExtractor
from xtr_security_openid_connect_server.controller.user_info_controller import UserInfoController
from xtr_security_openid_connect_server.entities.claim_set_entity import ClaimSetEntity

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )

    from xtr_security_openid_connect_server.entities.user_claims_entity_interface import (
        UserClaimsEntityInterface,
    )
    from xtr_security_openid_connect_server.repositories.identity_provider_interface import (
        IdentityProviderInterface,
    )

pytestmark = pytest.mark.anyio

_CLIENT_ID = "my-client"


@final
class _OneUserIdentityProvider:
    """Answers every identifier with the one user it holds.

    A deployment's own provider names a user whatever it keeps them under, and
    holds whatever claims it was given; this holds one of each, so what the
    answer's subject is read from shows.
    """

    __slots__ = ("_user",)

    def __init__(self, user: ClaimsUser) -> None:
        self._user = user

    async def get_user_entity_by_identifier(
        self,
        identifier: str,
        client: ClientEntityInterface,
    ) -> UserClaimsEntityInterface:
        del identifier, client  # The one user it holds answers for every token.
        return self._user


def _oauth2_token(scopes: tuple[str, ...], client_id: str = _CLIENT_ID) -> OAuth2Token:
    return OAuth2Token(
        InMemoryUser("alice", roles=["ROLE_USER"]),
        "userinfo",
        "token-1",
        client_id,
        scopes,
        "ROLE_OAUTH2_",
    )


def _controller(
    token: TokenInterface | None,
    claim_extractor: ClaimExtractor | None = None,
    identity_provider: IdentityProviderInterface | None = None,
) -> UserInfoController:
    storage = TokenStorage()
    storage.set_token(token)
    clients = InMemoryClientRepository()
    client = Client()
    client.set_identifier(_CLIENT_ID)
    clients.add(client)
    return UserInfoController(
        storage,
        clients,
        identity_provider if identity_provider is not None else InMemoryIdentityProvider(),
        claim_extractor if claim_extractor is not None else ClaimExtractor(),
    )


async def _answer(
    controller: UserInfoController,
    request: ServerRequest | None = None,
) -> tuple[Response, Mapping[str, object]]:
    answered = await controller.index_action(
        request if request is not None else ServerRequest("GET", "/userinfo"),
        Response(),
    )
    body = await answered.get_body().get_contents()
    return answered, cast("Mapping[str, object]", json.loads(body))


async def test_the_claims_the_granted_scopes_reveal_are_answered_with_the_subject() -> None:
    answered, document = await _answer(_controller(_oauth2_token(("openid", "email"))))

    assert answered.get_status_code() == 200
    assert document == {"sub": "alice", "email": "alice@example.com", "email_verified": True}


async def test_no_claim_replaces_the_subject() -> None:
    # A deployment's own claim set may name a claim ``sub``; the subject the
    # token names still answers.
    extractor = ClaimExtractor((ClaimSetEntity("account", ("sub", "name")),))
    provider = _OneUserIdentityProvider(
        ClaimsUser("alice", {"sub": "not-alice", "name": "Alice"}),
    )
    controller = _controller(_oauth2_token(("openid", "account")), extractor, provider)

    _, document = await _answer(controller)

    assert document == {"sub": "alice", "name": "Alice"}


async def test_the_subject_is_the_end_user_the_token_was_issued_for() -> None:
    # The identity provider keeps the user under an identifier of its own; the
    # answer's subject is the one the token was issued for, because that is
    # what the ID token named and what a client compares it against.
    extractor = ClaimExtractor((ClaimSetEntity("account", ("name",)),))
    provider = _OneUserIdentityProvider(
        ClaimsUser("alice@the-identity-provider", {"name": "Alice"}),
    )
    controller = _controller(_oauth2_token(("openid", "account")), extractor, provider)

    _, document = await _answer(controller)

    assert document == {"sub": "alice", "name": "Alice"}


async def test_a_token_no_access_token_proved_is_refused() -> None:
    token = PostAuthenticationToken(InMemoryUser("alice"), "main", ["ROLE_USER"])

    answered, document = await _answer(_controller(token))

    assert answered.get_status_code() == 401
    assert document["error"] == "invalid_token"


async def test_a_token_issued_to_a_client_no_longer_registered_is_refused() -> None:
    answered, document = await _answer(_controller(_oauth2_token(("openid",), "gone-client")))

    assert answered.get_status_code() == 401
    assert document["error"] == "invalid_token"


async def test_a_form_posted_with_a_charset_is_read_as_a_form() -> None:
    request = ServerRequest(
        "POST",
        "/userinfo",
        {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )

    answered, _ = await _answer(_controller(_oauth2_token(("openid",))), request)

    assert answered.get_status_code() == 200


async def test_a_post_carrying_no_content_type_is_refused_as_malformed() -> None:
    request = ServerRequest("POST", "/userinfo")

    answered, document = await _answer(_controller(_oauth2_token(("openid",))), request)

    assert answered.get_status_code() == 400
    assert document["error"] == "invalid_request"


async def test_a_refusal_carries_the_bearer_challenge_naming_the_error() -> None:
    answered, _ = await _answer(_controller(None))

    assert answered.get_header_line("www-authenticate") == (
        'Bearer error="invalid_token", '
        'error_description="The access token does not stand for a signed-in end-user."'
    )


def test_it_is_described_by_its_type_alone() -> None:
    assert repr(_controller(None)) == "UserInfoController()"
