"""The discovery provider fetches, caches and refetches an issuer's JWKS."""

from __future__ import annotations

from typing import final

import anyio
import pytest
from xtr_security_core.exception import InvalidArgumentError

from tests.support.oidc import IssuerServer, make_key, make_key_set
from xtr_security_http.access_token.oidc.exception.oidc_key_set_error import OidcKeySetError
from xtr_security_http.oidc.oidc_discovery import DiscoveryOidcKeySetProvider


@final
class _Clock:
    """A hand-wound monotonic clock the cache times against."""

    now: float

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.anyio
async def test_it_discovers_the_jwks_uri_from_the_base_uri() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    provider = DiscoveryOidcKeySetProvider(
        base_uri=server.base_uri,
        http_client_factory=server.client_factory(),
    )

    key_set = await provider.get_key_set()

    assert [held.kid for held in key_set.keys] == [key.kid]
    assert server.discovery_requests == 1
    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_it_fetches_a_given_jwks_uri_without_discovery() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
    )

    _ = await provider.get_key_set()

    assert server.discovery_requests == 0
    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_a_cached_set_is_answered_within_the_ttl() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    clock = _Clock()
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
        ttl=600,
        monotonic=clock,
    )

    _ = await provider.get_key_set()
    clock.now = 599
    _ = await provider.get_key_set()

    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_the_set_is_refetched_once_the_ttl_lapses() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    clock = _Clock()
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
        ttl=600,
        monotonic=clock,
    )

    _ = await provider.get_key_set()
    clock.now = 601
    _ = await provider.get_key_set()

    assert server.jwks_requests == 2


@pytest.mark.anyio
async def test_a_forced_refresh_within_the_cooldown_is_not_refetched() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    clock = _Clock()
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
        refresh_cooldown=60,
        monotonic=clock,
    )

    _ = await provider.get_key_set()
    clock.now = 30
    _ = await provider.get_key_set(force_refresh=True)

    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_a_forced_refresh_past_the_cooldown_refetches() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    clock = _Clock()
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
        refresh_cooldown=60,
        monotonic=clock,
    )

    _ = await provider.get_key_set()
    clock.now = 61
    _ = await provider.get_key_set(force_refresh=True)

    assert server.jwks_requests == 2


@pytest.mark.anyio
async def test_a_burst_of_forced_refreshes_during_an_outage_makes_one_fetch() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    clock = _Clock()
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
        refresh_cooldown=60,
        monotonic=clock,
    )

    _ = await provider.get_key_set()
    server.down = True
    clock.now = 1000
    key_set = await provider.get_key_set(force_refresh=True)
    for _ in range(4):
        _ = await provider.get_key_set(force_refresh=True)

    assert server.jwks_requests == 2
    assert [held.kid for held in key_set.keys] == [key.kid]


@pytest.mark.anyio
async def test_a_burst_during_a_cold_start_outage_makes_one_fetch() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    server.down = True
    clock = _Clock()
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
        refresh_cooldown=60,
        monotonic=clock,
    )

    for offset in (0, 10, 20, 30, 40):
        clock.now = offset
        with pytest.raises(OidcKeySetError):
            _ = await provider.get_key_set()

    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_a_cold_start_outage_refetches_once_the_cooldown_lapses() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    server.down = True
    clock = _Clock()
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
        refresh_cooldown=60,
        monotonic=clock,
    )

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()
    clock.now = 61
    server.down = False
    key_set = await provider.get_key_set()

    assert server.jwks_requests == 2
    assert [held.kid for held in key_set.keys] == [key.kid]


@pytest.mark.anyio
async def test_concurrent_stale_reads_share_one_fetch() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
    )

    async with anyio.create_task_group() as group:
        for _ in range(5):
            group.start_soon(provider.get_key_set)  # pyright: ignore[reportUnusedCallResult]

    assert server.jwks_requests == 1


def test_an_insecure_base_uri_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = DiscoveryOidcKeySetProvider(
            base_uri="http://issuer.example",
            http_client_factory=IssuerServer(make_key_set(make_key())).client_factory(),
        )


def test_an_insecure_jwks_uri_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = DiscoveryOidcKeySetProvider(
            jwks_uri="http://issuer.example/jwks.json",
            http_client_factory=IssuerServer(make_key_set(make_key())).client_factory(),
        )


def test_an_insecure_uri_is_allowed_for_a_dev_issuer() -> None:
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri="http://issuer.example/jwks.json",
        http_client_factory=IssuerServer(make_key_set(make_key())).client_factory(),
        allow_insecure_http=True,
    )

    assert isinstance(provider, DiscoveryOidcKeySetProvider)


def test_giving_neither_endpoint_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = DiscoveryOidcKeySetProvider(
            http_client_factory=IssuerServer(make_key_set(make_key())).client_factory(),
        )


def test_giving_both_endpoints_is_refused() -> None:
    server = IssuerServer(make_key_set(make_key()))
    with pytest.raises(InvalidArgumentError):
        _ = DiscoveryOidcKeySetProvider(
            base_uri=server.base_uri,
            jwks_uri=server.jwks_uri,
            http_client_factory=server.client_factory(),
        )


@pytest.mark.anyio
async def test_a_discovery_document_without_a_jwks_uri_is_refused() -> None:
    server = IssuerServer(make_key_set(make_key()), omit_jwks_uri=True)
    provider = DiscoveryOidcKeySetProvider(
        base_uri=server.base_uri,
        http_client_factory=server.client_factory(),
    )

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_a_fetch_failure_becomes_a_key_set_error() -> None:
    key = make_key()
    server = IssuerServer(make_key_set(key))
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=f"{server.base_uri}/missing.json",
        http_client_factory=server.client_factory(),
    )

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_a_malformed_jwks_document_becomes_a_key_set_error() -> None:
    server = IssuerServer(make_key_set(make_key()), jwks_body={"keys": [{"kty": "nonsense"}]})
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
    )

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_a_jwks_answer_that_is_not_an_object_becomes_a_key_set_error() -> None:
    server = IssuerServer(make_key_set(make_key()), jwks_body=[])
    provider = DiscoveryOidcKeySetProvider(
        jwks_uri=server.jwks_uri,
        http_client_factory=server.client_factory(),
    )

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()
