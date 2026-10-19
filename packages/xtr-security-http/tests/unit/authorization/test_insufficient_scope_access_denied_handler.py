"""The insufficient-scope handler answers with an RFC 6750 scope challenge."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.exception import AccessDeniedError

from tests.support.messages import make_message
from xtr_security_http.authorization.insufficient_scope_access_denied_handler import (
    InsufficientScopeAccessDeniedHandler,
)
from xtr_security_http.authorization.oauth2_scope_voter import oauth2_scope

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

pytestmark = pytest.mark.anyio


@final
class _RecordingInner:
    """Answers as it was built to, recording what it was handed."""

    def __init__(self, response: ResponseInterface | None = None) -> None:
        self._response = response
        self.handled: tuple[ServerRequestInterface, AccessDeniedError] | None = None

    async def handle(
        self, request: ServerRequestInterface, error: AccessDeniedError
    ) -> ResponseInterface | None:
        self.handled = (request, error)
        return self._response


class _SchemeConstraint:
    """A sender constraint answering a fixed scheme, and parameters nobody reads."""

    def get_challenge(self, error: object) -> tuple[str, dict[str, str]]:
        del error
        return "DPoP", {"error": "invalid_dpop_proof"}

    async def check(
        self,
        request: ServerRequestInterface,
        access_token: str,
        claims: object,
    ) -> None:
        del request, access_token, claims


def test_it_builds_with_no_arguments_beyond_the_factory() -> None:
    handler = InsufficientScopeAccessDeniedHandler(ResponseFactory())

    assert isinstance(handler, InsufficientScopeAccessDeniedHandler)


def test_the_realm_stays_the_first_optional_argument() -> None:
    handler = InsufficientScopeAccessDeniedHandler(ResponseFactory(), "shop")

    assert isinstance(handler, InsufficientScopeAccessDeniedHandler)


async def test_it_names_the_missing_scope_and_realm() -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read", "books:write"),))

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory(), realm="shop").handle(
        make_message(), error
    )

    assert response is not None
    assert response.get_status_code() == 403
    challenge = response.get_header_line("www-authenticate")
    assert 'realm="shop"' in challenge
    assert 'error="insufficient_scope"' in challenge
    assert 'scope="books:read books:write"' in challenge


async def test_it_answers_with_an_empty_body() -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read"),))

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory()).handle(
        make_message(), error
    )

    assert response is not None
    assert await response.get_body().get_contents() == b""


async def test_it_carries_the_exact_upstream_challenge() -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read"),))

    response = await InsufficientScopeAccessDeniedHandler(
        ResponseFactory(),
        realm="shop",
        resource_metadata_uri="https://shop.example/.well-known/oauth-protected-resource",
    ).handle(make_message(), error)

    assert response is not None
    assert response.get_header_line("www-authenticate") == (
        'Bearer realm="shop",error="insufficient_scope",'
        'error_description="The request requires higher privileges than '
        'provided by the access token.",'
        'scope="books:read",'
        'resource_metadata="https://shop.example/.well-known/oauth-protected-resource"'
    )


async def test_it_omits_the_realm_when_unset() -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read"),))

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory()).handle(
        make_message(), error
    )

    assert response is not None
    assert "realm=" not in response.get_header_line("www-authenticate")


async def test_it_merges_and_deduplicates_the_scopes_of_every_attribute() -> None:
    error = AccessDeniedError(
        attributes=(
            oauth2_scope("books:read", "books:write"),
            "ROLE_ADMIN",
            123,
            oauth2_scope("books:write", "books:delete"),
        ),
    )

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory()).handle(
        make_message(), error
    )

    assert response is not None
    assert 'scope="books:read books:write books:delete"' in response.get_header_line(
        "www-authenticate"
    )


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        (
            "/.well-known/oauth-protected-resource",
            "https://example.com/.well-known/oauth-protected-resource",
        ),
        ("https://shop.example/metadata", "https://shop.example/metadata"),
    ],
)
async def test_it_resolves_the_resource_metadata_against_the_request(
    uri: str, expected: str
) -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read"),))

    response = await InsufficientScopeAccessDeniedHandler(
        ResponseFactory(),
        resource_metadata_uri=uri,
    ).handle(make_message(query="page=1"), error)

    assert response is not None
    assert f'resource_metadata="{expected}"' in response.get_header_line("www-authenticate")


async def test_it_names_the_scheme_of_the_sender_constraint() -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read"),))

    response = await InsufficientScopeAccessDeniedHandler(
        ResponseFactory(),
        sender_constraint=_SchemeConstraint(),
    ).handle(make_message(), error)

    assert response is not None
    challenge = response.get_header_line("www-authenticate")
    assert challenge.startswith("DPoP ")
    assert "invalid_dpop_proof" not in challenge


async def test_a_denial_no_scope_took_part_in_is_left_to_the_regular_handling() -> None:
    error = AccessDeniedError(attributes=("ROLE_ADMIN",))

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory()).handle(
        make_message(), error
    )

    assert response is None


async def test_a_denial_no_scope_took_part_in_is_handed_to_the_inner_handler() -> None:
    error = AccessDeniedError(attributes=("ROLE_ADMIN",))
    inner_response = ResponseFactory().create_response(403)
    inner = _RecordingInner(inner_response)
    request = make_message()

    response = await InsufficientScopeAccessDeniedHandler(
        ResponseFactory(),
        inner=inner,
    ).handle(request, error)

    assert response is inner_response
    assert inner.handled is not None
    assert inner.handled[0] is request
    assert inner.handled[1] is error


async def test_the_inner_handler_may_answer_none() -> None:
    error = AccessDeniedError(attributes=("ROLE_ADMIN",))
    inner = _RecordingInner(None)

    response = await InsufficientScopeAccessDeniedHandler(
        ResponseFactory(),
        inner=inner,
    ).handle(make_message(), error)

    assert response is None
    assert inner.handled is not None


async def test_the_challenge_is_not_cached() -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read"),))

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory()).handle(
        make_message(), error
    )

    assert response is not None
    assert response.get_header_line("cache-control") == "no-store"
    assert response.get_header_line("pragma") == "no-cache"
