"""What the builder does with a DSN written to break it: refuses it, fast, keeping secrets.

Fast means in time growing with the DSN's length, never with its square: each hostile shape is
read at a quarter of a megabyte and at a megabyte (see :mod:`tests.support.growth`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_http_client import MockHttpClient
from xtr_logging_contracts import AbstractLogger

from tests.support.dummy_transport_factory import DummyTransportFactory
from tests.support.growth import assert_linear_growth
from xtr_mailer import MailerError
from xtr_mailer.transport import Transport, TransportFactoryDiscovery

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from xtr_logging_contracts import Context, LevelLike

_MEGABYTE = 1024 * 1024
_SECRET = "s3cret-pass"
_USER = "s3cret-user"
#: The longest message a refusal may carry: it quotes a capped part of the DSN, never all of it.
_LONGEST_MESSAGE = 200

_HOSTILE: dict[str, Callable[[int], str]] = {
    "unclosed groups": lambda size: "failover(" * (size // 9),
    "balanced nesting": lambda size: "failover(" * (size // 20) + "dummy://a" + ")" * (size // 20),
    "open parentheses": lambda size: "(" * size,
    "long keyword": lambda size: "k" * size + "(dummy://a)",
    "long scheme": lambda size: "s" * size + "://a",
    "long retry period": lambda size: "failover(dummy://a)?retry_period=" + "x" * size,
    "garbage": lambda size: "dummy://a " + "x " * (size // 2),
}


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
    with pytest.raises(MailerError) as caught:
        _ = _builder().from_string(dsn)
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
    error = _refusal(_HOSTILE["unclosed groups"](_MEGABYTE))

    assert str(error) == "The mailer DSN must contain a scheme."


def test_a_megabyte_of_balanced_nesting_is_refused_fast() -> None:
    error = _refusal(_HOSTILE["balanced nesting"](_MEGABYTE))

    assert str(error) == "The mailer DSN nests its transports more than 32 deep."


def test_a_megabyte_of_open_parentheses_is_refused_fast() -> None:
    error = _refusal(_HOSTILE["open parentheses"](_MEGABYTE))

    assert str(error) == "The mailer DSN must contain a scheme."


def test_a_megabyte_keyword_is_refused_with_a_short_message() -> None:
    error = _refusal(_HOSTILE["long keyword"](_MEGABYTE))

    assert str(error).startswith('The "kkk')
    assert len(str(error)) < _LONGEST_MESSAGE


def test_a_megabyte_scheme_is_refused_with_a_short_message() -> None:
    error = _refusal(_HOSTILE["long scheme"](_MEGABYTE))

    assert str(error).startswith('The "sss')
    assert len(str(error)) < _LONGEST_MESSAGE


def test_a_megabyte_retry_period_is_refused_with_a_short_message() -> None:
    error = _refusal(_HOSTILE["long retry period"](_MEGABYTE))

    assert len(str(error)) < _LONGEST_MESSAGE


def test_a_megabyte_of_garbage_is_refused_fast() -> None:
    error = _refusal(_HOSTILE["garbage"](_MEGABYTE))

    assert str(error) == "The mailer DSN has some garbage at the end."


@pytest.mark.parametrize("build", _HOSTILE.values(), ids=_HOSTILE.keys())
def test_a_hostile_dsn_is_refused_in_linear_time(build: Callable[[int], str]) -> None:
    assert_linear_growth(lambda size: _refusal(build(size)), _MEGABYTE // 4)


def test_spaces_between_members_are_read_in_linear_time() -> None:
    builder = _builder()

    assert_linear_growth(
        lambda size: builder.from_string("failover(dummy://a" + " " * size + "dummy://b)"),
        _MEGABYTE // 4,
    )


@pytest.mark.parametrize("scheme", ["dummy", "null"], ids=["given factory", "discovered factory"])
def test_members_are_read_in_linear_time(scheme: str) -> None:
    builder = Transport(
        [DummyTransportFactory(http_client=MockHttpClient())], TransportFactoryDiscovery()
    )

    assert_linear_growth(
        lambda size: builder.from_string("roundrobin(" + f"{scheme}://a " * size + ")"), 2_500
    )


def test_a_hundred_thousand_members_are_read() -> None:
    built = _builder().from_string("roundrobin(" + "dummy://a " * 100_000 + ")")

    assert str(built).startswith("roundrobin(")
