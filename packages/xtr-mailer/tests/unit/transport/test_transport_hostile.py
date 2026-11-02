"""What the builder does with a DSN written to break it: refuses it, fast, keeping secrets."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_http_client import MockHttpClient
from xtr_logging_contracts import AbstractLogger

from tests.support.dummy_transport_factory import DummyTransportFactory
from xtr_mailer import MailerError
from xtr_mailer.transport import Transport, TransportFactoryDiscovery

if TYPE_CHECKING:
    from collections.abc import Iterator

    from xtr_logging_contracts import Context, LevelLike

_MEGABYTE = 1024 * 1024
_SECRET = "s3cret-pass"
_USER = "s3cret-user"
#: Long enough to notice a parser going quadratic on a megabyte; far beyond a linear one.
_BUDGET_SECONDS = 2.0
#: Building a hundred thousand transports takes about a second; quadratic would take hours.
_BUILD_BUDGET_SECONDS = 10.0
#: The longest message a refusal may carry: it quotes a capped part of the DSN, never all of it.
_LONGEST_MESSAGE = 200


class _RecordingLogger(AbstractLogger):
    def __init__(self) -> None:
        self.records: list[str] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        self.records.append(f"{message} {context!r}")


def _builder() -> Transport:
    return Transport([DummyTransportFactory(http_client=MockHttpClient())])


def _chain(error: BaseException) -> Iterator[BaseException]:
    current: BaseException | None = error
    while current is not None:
        yield current
        current = current.__cause__ or current.__context__


def _refusal(dsn: str) -> MailerError:
    started = time.perf_counter()
    with pytest.raises(MailerError) as caught:
        _ = _builder().from_string(dsn)
    assert time.perf_counter() - started < _BUDGET_SECONDS
    return caught.value


@pytest.mark.parametrize(
    "dsn",
    [
        pytest.param(f"dummy://user:{_SECRET}@a\r\nb", id="crlf in the host"),
        pytest.param(f"failover(dummy://user:{_SECRET}\r\n@a dummy://b)", id="crlf in a member"),
        pytest.param(f"dummy://user:{_SECRET}@a\x00", id="nul in the host"),
        pytest.param(f"dummy://user:{_SECRET}\x00@a", id="nul in the password"),
        pytest.param(f"dummy://user:{_SECRET}@a?x=\x7f", id="del in an option"),
        pytest.param(f"dummy://user:{_SECRET}@a\tb", id="tab inside"),
    ],
)
def test_a_control_character_inside_a_dsn_is_refused(dsn: str) -> None:
    error = _refusal(dsn)

    assert str(error) == "The mailer DSN is invalid."


@pytest.mark.parametrize(
    "dsn",
    [
        pytest.param(f"null://user:{_SECRET}@a garbage", id="garbage"),
        pytest.param(f"failover(null://user:{_SECRET}@a", id="unclosed"),
        pytest.param(f"other://user:{_SECRET}@a", id="unsupported scheme"),
        pytest.param(f"mailgun+api://user:{_SECRET}@a", id="provider not installed"),
        pytest.param(f"foo(null://user:{_SECRET}@a)", id="unknown keyword"),
        pytest.param(f"null://user:{_SECRET}@a:99999", id="bad port"),
        pytest.param(f"null://user:{_SECRET}@a\r\nb", id="crlf"),
        pytest.param(f"failover(null://user:{_SECRET}@a)?retry_period=-1", id="negative retry"),
        pytest.param(
            f"roundrobin(failover(null://a)?retry_period=15smtp://{_USER}:{_SECRET}@smtp.example.com)",
            id="dsn glued onto a nested retry period",
        ),
        pytest.param(
            f"failover(null://a)?retry_period=15,smtp://{_USER}:{_SECRET}@smtp.example.com",
            id="dsn glued onto a retry period with a comma",
        ),
        pytest.param(
            f"failover(null://a)?retry_period=15 smtp://{_USER}:{_SECRET}@smtp.example.com",
            id="dsn after the retry period",
        ),
        pytest.param(
            f"failover(null://a)smtp://{_USER}:{_SECRET}@smtp.example.com",
            id="dsn glued after the group",
        ),
        pytest.param(
            f"failover(null://a) smtp://{_USER}:{_SECRET}@smtp.example.com",
            id="dsn after the group",
        ),
        pytest.param(
            f"failover(null://a)?{_USER}:{_SECRET}@smtp.example.com",
            id="credentials as the option of a group",
        ),
        pytest.param(
            f"failover(null://a)?retry_period={_USER}:{_SECRET}@smtp.example.com",
            id="credentials as the retry period",
        ),
        pytest.param(
            f"roundrobin(null://a foo(smtp://{_USER}:{_SECRET}@smtp.example.com))",
            id="credentials inside an unknown keyword",
        ),
    ],
)
def test_no_refusal_shows_the_credentials(dsn: str) -> None:
    logger = _RecordingLogger()

    with pytest.raises(MailerError) as caught:
        _ = Transport.from_dsn(dsn, logger=logger)

    for error in _chain(caught.value):
        for secret in (_USER, _SECRET):
            assert secret not in str(error)
            assert secret not in repr(error)
    assert all(_SECRET not in record and _USER not in record for record in logger.records)


@pytest.mark.parametrize("keyword", ["foo", "a:b", "user@host", "x://y"])
def test_an_unknown_keyword_is_shown_as_word_characters_only(keyword: str) -> None:
    with pytest.raises(MailerError) as caught:
        _ = _builder().from_string(f"{keyword}(dummy://a)")

    quoted = str(caught.value).partition('"')[2].partition('"')[0]
    assert ":" not in quoted
    assert "@" not in quoted


def test_a_megabyte_of_unclosed_groups_is_refused_fast() -> None:
    error = _refusal("failover(" * (_MEGABYTE // 9))

    assert str(error) == "The mailer DSN must contain a scheme."


def test_a_megabyte_of_balanced_nesting_is_refused_fast() -> None:
    depth = _MEGABYTE // 20
    error = _refusal("failover(" * depth + "dummy://a" + ")" * depth)

    assert str(error) == "The mailer DSN nests its transports more than 32 deep."


def test_a_megabyte_of_open_parentheses_is_refused_fast() -> None:
    error = _refusal("(" * _MEGABYTE)

    assert str(error) == "The mailer DSN must contain a scheme."


def test_a_megabyte_keyword_is_refused_with_a_short_message() -> None:
    error = _refusal("k" * _MEGABYTE + "(dummy://a)")

    assert str(error).startswith('The "kkk')
    assert len(str(error)) < _LONGEST_MESSAGE


def test_a_megabyte_scheme_is_refused_with_a_short_message() -> None:
    error = _refusal("s" * _MEGABYTE + "://a")

    assert str(error).startswith('The "sss')
    assert len(str(error)) < _LONGEST_MESSAGE


def test_a_megabyte_retry_period_is_refused_with_a_short_message() -> None:
    error = _refusal("failover(dummy://a)?retry_period=" + "x" * _MEGABYTE)

    assert len(str(error)) < _LONGEST_MESSAGE


def test_a_megabyte_of_garbage_is_refused_fast() -> None:
    error = _refusal("dummy://a " + "x " * (_MEGABYTE // 2))

    assert str(error) == "The mailer DSN has some garbage at the end."


def test_a_megabyte_of_spaces_between_members_is_read_fast() -> None:
    started = time.perf_counter()

    _ = _builder().from_string("failover(dummy://a" + " " * _MEGABYTE + "dummy://b)")

    assert time.perf_counter() - started < _BUDGET_SECONDS


@pytest.mark.parametrize("scheme", ["dummy", "null"], ids=["given factory", "discovered factory"])
def test_a_megabyte_of_members_is_read_fast(scheme: str) -> None:
    builder = Transport(
        [DummyTransportFactory(http_client=MockHttpClient())], TransportFactoryDiscovery()
    )
    started = time.perf_counter()

    built = builder.from_string("roundrobin(" + f"{scheme}://a " * (_MEGABYTE // 10) + ")")

    assert time.perf_counter() - started < _BUILD_BUDGET_SECONDS
    assert str(built).startswith("roundrobin(")
