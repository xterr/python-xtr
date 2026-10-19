"""The default login rate limiter: its keys, its secret, its forgetting.

The keys are the security-critical part: both are HMAC-SHA256 digests of
what they count, prefixed with the application's secret and cut to eight
base64 characters, so the store a count lives in keeps no readable
account or address. The expected keys below are known-answer vectors,
computed once from the upstream derivation and pinned here so a change
to any part of it — the digest, the encoding, the prefix length, the
alphabet — fails a test.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

import pytest
from xtr_rate_limiter import (
    InMemoryStorage,
    LimiterConfig,
    RateLimit,
    RateLimiterFactory,
    ReserveNotSupportedError,
)
from xtr_security_core.exception import InvalidArgumentError

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.rate_limiter import DefaultLoginRateLimiter
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_rate_limiter import LimiterInterface, Reservation

pytestmark = pytest.mark.anyio

_HMAC_KEY = "secret_key"
"""The secret the pinned keys below were derived with."""

#: HMAC-SHA256 over ``"127.0.0.1"``, base64, eight characters, ``/`` and
#: ``+`` replaced: the key one address counts under.
_GLOBAL_KEY = "qXXdWmUe"

#: HMAC-SHA256 over ``"alice-127.0.0.1"``: the key one account from one
#: address counts under, the username lower-cased.
_LOCAL_KEY = ".HUgD9N2"

#: HMAC-SHA256 over ``"-127.0.0.1"``: the local key of an attempt that
#: named no account.
_UNNAMED_LOCAL_KEY = "fqyACTXl"

#: HMAC-SHA256 over the empty string: the global key of a request the
#: server reported no address for.
_UNADDRESSED_GLOBAL_KEY = "8wTBEnTK"

#: HMAC-SHA256 over ``"127.0.0.1"`` under another secret: the keys are
#: per-application.
_OTHER_HMAC_KEY = "_UhhmW23"


@final
class _RecordingLimiter:
    """Counts nothing; records every reset it is asked for."""

    def __init__(self) -> None:
        self.resets = 0

    async def consume(self, tokens: int = 1) -> RateLimit:
        del tokens
        return RateLimit(sys.maxsize, datetime.now(UTC), accepted=True, limit=sys.maxsize)

    async def reserve(self, tokens: int = 1, max_time: float | None = None) -> Reservation:
        """Refuse: this counter only records, it never books."""
        del tokens, max_time
        raise ReserveNotSupportedError("The recording limiter cannot reserve.")

    async def reset(self) -> None:
        self.resets += 1


@final
class _RecordingFactory:
    """Hands out one recording limiter per key, keeping every key it was asked for."""

    def __init__(self) -> None:
        self.keys: list[str | None] = []
        self.limiters: list[_RecordingLimiter] = []

    def create(self, key: str | None = None) -> LimiterInterface:
        self.keys.append(key)
        limiter = _RecordingLimiter()
        self.limiters.append(limiter)
        return limiter


def _request(
    username: str | None = "alice",
    client: tuple[str, int] | None = ("127.0.0.1", 80),
) -> ServerRequestInterface:
    """Return a request naming ``username`` from ``client``, as the flow parks them."""
    message = make_message(client=client)
    bag: dict[str, object] = {}
    if username is not None:
        security_state_of(bag).attributes[SecurityRequestAttributes.LAST_USERNAME] = username
    return message.with_attribute(SecurityRequestAttributes.STATE_BAG, bag)


async def test_it_refuses_an_empty_secret() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = DefaultLoginRateLimiter(_RecordingFactory(), _RecordingFactory(), "")

    assert str(raised.value) == "A non-empty secret is required."


async def test_it_keys_the_global_limit_by_the_address_and_the_local_by_the_account() -> None:
    global_factory = _RecordingFactory()
    local_factory = _RecordingFactory()
    limiter = DefaultLoginRateLimiter(global_factory, local_factory, _HMAC_KEY)

    limiters = limiter.get_limiters(_request())

    assert global_factory.keys == [_GLOBAL_KEY]
    assert local_factory.keys == [_LOCAL_KEY]
    assert list(limiters) == [global_factory.limiters[0], local_factory.limiters[0]]


async def test_it_lower_cases_the_account_before_keying_it() -> None:
    local_factory = _RecordingFactory()
    limiter = DefaultLoginRateLimiter(_RecordingFactory(), local_factory, _HMAC_KEY)

    _ = limiter.get_limiters(_request(username="Alice"))

    assert local_factory.keys == [_LOCAL_KEY]


async def test_it_counts_an_attempt_that_named_no_account_under_the_empty_one() -> None:
    local_factory = _RecordingFactory()
    limiter = DefaultLoginRateLimiter(_RecordingFactory(), local_factory, _HMAC_KEY)

    _ = limiter.get_limiters(_request(username=None))

    assert local_factory.keys == [_UNNAMED_LOCAL_KEY]


async def test_it_counts_a_request_the_server_reported_no_address_for_under_no_address() -> None:
    global_factory = _RecordingFactory()
    limiter = DefaultLoginRateLimiter(global_factory, _RecordingFactory(), _HMAC_KEY)

    _ = limiter.get_limiters(_request(client=None))

    assert global_factory.keys == [_UNADDRESSED_GLOBAL_KEY]


async def test_it_derives_its_keys_per_secret() -> None:
    global_factory = _RecordingFactory()
    limiter = DefaultLoginRateLimiter(global_factory, _RecordingFactory(), "another-secret")

    _ = limiter.get_limiters(_request())

    assert global_factory.keys == [_OTHER_HMAC_KEY]


async def test_it_forgets_the_local_count_only() -> None:
    global_factory = _RecordingFactory()
    local_factory = _RecordingFactory()
    limiter = DefaultLoginRateLimiter(global_factory, local_factory, _HMAC_KEY)

    _ = limiter.get_limiters(_request())
    await limiter.reset(_request())

    assert [limiter.resets for limiter in global_factory.limiters] == [0]
    # The local limiter the reset built is the second one the factory
    # handed out: the first was only asked for by the limiters read.
    assert [limiter.resets for limiter in local_factory.limiters] == [0, 1]


async def test_it_spends_only_on_a_count_and_keeps_the_address_count_across_a_reset() -> None:
    global_factory = RateLimiterFactory(
        "global", LimiterConfig("fixed_window", limit=1, interval="1 hour"), InMemoryStorage()
    )
    local_factory = RateLimiterFactory(
        "local", LimiterConfig("fixed_window", limit=5, interval="1 hour"), InMemoryStorage()
    )
    limiter = DefaultLoginRateLimiter(global_factory, local_factory, _HMAC_KEY)
    request = _request()

    first = await limiter.consume(request)
    assert first.is_accepted()

    # A look ahead spends nothing: the limit reads the same twice.
    peeked = await limiter.peek(request)
    assert peeked.is_accepted()
    assert peeked.remaining_tokens == first.remaining_tokens

    # The account's count is forgotten; the address's survives, so the
    # next attempt from the same address is still over the address's limit.
    await limiter.reset(request)
    second = await limiter.consume(request)
    assert not second.is_accepted()
