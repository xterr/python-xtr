"""The chain step that renews the OIDC tokens the stored token carries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_http_kernel import RequestEvent
from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.exception import AuthenticationError

from tests.support.messages import make_message
from tests.support.recording_logger import RecordingLogger
from xtr_security_http.decorator.firewall_listener_order import firewall_listener_order_of
from xtr_security_http.exception import OidcInvalidGrantError
from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.firewall.context_listener import ContextListener
from xtr_security_http.firewall.oidc_token_refresh_listener import OidcTokenRefreshListener
from xtr_security_http.oidc.oidc_client_interface import OidcClientInterface
from xtr_security_http.oidc.oidc_discovery import OidcDiscovery
from xtr_security_http.oidc.oidc_id_token import OidcIdToken
from xtr_security_http.oidc.oidc_token_refresher import OidcTokenRefresher

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_client_contracts import HttpResponseInterface

pytestmark = pytest.mark.anyio

_ISSUER = "https://issuer.example"
_CLIENT_ID = "client-1"
_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)


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


def _refresher(client: OidcClientInterface) -> OidcTokenRefresher:
    """A refresher over ``client``, its clock frozen at the test instant."""
    frozen = MockClock(_FROZEN)
    return OidcTokenRefresher(
        client,
        _discovery(),
        OidcIdToken(frozen),
        _CLIENT_ID,
        clock=frozen,
    )


def _refresh_answer() -> dict[str, object]:
    """A refresh grant answer."""
    return {"token_type": "Bearer", "access_token": "at-2", "expires_in": 3600}


def _listener(
    refresher: OidcTokenRefresher,
    *,
    storage: TokenStorage | None = None,
    logger: RecordingLogger | None = None,
) -> OidcTokenRefreshListener:
    """A step over ``refresher`` and a storage holding no token."""
    return OidcTokenRefreshListener(
        storage if storage is not None else TokenStorage(),
        refresher,
        logger,
    )


def _request_event() -> RequestEvent:
    """A request event over a bare message."""
    return RequestEvent(make_message(path="/account"), {})


async def test_supports_answers_the_lazy_join() -> None:
    """``supports`` never decides: the storage is only read in ``authenticate``."""
    listener = _listener(_refresher(_ScriptedClient(_refresh_answer())))

    assert await listener.supports(make_message(path="/account")) is None


async def test_a_request_without_a_token_is_left_alone() -> None:
    """No stored token means no renewal: the refresher is never asked."""
    client = _ScriptedClient(_refresh_answer())
    logger = RecordingLogger()
    listener = _listener(_refresher(client), logger=logger)

    await listener.authenticate(_request_event())

    assert client.refresh_calls == []
    assert logger.records == []


async def test_a_token_without_the_oidc_attributes_is_skipped() -> None:
    """A token carrying no refresh token has nothing the refresher renews."""
    client = _ScriptedClient(_refresh_answer())
    logger = RecordingLogger()
    storage = TokenStorage()
    storage.set_token(_token())
    listener = _listener(_refresher(client), storage=storage, logger=logger)

    await listener.authenticate(_request_event())

    assert client.refresh_calls == []
    assert logger.records == []
    assert storage.get_token() is not None


async def test_a_token_without_an_expiry_is_skipped() -> None:
    """A refresh token without an expiry says nothing about staleness."""
    client = _ScriptedClient(_refresh_answer())
    logger = RecordingLogger()
    storage = TokenStorage()
    storage.set_token(_token(oidc_refresh_token="rt-1"))  # noqa: S106 -- an attribute name, not a credential
    listener = _listener(_refresher(client), storage=storage, logger=logger)

    await listener.authenticate(_request_event())

    assert client.refresh_calls == []
    assert logger.records == []


async def test_a_far_expiry_is_not_renewed() -> None:
    """An access token outside the refresher's leeway is left as it is."""
    client = _ScriptedClient(_refresh_answer())
    logger = RecordingLogger()
    storage = TokenStorage()
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_access_token_expires_at=_NOW + 3600,
    )
    storage.set_token(token)
    listener = _listener(_refresher(client), storage=storage, logger=logger)

    await listener.authenticate(_request_event())

    assert client.refresh_calls == []
    assert logger.records == []
    assert storage.get_token() is token


async def test_an_expiry_within_the_leeway_is_renewed_in_place() -> None:
    """A due token is handed to the refresher and keeps its seat in the storage."""
    client = _ScriptedClient(_refresh_answer())
    logger = RecordingLogger()
    storage = TokenStorage()
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_access_token_expires_at=_NOW + 10,
    )
    storage.set_token(token)
    listener = _listener(_refresher(client), storage=storage, logger=logger)

    await listener.authenticate(_request_event())

    assert client.refresh_calls == ["rt-1"]
    assert token.get_attribute("oidc_access_token") == "at-2"
    assert token.get_attribute("oidc_access_token_expires_at") == _NOW + 3600
    assert storage.get_token() is token
    assert logger.messages("debug") == ["Renewed the OIDC access token of the logged-in user."]


async def test_an_invalid_grant_clears_the_token() -> None:
    """A refresh token the provider no longer honors ends the login."""
    error = OidcInvalidGrantError("The OIDC provider rejected the refresh token.")
    client = _ScriptedClient(error)
    logger = RecordingLogger()
    storage = TokenStorage()
    storage.set_token(
        _token(
            oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
            oidc_access_token_expires_at=_NOW + 10,
        ),
    )
    listener = _listener(_refresher(client), storage=storage, logger=logger)

    await listener.authenticate(_request_event())

    assert storage.get_token() is None
    assert logger.messages("info") == [
        "The OIDC provider no longer honors the refresh token; logging the user out.",
    ]
    assert logger.contexts("info") == [{"exception": error}]


async def test_another_authentication_error_is_swallowed_and_logged() -> None:
    """Any other renewal failure costs a warning, not the login."""
    error = AuthenticationError("The provider is unreachable.")
    client = _ScriptedClient(error)
    logger = RecordingLogger()
    storage = TokenStorage()
    token = _token(
        oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
        oidc_access_token_expires_at=_NOW + 10,
    )
    storage.set_token(token)
    listener = _listener(_refresher(client), storage=storage, logger=logger)

    await listener.authenticate(_request_event())

    assert storage.get_token() is token
    assert logger.messages("warning") == [
        "Could not renew the OIDC access token of the logged-in user.",
    ]
    assert logger.contexts("warning") == [{"exception": error}]
    assert logger.messages("info") == []


async def test_an_unexpected_error_propagates() -> None:
    """Only the two authentication failures are answered here; the rest crash the chain."""
    client = _ScriptedClient(ValueError("a broken client"))
    storage = TokenStorage()
    storage.set_token(
        _token(
            oidc_refresh_token="rt-1",  # noqa: S106 -- an attribute name, not a credential
            oidc_access_token_expires_at=_NOW + 10,
        ),
    )
    listener = _listener(_refresher(client), storage=storage)

    with pytest.raises(ValueError, match="a broken client"):
        await listener.authenticate(_request_event())


def test_the_step_orders_after_the_context_listener() -> None:
    """The step keeps the default priority and declares its only neighbour."""
    order = firewall_listener_order_of(OidcTokenRefreshListener)

    assert order is not None
    assert order.before == ()
    assert order.after == (ContextListener,)
    assert OidcTokenRefreshListener.get_priority() == ContextListener.get_priority()
    assert OidcTokenRefreshListener.get_priority() == AbstractListener.get_priority()
