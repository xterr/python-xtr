from __future__ import annotations

import socket
from typing import TYPE_CHECKING, NoReturn

import anyio
import httpx
import pytest
from typing_extensions import override

from xtr_webhook.bridge.httpx import NoPrivateNetworkTransport
from xtr_webhook.exception import PrivateNetworkError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

pytestmark = pytest.mark.anyio

_Resolved = list[tuple[int, int, int, str, tuple[str, int]]]


def _recording(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202)

    return httpx.MockTransport(handler)


def _resolving_to(*addresses: str) -> Callable[..., Awaitable[_Resolved]]:
    async def fake(host: object, port: int, **kwargs: object) -> _Resolved:
        del host, kwargs

        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (address, port),
            )
            for address in addresses
        ]

    return fake


async def _never_resolves(host: object, port: object, **kwargs: object) -> NoReturn:
    del host, port, kwargs

    raise AssertionError("a literal address must be checked without resolving it")


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "10.0.0.5", "169.254.169.254"],
)
async def test_a_private_literal_is_refused_without_resolving_it(
    host: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _never_resolves)
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen))

    with pytest.raises(PrivateNetworkError) as caught:
        _ = await guard.handle_async_request(
            httpx.Request("POST", f"https://{host}/hook", content=b"{}"),
        )

    assert str(caught.value) == (
        f'The host "{host}" resolves to "{host}", which is in a private network.'
    )
    assert seen == []


async def test_an_ipv6_loopback_literal_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _never_resolves)
    guard = NoPrivateNetworkTransport(_recording([]))

    with pytest.raises(PrivateNetworkError) as caught:
        _ = await guard.handle_async_request(
            httpx.Request("POST", "https://[::1]/hook", content=b"{}"),
        )

    assert str(caught.value) == 'The host "::1" resolves to "::1", which is in a private network.'


async def test_a_hostname_resolving_privately_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _resolving_to("192.168.1.1"))
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen))

    with pytest.raises(PrivateNetworkError) as caught:
        _ = await guard.handle_async_request(
            httpx.Request("POST", "https://internal.test/hook", content=b"{}"),
        )

    assert str(caught.value) == (
        'The host "internal.test" resolves to "192.168.1.1", which is in a private network.'
    )
    assert seen == []


async def test_a_mixed_resolution_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """One public address does not excuse a private one: whichever of the two
    the connection would actually pick, nothing is sent."""
    monkeypatch.setattr(anyio, "getaddrinfo", _resolving_to("93.184.216.34", "10.0.0.5"))
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen))

    with pytest.raises(PrivateNetworkError) as caught:
        _ = await guard.handle_async_request(
            httpx.Request("POST", "https://receiver.test/hook", content=b"{}"),
        )

    assert caught.value.address == "10.0.0.5"
    assert seen == []


async def test_a_public_hostname_is_pinned_to_its_first_resolved_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This proves routing only, not TLS: the url carries the pinned address
    while the ``Host`` header and ``sni_hostname`` keep the original name — but
    ``MockTransport`` performs no handshake, so what the certificate is checked
    against is httpcore's affair, not asserted here."""
    monkeypatch.setattr(anyio, "getaddrinfo", _resolving_to("93.184.216.34", "8.8.8.8"))
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen))

    response = await guard.handle_async_request(
        httpx.Request("POST", "https://receiver.test/hook", content=b"{}"),
    )

    assert response.status_code == 202
    assert seen[0].url.host == "93.184.216.34"
    assert seen[0].headers["Host"] == "receiver.test"
    assert seen[0].extensions["sni_hostname"] == "receiver.test"


async def test_a_public_ipv6_resolution_is_pinned_bracketed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _resolving_to("2001:4860:4860::8888"))
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen))

    _ = await guard.handle_async_request(
        httpx.Request("POST", "https://receiver.test/hook", content=b"{}"),
    )

    assert seen[0].url.host == "2001:4860:4860::8888"
    assert "[2001:4860:4860::8888]" in str(seen[0].url)


async def test_pinning_keeps_the_method_the_headers_and_the_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _resolving_to("93.184.216.34"))
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen))

    _ = await guard.handle_async_request(
        httpx.Request(
            "POST",
            "https://receiver.test/hook",
            headers={"Webhook-Id": "evt_1"},
            content=b'{"total":10}',
        ),
    )

    assert seen[0].method == "POST"
    assert seen[0].headers["Webhook-Id"] == "evt_1"
    assert seen[0].content == b'{"total":10}'


async def test_a_public_literal_is_delivered_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _never_resolves)
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen))
    request = httpx.Request("POST", "https://93.184.216.34/hook", content=b"{}")

    response = await guard.handle_async_request(request)

    assert response.status_code == 202
    assert seen[0] is request


async def test_the_allow_list_exempts_a_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _never_resolves)
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen), allow_list=["10.0.0.0/8"])

    response = await guard.handle_async_request(
        httpx.Request("POST", "https://10.0.0.5/hook", content=b"{}"),
    )

    assert response.status_code == 202
    assert len(seen) == 1


async def test_the_allow_list_exempts_a_resolved_address_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _resolving_to("10.0.0.5"))
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen), allow_list=["10.0.0.0/8"])

    _ = await guard.handle_async_request(
        httpx.Request("POST", "https://internal.test/hook", content=b"{}"),
    )

    assert seen[0].url.host == "10.0.0.5"


async def test_the_allow_list_exempts_only_what_it_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _never_resolves)
    guard = NoPrivateNetworkTransport(_recording([]), allow_list=["10.0.0.0/8"])

    with pytest.raises(PrivateNetworkError):
        _ = await guard.handle_async_request(
            httpx.Request("POST", "https://127.0.0.1/hook", content=b"{}"),
        )


async def test_a_custom_subnet_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _never_resolves)
    guard = NoPrivateNetworkTransport(_recording([]), subnets=["203.0.113.0/24"])

    with pytest.raises(PrivateNetworkError) as caught:
        _ = await guard.handle_async_request(
            httpx.Request("POST", "https://203.0.113.9/hook", content=b"{}"),
        )

    assert str(caught.value) == (
        'The host "203.0.113.9" resolves to "203.0.113.9", which is in a private network.'
    )


async def test_custom_subnets_replace_the_default_blocked_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(anyio, "getaddrinfo", _never_resolves)
    seen: list[httpx.Request] = []
    guard = NoPrivateNetworkTransport(_recording(seen), subnets=["203.0.113.0/24"])

    response = await guard.handle_async_request(
        httpx.Request("POST", "https://10.0.0.5/hook", content=b"{}"),
    )

    assert response.status_code == 202
    assert len(seen) == 1


async def test_aclose_closes_the_inner_transport() -> None:
    class ClosingTransport(httpx.AsyncBaseTransport):
        def __init__(self) -> None:
            self.closed: bool = False

        @override
        async def aclose(self) -> None:
            self.closed = True

    inner = ClosingTransport()
    guard = NoPrivateNetworkTransport(inner)

    await guard.aclose()

    assert inner.closed
