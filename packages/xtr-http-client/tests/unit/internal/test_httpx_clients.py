from __future__ import annotations

import asyncio
import ssl
from typing import TYPE_CHECKING

import httpx
import pytest

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.httpx_clients import HttpxClients, _verification, _wants_http2

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("version", [None, "1.1"])
def test_the_default_version_is_http_1_1(version: str | None) -> None:
    assert _wants_http2(version) is False


@pytest.mark.parametrize("version", ["2", "2.0"])
def test_version_two_asks_for_http_2(version: str) -> None:
    assert _wants_http2(version) is True


@pytest.mark.parametrize("version", ["1.0", "3", "", "two"])
def test_a_version_that_cannot_be_sent_is_refused(version: str) -> None:
    with pytest.raises(InvalidArgumentError, match=f'Invalid HTTP version "{version}"'):
        _ = _wants_http2(version)


async def test_asking_for_http_2_without_the_extra_names_the_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(**_kwargs: object) -> httpx.AsyncClient:
        raise ImportError("no module named h2")

    monkeypatch.setattr(httpx, "AsyncClient", missing)

    with pytest.raises(InvalidArgumentError, match='needs the "http2" extra'):
        _ = HttpxClients(2).for_options({"http_version": "2"})


def test_checking_nothing_is_said_plainly() -> None:
    assert _verification({"verify_peer": False}) is False


def test_the_platform_trust_store_is_said_plainly() -> None:
    assert _verification({}) is True


def test_a_name_that_is_not_to_be_matched_needs_a_context() -> None:
    verification = _verification({"verify_host": False})

    assert isinstance(verification, ssl.SSLContext)
    assert verification.check_hostname is False
    assert verification.verify_mode is ssl.CERT_REQUIRED


def test_another_trust_store_needs_a_context(tmp_path: object) -> None:
    verification = _verification({"capath": str(tmp_path)})

    assert isinstance(verification, ssl.SSLContext)
    assert verification.check_hostname is True


def test_a_client_certificate_is_loaded_with_its_key_and_passphrase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[tuple[object, object, object]] = []

    def record(
        _self: ssl.SSLContext,
        certfile: object,
        keyfile: object = None,
        password: object = None,
    ) -> None:
        loaded.append((certfile, keyfile, password))

    monkeypatch.setattr(ssl.SSLContext, "load_cert_chain", record)

    verification = _verification(
        {"local_cert": "/cert.pem", "local_pk": "/key.pem", "passphrase": "secret"}
    )

    assert isinstance(verification, ssl.SSLContext)
    assert loaded == [("/cert.pem", "/key.pem", "secret")]


async def test_options_that_connect_the_same_way_share_a_pool() -> None:
    clients = HttpxClients(3)

    first = clients.for_options({"timeout": 5})
    second = clients.for_options({"timeout": 5, "user_data": object()})

    assert first is second

    await clients.aclose()


@pytest.mark.parametrize(
    "apart",
    [
        {"timeout": 1},
        {"proxy": "http://proxy.test:3128"},
        {"verify_peer": False},
        {"http_version": "2"},
        {"max_connect_duration": 0.5},
    ],
)
async def test_options_that_connect_differently_get_pools_of_their_own(
    apart: Mapping[str, object],
) -> None:
    clients = HttpxClients(3)

    plain = clients.for_options({})
    other = clients.for_options(apart)

    assert plain is not other

    await clients.aclose()


async def test_closing_lets_go_of_every_pool() -> None:
    clients = HttpxClients(3)
    client = clients.for_options({})

    await clients.aclose()

    assert client.is_closed
    assert clients.for_options({}) is not client

    await clients.aclose()


def test_a_second_event_loop_gets_its_own_client() -> None:
    # A pool's connections belong to the loop that opened them; handing one to
    # another loop fails the first request it sends.
    clients = HttpxClients(3)

    async def pool() -> httpx.AsyncClient:
        return clients.for_options({})

    first = asyncio.run(pool())
    second = asyncio.run(pool())

    assert first is not second


async def test_closing_lets_go_of_the_running_loops_pools_only() -> None:
    clients = HttpxClients(3)

    async def pool() -> httpx.AsyncClient:
        return clients.for_options({})

    def on_another_loop() -> httpx.AsyncClient:
        return asyncio.run(pool())

    elsewhere = await asyncio.to_thread(on_another_loop)
    here = clients.for_options({})

    await clients.aclose()

    assert here.is_closed
    assert not elsewhere.is_closed
