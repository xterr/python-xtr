"""The OIDC client authenticates at the token endpoint and presents the token."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_cache import ArrayAdapter
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.exception import OidcInvalidGrantError
from xtr_security_http.oauth2.client_authentication.client_secret_post import (
    ClientSecretPost,
)
from xtr_security_http.oauth2.client_authentication.no_client_authentication import (
    NoClientAuthentication,
)
from xtr_security_http.oidc.oidc_client import OidcClient
from xtr_security_http.oidc.oidc_discovery import OidcDiscovery

if TYPE_CHECKING:
    from xtr_http_client_contracts import RequestOptions


_ISSUER = "https://issuer.example"
_TOKEN_ENDPOINT = "https://issuer.example/token"  # noqa: S105 -- an endpoint URL, not a credential
_USERINFO_ENDPOINT = "https://issuer.example/userinfo"
_DOCUMENT_URI = "https://issuer.example/.well-known/openid-configuration"
_CLIENT_ID = "client-1"


def _json_response(body: object, *, status: int = 200) -> MockResponse:
    """A JSON answer carrying ``body``."""
    return MockResponse(
        json.dumps(body).encode(),
        {"http_code": status, "response_headers": {"Content-Type": "application/json"}},
    )


def _document(**members: object) -> MockResponse:
    """The test issuer's discovery document, plus ``members``."""
    return _json_response(
        {
            "issuer": _ISSUER,
            "token_endpoint": _TOKEN_ENDPOINT,
            "userinfo_endpoint": _USERINFO_ENDPOINT,
            "revocation_endpoint": "https://issuer.example/revoke",
            "mtls_endpoint_aliases": {
                "token_endpoint": "https://issuer.example/token-mtls",
                "userinfo_endpoint": "http://issuer.example/userinfo-mtls",
            },
            **members,
        },
    )


def _body(options: RequestOptions) -> dict[str, object]:
    """Read a request's form body back as the mapping the test wrote."""
    return cast("dict[str, object]", options.get("body"))


@final
class _Recorder:
    """A scripted issuer recording every request it answers."""

    def __init__(self, *answers: MockResponse) -> None:
        self.requests: list[tuple[str, str, RequestOptions]] = []
        self._answers = list(answers)

    def answer(self, method: str, url: str, options: RequestOptions) -> MockResponse:
        """Record the request, answering from the script or the document."""
        self.requests.append((method, url, options))
        if url == _DOCUMENT_URI:
            return _document()
        return self._answers.pop(0) if self._answers else _json_response({})

    def client(self) -> MockHttpClient:
        """A client answering this issuer's paths."""
        return MockHttpClient(self.answer, base_uri=_ISSUER)


def _client(
    recorder: _Recorder,
    *,
    authentication: object = None,
    certificate_options: dict[str, object] | None = None,
) -> OidcClient:
    """An OIDC client over ``recorder``, a public client by default."""
    http_client = recorder.client()
    discovery = OidcDiscovery(http_client, ArrayAdapter(), issuer=_ISSUER)
    return OidcClient(
        http_client,
        discovery,
        _CLIENT_ID,
        authentication  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        if authentication is not None
        else NoClientAuthentication(),
        certificate_options,
    )


def _token_response(**members: object) -> MockResponse:
    """An access-token response, plus ``members``."""
    return _json_response({"token_type": "Bearer", "access_token": "at-1", **members})


@pytest.mark.anyio
async def test_request_posts_to_the_announced_endpoint_with_the_client_id() -> None:
    recorder = _Recorder(_json_response({}))
    client_ = _client(recorder)

    _ = await client_.request("revocation_endpoint", {"token": "at-1"})

    method, url, options = recorder.requests[-1]
    assert method == "POST"
    assert url == "https://issuer.example/revoke"
    assert _body(options) == {"token": "at-1", "client_id": _CLIENT_ID}
    assert options.get("max_redirects") == 0


@pytest.mark.anyio
async def test_request_applies_the_client_authentication() -> None:
    recorder = _Recorder(_json_response({}))
    client_ = _client(recorder, authentication=ClientSecretPost("the-secret"))

    _ = await client_.request("token_endpoint", {"grant_type": "authorization_code"})

    assert _body(recorder.requests[-1][2])["client_secret"] == "the-secret"  # noqa: S105 -- a protocol member name, not a credential


@pytest.mark.anyio
async def test_the_client_authentication_is_told_the_token_endpoint() -> None:
    recorder = _Recorder(_json_response({}))
    client_ = _client(recorder, authentication=ClientSecretPost("the-secret"))

    _ = await client_.request("revocation_endpoint", {})

    # The assertion method signs the audience it is handed; the token
    # endpoint is what it must be handed, whatever endpoint is called.
    assert _body(recorder.requests[-1][2])["client_secret"] == "the-secret"  # noqa: S105 -- a protocol member name, not a credential


@pytest.mark.anyio
async def test_the_certificate_options_win_over_the_request_options() -> None:
    recorder = _Recorder(_json_response({}))
    client_ = _client(
        recorder,
        certificate_options={"local_cert": "/certs/client.pem", "timeout": 5.0},
    )

    _ = await client_.request("token_endpoint", {}, {"timeout": 30.0})

    assert recorder.requests[-1][2].get("local_cert") == "/certs/client.pem"
    assert recorder.requests[-1][2].get("timeout") == 5.0


@pytest.mark.anyio
async def test_an_mtls_alias_is_used_when_the_client_presents_a_certificate() -> None:
    recorder = _Recorder(_json_response({}))
    client_ = _client(
        recorder,
        certificate_options={"local_cert": "/certs/client.pem"},
    )

    _ = await client_.request("token_endpoint", {})

    assert recorder.requests[-1][1] == "https://issuer.example/token-mtls"


@pytest.mark.anyio
async def test_an_insecure_mtls_alias_is_refused() -> None:
    recorder = _Recorder(_json_response({}))
    client_ = _client(
        recorder,
        certificate_options={"local_cert": "/certs/client.pem"},
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await client_.fetch_user_info("at-1")

    assert "mtls_endpoint_aliases" in str(raised.value)


@pytest.mark.anyio
async def test_a_missing_endpoint_is_refused() -> None:
    recorder = _Recorder(_json_response({}))
    client_ = _client(recorder)

    with pytest.raises(AuthenticationError) as raised:
        _ = await client_.request("pushed_authorization_request_endpoint", {})

    assert "does not announce any" in str(raised.value)


@pytest.mark.anyio
async def test_exchange_code_posts_the_grant() -> None:
    recorder = _Recorder(_token_response())
    client_ = _client(recorder)

    members = await client_.exchange_code("the-code", "https://app.example/cb", "the-verifier")

    _, _, options = recorder.requests[-1]
    assert _body(options)["grant_type"] == "authorization_code"
    assert _body(options)["code"] == "the-code"
    assert _body(options)["redirect_uri"] == "https://app.example/cb"
    assert _body(options)["code_verifier"] == "the-verifier"
    assert members["access_token"] == "at-1"  # noqa: S105 -- a protocol member name, not a credential


@pytest.mark.anyio
async def test_exchange_code_without_a_verifier_leaves_it_out() -> None:
    recorder = _Recorder(_token_response())
    client_ = _client(recorder, authentication=ClientSecretPost("the-secret"))

    _ = await client_.exchange_code("the-code", "https://app.example/cb")

    assert "code_verifier" not in _body(recorder.requests[-1][2])


@pytest.mark.anyio
async def test_a_token_of_another_type_is_refused() -> None:
    recorder = _Recorder(_json_response({"token_type": "DPoP", "access_token": "at-1"}))
    client_ = _client(recorder, authentication=ClientSecretPost("the-secret"))

    with pytest.raises(AuthenticationError):
        _ = await client_.exchange_code("the-code", "https://app.example/cb")


@pytest.mark.anyio
async def test_an_unreachable_token_endpoint_is_wrapped() -> None:
    recorder = _Recorder(MockResponse(b"", {"error": "no answer"}))
    client_ = _client(recorder, authentication=ClientSecretPost("the-secret"))

    with pytest.raises(AuthenticationError) as raised:
        _ = await client_.exchange_code("the-code", "https://app.example/cb")

    assert "token endpoint request failed" in str(raised.value)


@pytest.mark.anyio
async def test_refresh_token_posts_the_grant_with_the_scopes_joined() -> None:
    recorder = _Recorder(_token_response())
    client_ = _client(recorder)

    _ = await client_.refresh_token("rt-1", ["books:read", "books:write"])

    _, _, options = recorder.requests[-1]
    assert _body(options)["grant_type"] == "refresh_token"
    assert _body(options)["refresh_token"] == "rt-1"  # noqa: S105 -- a protocol member name, not a credential
    assert _body(options)["scope"] == "books:read books:write"


@pytest.mark.anyio
async def test_a_rejected_refresh_token_raises_the_invalid_grant_error() -> None:
    recorder = _Recorder(
        _json_response({"error": "invalid_grant"}, status=400),
    )
    client_ = _client(recorder)

    with pytest.raises(OidcInvalidGrantError) as raised:
        _ = await client_.refresh_token("rt-1")

    assert str(raised.value.MESSAGE_KEY) == "The OIDC provider rejected the grant."


@pytest.mark.anyio
async def test_another_client_error_is_an_authentication_error() -> None:
    recorder = _Recorder(_json_response({"error": "invalid_client"}, status=401))
    client_ = _client(recorder)

    with pytest.raises(AuthenticationError) as raised:
        _ = await client_.refresh_token("rt-1")

    assert not isinstance(raised.value, OidcInvalidGrantError)


@pytest.mark.anyio
async def test_fetch_userinfo_gets_the_endpoint_with_the_bearer_token() -> None:
    recorder = _Recorder(_json_response({"sub": "alice"}))
    client_ = _client(recorder)

    claims = await client_.fetch_user_info("at-1")

    method, url, options = recorder.requests[-1]
    assert method == "GET"
    assert url == _USERINFO_ENDPOINT
    assert options.get("auth_bearer") == "at-1"
    assert options.get("max_redirects") == 0
    assert claims == {"sub": "alice"}


@pytest.mark.anyio
async def test_an_unreachable_userinfo_endpoint_is_wrapped() -> None:
    recorder = _Recorder(MockResponse(b"", {"error": "no answer"}))
    client_ = _client(recorder, authentication=ClientSecretPost("the-secret"))

    with pytest.raises(AuthenticationError) as raised:
        _ = await client_.fetch_user_info("at-1")

    assert "userinfo endpoint request failed" in str(raised.value)


def test_the_client_authentication_method_is_delegated() -> None:
    recorder = _Recorder()
    client_ = _client(recorder, authentication=ClientSecretPost("the-secret"))

    assert client_.get_client_authentication_method() == "client_secret_post"
