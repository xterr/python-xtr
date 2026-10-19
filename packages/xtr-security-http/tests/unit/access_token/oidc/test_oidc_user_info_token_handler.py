"""The OIDC userinfo token handler reads the user off the issuer's userinfo endpoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, TypeVar, final

import pytest
from xtr_cache import ArrayAdapter, CacheItem
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.in_memory_user_provider import InMemoryUserProvider
from xtr_security_core.user.oidc_user import OidcUser

from tests.support.messages import make_message
from tests.support.recording_logger import RecordingLogger
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.access_token.oidc import MissingClaimError, OidcUserInfoTokenHandler
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.fallback_user_loader import FallbackUserLoader
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.exception import InvalidAccessTokenError

if TYPE_CHECKING:
    from xtr_cache_contracts import Callback
    from xtr_http_client_contracts import HttpClientInterface, RequestOptions

_ISSUER = "https://issuer.example"
_USERINFO_URI = "https://issuer.example/userinfo"
_CONFIGURATION_URI = "https://issuer.example/.well-known/openid-configuration"

_CLAIMS: dict[str, object] = {
    "sub": "alice",
    "email": "alice@example.com",
    "email_verified": True,
    "roles": ["ROLE_ADMIN"],
}

_T = TypeVar("_T")


def _json_response(body: object) -> MockResponse:
    """A JSON answer carrying ``body``."""
    return MockResponse(
        json.dumps(body).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


def _client(
    *answers: MockResponse,
    base_uri: str = _USERINFO_URI,
) -> MockHttpClient:
    """A client answering from ``answers``, in order, its base URI at ``base_uri``."""
    return MockHttpClient(list(answers), base_uri=base_uri)


def _recording_client(
    requests: list[tuple[str, str, RequestOptions]],
    answer: MockResponse,
    base_uri: str = _USERINFO_URI,
) -> MockHttpClient:
    """A client recording every request it answers with ``answer``."""

    def answer_with(method: str, url: str, options: RequestOptions) -> MockResponse:
        requests.append((method, url, options))
        return answer

    return MockHttpClient(answer_with, base_uri=base_uri)


def _handler(
    client: HttpClientInterface | None = None,
    *,
    claim: str = "sub",
    logger: RecordingLogger | None = None,
) -> OidcUserInfoTokenHandler:
    """A handler over ``client``, reading the identifier from ``claim``."""
    return OidcUserInfoTokenHandler(
        client if client is not None else MockHttpClient(),
        logger,
        claim,
    )


@final
class _RecordingCache:
    """A cache that computes on every call, keeping the keys it saw."""

    def __init__(self) -> None:
        self.keys: list[str] = []

    async def get(
        self,
        key: str,
        callback: Callback[_T],
        /,
        *,
        beta: float | None = None,
        metadata: object = None,
    ) -> _T:
        """Compute the value, recording the key it was computed for."""
        del beta, metadata
        self.keys.append(key)
        return await callback(CacheItem(key))

    async def delete(self, key: str, /) -> bool:
        """Remove nothing; this cache holds nothing."""
        del key
        return True


@pytest.mark.anyio
async def test_the_userinfo_endpoint_is_reached_with_the_token_as_its_bearer_credential() -> None:
    requests: list[tuple[str, str, RequestOptions]] = []
    client = _recording_client(requests, _json_response(_CLAIMS))

    _ = await _handler(client).get_user_badge_from("the-token")

    method, url, options = requests[0]
    assert method == "GET"
    assert url == _USERINFO_URI
    assert options.get("auth_bearer") == "the-token"
    assert options.get("max_redirects") == 0


@pytest.mark.anyio
async def test_the_identifier_is_read_from_the_sub_claim_by_default() -> None:
    handler = _handler(_client(_json_response(_CLAIMS)))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_the_identifier_is_read_from_the_configured_claim() -> None:
    handler = _handler(_client(_json_response(_CLAIMS)), claim="email")

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice@example.com"


@pytest.mark.anyio
async def test_a_numeric_identifier_claim_is_read_as_text() -> None:
    handler = _handler(_client(_json_response({"sub": 12345})))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "12345"


@pytest.mark.anyio
async def test_the_badge_carries_the_claims_as_its_attributes() -> None:
    handler = _handler(_client(_json_response(_CLAIMS)))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_attributes() == _CLAIMS


@pytest.mark.anyio
async def test_the_badge_loader_is_wrapped_in_a_fallback_user_loader() -> None:
    handler = _handler(_client(_json_response(_CLAIMS)))

    badge = await handler.get_user_badge_from("the-token")

    assert isinstance(badge.get_user_loader(), FallbackUserLoader)


@pytest.mark.anyio
async def test_the_badge_loader_builds_the_oidc_user_the_claims_describe() -> None:
    handler = _handler(_client(_json_response(_CLAIMS)))

    badge = await handler.get_user_badge_from("the-token")
    user = await badge.get_user()

    assert isinstance(user, OidcUser)
    assert user.get_user_identifier() == "alice"
    assert user.get_email() == "alice@example.com"
    assert user.get_email_verified() is True
    assert user.get_roles() == ("ROLE_ADMIN",)


@pytest.mark.anyio
async def test_the_identifier_claim_names_the_user_over_one_the_claims_carried() -> None:
    handler = _handler(_client(_json_response({**_CLAIMS, "user_identifier": "alice@local"})))

    badge = await handler.get_user_badge_from("the-token")
    user = await badge.get_user()

    assert isinstance(user, OidcUser)
    assert user.get_user_identifier() == "alice"
    assert user.get_sub() == "alice"


@pytest.mark.anyio
async def test_a_missing_claim_is_refused_and_wrapped() -> None:
    handler = _handler(_client(_json_response({"email": "alice@example.com"})))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert isinstance(raised.value.__cause__, MissingClaimError)
    assert str(raised.value.__cause__) == '"sub" claim not found on OIDC server response.'


@pytest.mark.anyio
async def test_an_empty_claim_is_refused() -> None:
    handler = _handler(_client(_json_response({"sub": ""})))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert isinstance(raised.value.__cause__, MissingClaimError)


@pytest.mark.anyio
async def test_a_claim_holding_an_unusable_value_is_refused() -> None:
    handler = _handler(_client(_json_response({"sub": ["alice"]})))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert isinstance(raised.value.__cause__, MissingClaimError)


@pytest.mark.anyio
async def test_an_unreachable_server_is_wrapped_and_logged() -> None:
    logger = RecordingLogger()
    handler = _handler(_client(MockResponse(b"", {"error": "no answer"})), logger=logger)

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value).startswith("An error occurred on the OIDC server:")
    assert logger.messages("error") == ["An error occurred on the OIDC server."]


@pytest.mark.anyio
async def test_a_refused_token_is_wrapped() -> None:
    handler = _handler(
        _client(
            MockResponse(
                json.dumps({"error": "invalid_token"}).encode(),
                {"http_code": 401, "response_headers": {"Content-Type": "application/json"}},
            ),
        ),
    )

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_an_answer_that_is_not_a_json_object_is_wrapped() -> None:
    handler = _handler(_client(_json_response(["not", "an", "object"])))

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_discovery_reads_the_userinfo_endpoint_off_the_document() -> None:
    requests: list[tuple[str, str, RequestOptions]] = []

    def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
        requests.append((method, url, options))
        if url == _CONFIGURATION_URI:
            return _json_response({"userinfo_endpoint": _USERINFO_URI})
        return _json_response(_CLAIMS)

    handler = _handler(MockHttpClient(answer, base_uri=_ISSUER))
    handler.enable_discovery(ArrayAdapter(), "oidc")

    badge = await handler.get_user_badge_from("the-token")

    assert requests[0][0] == "GET"
    assert requests[0][1] == _CONFIGURATION_URI
    assert requests[0][2].get("max_redirects") == 0
    assert requests[1][0] == "GET"
    assert requests[1][1] == _USERINFO_URI
    assert requests[1][2].get("auth_bearer") == "the-token"
    assert requests[1][2].get("max_redirects") == 0
    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_the_discovery_document_is_cached_under_the_key_with_its_suffix() -> None:
    cache = _RecordingCache()
    client = _client(
        _json_response({"userinfo_endpoint": _USERINFO_URI}),
        _json_response(_CLAIMS),
        base_uri=_ISSUER,
    )
    handler = _handler(client)
    handler.enable_discovery(cache, "oidc")

    _ = await handler.get_user_badge_from("the-token")

    assert cache.keys == ["oidc.document"]


@pytest.mark.anyio
async def test_a_cached_document_answers_the_second_call_without_a_fetch() -> None:
    client = _client(
        _json_response({"userinfo_endpoint": _USERINFO_URI}),
        _json_response(_CLAIMS),
        _json_response(_CLAIMS),
        base_uri=_ISSUER,
    )
    handler = _handler(client)
    handler.enable_discovery(ArrayAdapter(), "oidc")

    first = await handler.get_user_badge_from("the-token")
    second = await handler.get_user_badge_from("the-token")

    assert first.get_user_identifier() == "alice"
    assert second.get_user_identifier() == "alice"
    assert client.get_requests_count() == 3


@pytest.mark.anyio
async def test_a_document_announcing_no_userinfo_endpoint_is_refused() -> None:
    handler = _handler(_client(_json_response({"issuer": _ISSUER}), base_uri=_ISSUER))
    handler.enable_discovery(ArrayAdapter(), "oidc")

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert (
        str(raised.value) == 'The "userinfo_endpoint" is missing from the OIDC discovery document.'
    )


@pytest.mark.anyio
async def test_an_http_endpoint_of_an_https_discovery_url_is_refused_before_caching() -> None:
    client = _client(
        _json_response({"userinfo_endpoint": "http://issuer.example/userinfo"}),
        _json_response({"userinfo_endpoint": "http://issuer.example/userinfo"}),
        base_uri=_ISSUER,
    )
    handler = _handler(client)
    handler.enable_discovery(ArrayAdapter(), "oidc")

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")
    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        'The "userinfo_endpoint" found in the OIDC discovery document must use the '
        '"https" scheme, "http" given.'
    )
    assert client.get_requests_count() == 2


@pytest.mark.anyio
async def test_an_http_endpoint_of_an_http_discovery_url_is_allowed() -> None:
    handler = _handler(
        _client(
            _json_response({"userinfo_endpoint": "http://issuer.example/userinfo"}),
            _json_response(_CLAIMS),
            base_uri="http://issuer.example",
        ),
    )
    handler.enable_discovery(ArrayAdapter(), "oidc")

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_an_unreachable_discovery_document_is_wrapped_and_logged() -> None:
    logger = RecordingLogger()
    handler = _handler(
        _client(MockResponse(b"", {"error": "no answer"}), base_uri=_ISSUER),
        logger=logger,
    )
    handler.enable_discovery(ArrayAdapter(), "oidc")

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value).startswith(
        "An error occurred while requesting the OIDC configuration:"
    )
    assert logger.messages("error") == [
        "An error occurred while requesting the OIDC configuration.",
    ]


@pytest.mark.anyio
async def test_a_discovery_document_that_is_not_json_is_wrapped() -> None:
    handler = _handler(
        _client(MockResponse(b"not json", {"http_code": 200}), base_uri=_ISSUER),
    )
    handler.enable_discovery(ArrayAdapter(), "oidc")

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value).startswith("The OIDC discovery document could not be decoded:")


@pytest.mark.anyio
async def test_a_discovery_document_that_is_not_a_json_object_is_refused() -> None:
    handler = _handler(
        _client(_json_response(["not", "an", "object"]), base_uri=_ISSUER),
    )
    handler.enable_discovery(ArrayAdapter(), "oidc")

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == "The OIDC discovery document is not a JSON object."


@pytest.mark.anyio
async def test_an_oversized_discovery_document_is_refused() -> None:
    bulk = {"padding": "x" * (1024 * 1024 + 1)}
    handler = _handler(_client(_json_response(bulk), base_uri=_ISSUER))
    handler.enable_discovery(ArrayAdapter(), "oidc")

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == "The OIDC discovery document exceeds the maximum size of 1 MiB."


@pytest.mark.anyio
async def test_the_authenticator_leaves_the_marked_loader_to_its_claims() -> None:
    handler = _handler(_client(_json_response(_CLAIMS)))
    authenticator = AccessTokenAuthenticator(
        handler,
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )

    passport = await authenticator.authenticate(
        make_message(headers={"Authorization": "Bearer the-token"}),
    )
    badge = passport.get_badge(UserBadge)
    assert badge is not None
    user = await badge.get_user()

    assert isinstance(user, OidcUser)
    assert user.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_the_authenticator_replaces_the_marked_loader_with_the_user_provider() -> None:
    handler = _handler(_client(_json_response(_CLAIMS)))
    authenticator = AccessTokenAuthenticator(
        handler,
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
        user_provider=InMemoryUserProvider(
            {"alice": InMemoryUser("alice", roles=["ROLE_OWN"], enabled=True)},
        ),
    )

    passport = await authenticator.authenticate(
        make_message(headers={"Authorization": "Bearer the-token"}),
    )
    badge = passport.get_badge(UserBadge)
    assert badge is not None
    user = await badge.get_user()

    assert isinstance(user, InMemoryUser)
    assert user.get_roles() == ("ROLE_OWN",)
