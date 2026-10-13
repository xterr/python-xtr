from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_message import Request
from xtr_logging_contracts import AbstractLogger

from tests.support.fake_client import FakeClient
from xtr_http_client import (
    GenericRetryStrategy,
    MockHttpClient,
    MockResponse,
    RetryableHttpClient,
)
from xtr_http_client.exception import InvalidArgumentError, ServerError, TransportError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_logging_contracts import Context, LevelLike

    from xtr_http_client.retry import RetryContext

pytestmark = pytest.mark.anyio

_URL = "http://example.com/foo-bar"


@final
class _Logs(AbstractLogger):
    """A logger that keeps what it was told, message and context apart."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, object]]] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        del level
        self.records.append((message, dict(context or {})))


@final
class _Waits:
    """A stand-in for waiting, which keeps the waits and takes no time."""

    def __init__(self) -> None:
        self.seconds: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.seconds.append(delay)


@final
class _NeedsBody:
    """Retries anything but a 200, asking for the body of a 500 first."""

    async def should_retry(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> bool | None:
        del error
        if context.get_status_code() == 500 and content is None:
            return None

        return context.get_status_code() != 200

    def get_delay(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> int:
        del context, content, error

        return 0


@final
class _ReadsBody:
    """Retries only a body it has not seen before."""

    async def should_retry(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> bool | None:
        del context, error
        if content is None:
            return None

        return content != b"my bad"

    def get_delay(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> int:
        del context, content, error

        return 0


@final
class _Undecided:
    """A strategy that will not say, whatever it is asked with."""

    async def should_retry(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> bool | None:
        del context, content, error

        return None

    def get_delay(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> int:
        del context, content, error

        return 0


@final
class _Refusing:
    """A strategy that never retries, and remembers what it was asked about."""

    def __init__(self) -> None:
        self.asked: list[TransportError | None] = []

    async def should_retry(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> bool | None:
        del context, content
        self.asked.append(error)

        return False

    def get_delay(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> int:
        del context, content, error

        return 0


def _scripted(*responses: MockResponse) -> MockHttpClient:
    """A client answering from ``responses``, resolving nothing of its own."""
    return MockHttpClient(list(responses), None)


def _answer(status_code: int, body: bytes = b"") -> MockResponse:
    return MockResponse(body, {"http_code": status_code})


async def _produced() -> AsyncGenerator[bytes, None]:
    yield b"piece"


async def _instantly(delay: float) -> None:
    del delay


async def test_a_retried_request_is_answered_by_the_next_response() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(200)),
        GenericRetryStrategy([500], 0),
        1,
        sleep=_instantly,
    )

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 200


async def test_the_last_answer_is_the_answer_once_no_retry_is_left() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(500), _answer(200)),
        GenericRetryStrategy([500], 0),
        1,
        sleep=_instantly,
    )

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 500
        with pytest.raises(ServerError):
            _ = await response.get_content()


async def test_a_strategy_asking_for_the_body_is_asked_again_with_it() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500, b"abc"), _answer(200, b"def")),
        _NeedsBody(),
        2,
        sleep=_instantly,
    )

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 200
        assert await response.get_content() == b"def"


async def test_a_body_read_to_decide_is_still_there_to_be_read() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(400, b"my bad")),
        _ReadsBody(),
        1,
        sleep=_instantly,
    )

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 400
        assert await response.get_content(throw=False) == b"my bad"


async def test_a_strategy_that_will_not_decide_with_the_body_is_reported() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(200)),
        _Undecided(),
        1,
        sleep=_instantly,
    )

    with pytest.raises(InvalidArgumentError) as refused:
        _ = await client.request("GET", _URL)

    assert str(refused.value) == (
        'The "_Undecided.should_retry()" method must not return None when called with a body.'
    )


async def test_a_client_allowed_no_retries_hands_back_the_first_answer() -> None:
    inner = _scripted(_answer(500))
    client = RetryableHttpClient(inner, GenericRetryStrategy([500], 0), 0)

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 500

    assert inner.get_requests_count() == 1


async def test_the_answer_s_content_can_be_read_more_than_once() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(200, b"Test out content")),
        GenericRetryStrategy([500], 0),
        1,
        sleep=_instantly,
    )

    async with await client.request("GET", _URL) as response:
        assert await response.get_content() == b"Test out content"
        assert await response.get_content() == b"Test out content"


async def test_a_retry_after_header_is_obeyed_over_the_strategy_s_delay() -> None:
    logs = _Logs()
    waits = _Waits()
    asking_later = MockResponse(
        b"",
        {"http_code": 503, "response_headers": {"retry-after": "0.46"}},
    )
    client = RetryableHttpClient(_scripted(asking_later, _answer(200)), None, 1, logs, waits)

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 200

    assert logs.records == [
        ("Try #{count} after {delay}ms, status code: 503", {"count": 1, "delay": 460})
    ]
    assert waits.seconds == [0.46]


async def test_the_strategy_s_delay_is_waited_when_the_server_names_none() -> None:
    waits = _Waits()
    client = RetryableHttpClient(
        _scripted(_answer(503), _answer(200)),
        GenericRetryStrategy([503], 250, 1, 0, 0),
        1,
        sleep=waits,
    )

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 200

    assert waits.seconds == [0.25]


async def test_a_request_that_brought_back_nothing_is_made_again() -> None:
    logs = _Logs()
    client = RetryableHttpClient(
        _scripted(MockResponse(b"", {"error": "Connection refused."}), _answer(200, b"ok")),
        GenericRetryStrategy(),
        1,
        logs,
        _instantly,
    )

    async with await client.request("GET", _URL) as response:
        assert await response.get_content() == b"ok"

    assert logs.records[0][0] == "Try #{count} after {delay}ms: Connection refused."


async def test_an_attempt_that_brought_back_nothing_is_put_to_the_strategy() -> None:
    strategy = _Refusing()
    client = RetryableHttpClient(
        _scripted(MockResponse(b"", {"error": "Connection refused."})),
        strategy,
        2,
        sleep=_instantly,
    )

    with pytest.raises(TransportError, match=r"Connection refused\."):
        _ = await client.request("GET", _URL)

    assert len(strategy.asked) == 1
    assert isinstance(strategy.asked[0], TransportError)


async def test_a_strategy_that_will_not_decide_on_an_error_is_reported() -> None:
    client = RetryableHttpClient(
        _scripted(MockResponse(b"", {"error": "Connection refused."})),
        _Undecided(),
        1,
        sleep=_instantly,
    )

    with pytest.raises(InvalidArgumentError) as refused:
        _ = await client.request("GET", _URL)

    assert str(refused.value) == (
        'The "_Undecided.should_retry()" method must not return None when called with an error.'
    )


async def test_the_last_error_is_raised_once_no_retry_is_left() -> None:
    inner = _scripted(
        MockResponse(b"", {"error": "Connection refused."}),
        MockResponse(b"", {"error": "Connection reset."}),
    )
    client = RetryableHttpClient(inner, GenericRetryStrategy(), 1, sleep=_instantly)

    with pytest.raises(TransportError, match=r"Connection reset\."):
        _ = await client.request("GET", _URL)

    assert inner.get_requests_count() == 2


async def test_each_attempt_moves_one_base_uri_along() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(200, b"Hit on second uri")),
        GenericRetryStrategy([500], 0),
        1,
        sleep=_instantly,
    )

    async with await client.request(
        "GET",
        "foo-bar",
        base_uri=["http://example.com/a/", "http://example.com/b/"],
    ) as response:
        assert response.get_status_code() == 200
        assert response.get_info("url") == "http://example.com/b/foo-bar"


async def test_base_uris_given_to_the_client_are_moved_along_too() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(200, b"Hit on second uri")),
        GenericRetryStrategy([500], 0),
        1,
        sleep=_instantly,
    ).with_options(base_uri=["http://example.com/a/", "http://example.com/b/"])

    async with await client.request("GET", "foo-bar") as response:
        assert response.get_status_code() == 200
        assert response.get_info("url") == "http://example.com/b/foo-bar"


async def test_an_attempt_past_the_last_base_uri_stays_on_it() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(500), _answer(500), _answer(200)),
        GenericRetryStrategy([500], 0),
        3,
        sleep=_instantly,
    )

    async with await client.request(
        "GET",
        "foo-bar",
        base_uri=["http://example.com/a/", "http://example.com/b/"],
    ) as response:
        assert response.get_info("url") == "http://example.com/b/foo-bar"


async def test_one_base_uri_is_passed_on_to_the_wrapped_client() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(200)),
        GenericRetryStrategy([500], 0),
        1,
        sleep=_instantly,
    ).with_options(base_uri="http://example.com/a/")

    async with await client.request("GET", "foo-bar") as response:
        assert response.get_info("url") == "http://example.com/a/foo-bar"


async def test_the_option_lowers_how_many_retries_one_request_may_have() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(502), _answer(200)),
        GenericRetryStrategy([500, 502], 0),
        3,
        sleep=_instantly,
    )

    async with await client.request("GET", _URL, max_retries=1) as response:
        assert response.get_status_code() == 502


async def test_the_option_given_to_the_client_lowers_it_for_every_request() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(502), _answer(504), _answer(200)),
        GenericRetryStrategy([500, 502, 504], 0),
        3,
        sleep=_instantly,
    ).with_options(max_retries=2)

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 504


async def test_the_answer_says_how_many_tries_it_took() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(500), _answer(200)),
        GenericRetryStrategy([500], 0),
        2,
        sleep=_instantly,
    )

    async with await client.request("GET", _URL) as response:
        assert response.get_info("retry_count") == 2
        whole = response.get_info()
        assert isinstance(whole, Mapping)
        assert whole["retry_count"] == 2


async def test_an_answer_that_took_one_try_says_nothing_about_retries() -> None:
    client = RetryableHttpClient(_scripted(_answer(200)), GenericRetryStrategy([500], 0), 2)

    async with await client.request("GET", _URL) as response:
        assert response.get_info("retry_count") is None


async def test_a_body_produced_as_it_goes_is_sent_once() -> None:
    inner = _scripted(_answer(500), _answer(200))
    client = RetryableHttpClient(inner, GenericRetryStrategy([500], 0), 1, sleep=_instantly)
    producing = _produced()

    try:
        async with await client.request("POST", _URL, body=producing) as response:
            assert response.get_status_code() == 500
    finally:
        await producing.aclose()

    assert inner.get_requests_count() == 1


async def test_a_message_request_is_sent_again_with_its_body_rewound() -> None:
    inner = _scripted(_answer(500), _answer(200))
    client = RetryableHttpClient(inner, GenericRetryStrategy([500], 0), 1, sleep=_instantly)
    request = Request("PUT", _URL, body=b"payload")

    async with await client.send_request(request) as response:
        assert response.get_status_code() == 200
        assert await request.get_body().get_contents() == b"payload"

    assert inner.get_requests_count() == 2


async def test_a_message_request_with_no_body_is_sent_again() -> None:
    inner = _scripted(_answer(500), _answer(200))
    client = RetryableHttpClient(inner, GenericRetryStrategy([500], 0), 1, sleep=_instantly)

    async with await client.send_request(Request("GET", _URL)) as response:
        assert response.get_status_code() == 200

    assert inner.get_requests_count() == 2


async def test_the_default_strategy_retries_what_is_worth_retrying() -> None:
    client = RetryableHttpClient(_scripted(_answer(503), _answer(200)), sleep=_instantly)

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 200


async def test_narrowing_the_client_leaves_the_one_it_was_narrowed_from_alone() -> None:
    client = RetryableHttpClient(
        _scripted(_answer(500), _answer(200)),
        GenericRetryStrategy([500], 0),
        1,
        sleep=_instantly,
    )

    narrowed = client.with_options(user_data="narrowed")

    assert narrowed is not client
    async with await narrowed.request("GET", _URL) as response:
        assert response.get_status_code() == 200
        assert response.get_info("user_data") == "narrowed"


async def test_resetting_reaches_a_wrapped_client_that_can_be_reset() -> None:
    inner = _scripted(_answer(200))
    client = RetryableHttpClient(inner, sleep=_instantly)

    async with await client.request("GET", _URL):
        pass
    client.reset()

    assert inner.get_requests_count() == 0


async def test_resetting_leaves_a_wrapped_client_that_cannot_be_reset_able_to_answer() -> None:
    client = RetryableHttpClient(FakeClient([_answer(200), _answer(201)]), sleep=_instantly)

    async with await client.request("GET", _URL):
        pass
    client.reset()

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 201
