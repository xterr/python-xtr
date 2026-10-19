"""The token refresher renews what the security token carries, in place."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey
from typing_extensions import override
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.oidc.oidc_client_interface import OidcClientInterface
from xtr_security_http.oidc.oidc_discovery import OidcDiscovery
from xtr_security_http.oidc.oidc_id_token import OidcIdToken
from xtr_security_http.oidc.oidc_token_refresher import OidcTokenRefresher

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_client_contracts import HttpResponseInterface

_ISSUER = "https://issuer.example"
_CLIENT_ID = "client-1"
_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)


def _key() -> RSAKey:
    """A fresh RSA signing key."""
    return RSAKey.generate_key(2048, parameters={"kid": "k1"})


def _id_token(key: RSAKey, **claims: object) -> str:
    """A signed ID token carrying ``claims`` for the frozen clock."""
    return jwt.encode(
        {"alg": "RS256", "kid": key.kid},
        {
            "iss": _ISSUER,
            "aud": _CLIENT_ID,
            "sub": "alice",
            "iat": _NOW,
            "exp": _NOW + 3600,
            **claims,
        },
        key,
    )


@final
class _Token(AbstractToken):
    """A bare token carrying attributes, the way the firewall stores one."""


def _token(**attributes: object) -> _Token:
    """A token carrying ``attributes``."""
    token = _Token()
    for name, value in attributes.items():
        token.set_attribute(name, value)
    return token


@final
class _ScriptedClient(OidcClientInterface):
    """A client answering one refresh from a script."""

    def __init__(self, answer: dict[str, object] | Exception) -> None:
        self._answer = answer
        self.refresh_calls: list[str] = []

    @override
    async def request(
        self,
        endpoint: str,
        body: Mapping[str, object] | None = None,
        options: Mapping[str, object] | None = None,
    ) -> HttpResponseInterface:
        """Never called by the refresher."""
        raise NotImplementedError

    @override
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, object]:
        """Never called by the refresher."""
        raise NotImplementedError

    @override
    async def refresh_token(
        self,
        refresh_token: str,
        scopes: Sequence[str] = (),
    ) -> dict[str, object]:
        """Record the grant, answering from the script."""
        self.refresh_calls.append(refresh_token)
        if isinstance(self._answer, Exception):
            raise self._answer
        return dict(self._answer)

    @override
    async def fetch_user_info(self, access_token: str) -> dict[str, object]:
        """Never called by the refresher."""
        raise NotImplementedError

    @override
    def get_client_authentication_method(self) -> str:
        """Never asked by the refresher."""
        return "none"


def _discovery() -> OidcDiscovery:
    """A discovery reader answering the test issuer's document."""
    document = MockResponse(
        json.dumps({"issuer": _ISSUER}).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )
    return OidcDiscovery(
        MockHttpClient([document], base_uri=_ISSUER),
        ArrayAdapter(clock=MockClock(_FROZEN)),
        issuer=_ISSUER,
    )


def _refresher(
    client: OidcClientInterface,
    *,
    leeway: int = 30,
    clock: MockClock | None = None,
) -> OidcTokenRefresher:
    """A refresher over ``client``, its clock frozen at the test instant."""
    frozen = clock if clock is not None else MockClock(_FROZEN)
    return OidcTokenRefresher(
        client,
        _discovery(),
        OidcIdToken(frozen),
        _CLIENT_ID,
        leeway=leeway,
        clock=frozen,
    )


def _refresh_answer(**members: object) -> dict[str, object]:
    """A refresh grant answer, plus ``members``."""
    return {"token_type": "Bearer", "access_token": "at-2", "expires_in": 3600, **members}


@pytest.mark.anyio
async def test_a_far_expiry_is_not_renewed() -> None:
    key = _key()
    client = _ScriptedClient(_refresh_answer())
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_access_token_expires_at=_NOW + 3600,
        oidc_id_token=_id_token(key),
    )

    renewed = await refresher.refresh_if_needed(token)

    assert renewed is False
    assert client.refresh_calls == []


@pytest.mark.anyio
async def test_an_expiry_within_the_leeway_is_renewed() -> None:
    key = _key()
    client = _ScriptedClient(_refresh_answer())
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_access_token_expires_at=_NOW + 20,
        oidc_id_token=_id_token(key),
    )

    renewed = await refresher.refresh_if_needed(token)

    assert renewed is True
    assert client.refresh_calls == ["rt-1"]


@pytest.mark.anyio
async def test_a_token_without_a_refresh_token_is_left_alone() -> None:
    client = _ScriptedClient(_refresh_answer())
    refresher = _refresher(client)
    token = _token(oidc_access_token_expires_at=_NOW - 1)

    renewed = await refresher.refresh_if_needed(token)

    assert renewed is False


@pytest.mark.anyio
async def test_a_token_with_a_non_string_refresh_token_is_left_alone() -> None:
    client = _ScriptedClient(_refresh_answer())
    refresher = _refresher(client)
    token = _token(oidc_refresh_token=123, oidc_access_token_expires_at=_NOW - 1)

    renewed = await refresher.refresh_if_needed(token)

    assert renewed is False


@pytest.mark.anyio
async def test_a_token_without_an_expiry_is_left_alone() -> None:
    client = _ScriptedClient(_refresh_answer())
    refresher = _refresher(client)
    token = _token(oidc_refresh_token="rt-1")  # noqa: S106 -- an attribute name, not a credential

    renewed = await refresher.refresh_if_needed(token)

    assert renewed is False


@pytest.mark.anyio
async def test_refresh_stores_the_new_tokens() -> None:
    key = _key()
    client = _ScriptedClient(_refresh_answer(refresh_token="rt-2"))  # noqa: S106 -- a protocol member name, not a credential
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=_id_token(key),
    )

    await refresher.refresh(token)

    assert token.get_attribute("oidc_access_token") == "at-2"
    assert token.get_attribute("oidc_access_token_expires_at") == _NOW + 3600
    assert token.get_attribute("oidc_refresh_token") == "rt-2"


@pytest.mark.anyio
async def test_refresh_keeps_the_refresh_token_when_none_is_issued() -> None:
    key = _key()
    client = _ScriptedClient(_refresh_answer())
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=_id_token(key),
    )

    await refresher.refresh(token)

    assert token.get_attribute("oidc_refresh_token") == "rt-1"


@pytest.mark.anyio
async def test_refresh_stores_a_refreshed_id_token_and_its_sid() -> None:
    key = _key()
    client = _ScriptedClient(_refresh_answer(id_token=_id_token(key, sid="session-1")))
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=_id_token(key),
    )

    await refresher.refresh(token)

    assert token.get_attribute("oidc_id_token") == _id_token(key, sid="session-1")
    assert token.get_attribute("oidc_sid") == "session-1"


@pytest.mark.anyio
async def test_an_empty_sid_is_not_stored() -> None:
    key = _key()
    client = _ScriptedClient(_refresh_answer(id_token=_id_token(key, sid="")))
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=_id_token(key),
    )

    await refresher.refresh(token)

    assert not token.has_attribute("oidc_sid")


@pytest.mark.anyio
async def test_a_refreshed_id_token_of_another_subject_is_refused() -> None:
    key = _key()
    other = _id_token(key, sub="mallory")
    client = _ScriptedClient(_refresh_answer(id_token=other))
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=_id_token(key),
    )

    with pytest.raises(AuthenticationError) as raised:
        await refresher.refresh(token)

    assert '"sub" claim' in str(raised.value)
    # Nothing was stored: the token is exactly as it was.
    assert not token.has_attribute("oidc_access_token")


@pytest.mark.anyio
async def test_a_refreshed_id_token_of_another_audience_is_refused() -> None:
    key = _key()
    other = _id_token(key, aud="another-client")
    client = _ScriptedClient(_refresh_answer(id_token=other))
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=_id_token(key),
    )

    with pytest.raises(AuthenticationError):
        await refresher.refresh(token)


@pytest.mark.anyio
async def test_a_refresh_without_a_previous_id_token_is_refused() -> None:
    key = _key()
    client = _ScriptedClient(_refresh_answer(id_token=_id_token(key)))
    refresher = _refresher(client)
    token = _token(oidc_refresh_token="rt-1")  # noqa: S106 -- an attribute name, not a credential

    with pytest.raises(AuthenticationError) as raised:
        await refresher.refresh(token)

    assert "no OIDC ID token to compare" in str(raised.value)


@pytest.mark.anyio
async def test_a_refresh_without_a_refresh_token_is_refused() -> None:
    client = _ScriptedClient(_refresh_answer())
    refresher = _refresher(client)
    token = _Token()

    with pytest.raises(AuthenticationError) as raised:
        await refresher.refresh(token)

    assert "carries no OIDC refresh token" in str(raised.value)


@pytest.mark.anyio
async def test_an_answer_without_an_access_token_is_refused() -> None:
    key = _key()
    client = _ScriptedClient({"token_type": "Bearer"})
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=_id_token(key),
    )

    with pytest.raises(AuthenticationError) as raised:
        await refresher.refresh(token)

    assert "access_token" in str(raised.value)


@pytest.mark.anyio
async def test_an_answer_with_a_non_string_id_token_is_refused() -> None:
    key = _key()
    client = _ScriptedClient(_refresh_answer(id_token=123))
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=_id_token(key),
    )

    with pytest.raises(AuthenticationError) as raised:
        await refresher.refresh(token)

    assert '"id_token"' in str(raised.value)


@pytest.mark.anyio
async def test_a_previous_id_token_without_a_subject_is_refused() -> None:
    key = _key()
    client = _ScriptedClient(_refresh_answer(id_token=_id_token(key)))
    refresher = _refresher(client)
    subjectless = jwt.encode(
        {"alg": "RS256", "kid": key.kid},
        {"iss": _ISSUER, "aud": _CLIENT_ID, "iat": _NOW, "exp": _NOW + 3600},
        key,
    )
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=subjectless,
    )

    with pytest.raises(AuthenticationError) as raised:
        await refresher.refresh(token)

    assert '"sub" claim' in str(raised.value)


@pytest.mark.anyio
async def test_an_answer_without_an_expires_in_stores_no_expiry() -> None:
    key = _key()
    client = _ScriptedClient({"token_type": "Bearer", "access_token": "at-2"})
    refresher = _refresher(client)
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_id_token=_id_token(key),
    )

    await refresher.refresh(token)

    assert token.get_attribute("oidc_access_token_expires_at") is None
