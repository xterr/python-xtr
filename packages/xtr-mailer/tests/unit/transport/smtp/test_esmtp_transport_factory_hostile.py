"""EsmtpTransportFactory refusing what a DSN must not configure, and never quoting credentials."""

from __future__ import annotations

import pytest
from xtr_http_client import MockHttpClient

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.transport import Dsn, Transport
from xtr_mailer.transport.smtp import EsmtpTransportFactory

_SECONDS = "a number of seconds, zero or more"


def _refusal(option: str, requirement: str, given: str | None) -> str:
    shown = "" if given is None else f', "{given}" given'
    return f'The "{option}" option is not valid: it must be {requirement}{shown}.'


def _create(dsn: str) -> InvalidArgumentError:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = EsmtpTransportFactory().create(Dsn.from_string(dsn))
    return caught.value


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("timeout=nan", _refusal("timeout", "a positive number of seconds", "nan")),
        ("timeout=inf", _refusal("timeout", "a positive number of seconds", "inf")),
        ("timeout=-inf", _refusal("timeout", "a positive number of seconds", "-inf")),
        ("timeout=1e999", _refusal("timeout", "a positive number of seconds", "1e999")),
        ("timeout=", _refusal("timeout", "a positive number of seconds", "")),
        ("timeout[]=1", _refusal("timeout", "a positive number of seconds", None)),
        (
            "max_per_second=-1",
            _refusal("max_per_second", "a number of emails a second, zero or more", "-1"),
        ),
        (
            "max_per_second=inf",
            _refusal("max_per_second", "a number of emails a second, zero or more", "inf"),
        ),
        (
            "restart_threshold=1.5",
            _refusal("restart_threshold", "a whole number of emails, zero or more", "1.5"),
        ),
        (
            "restart_threshold=-1",
            _refusal("restart_threshold", "a whole number of emails, zero or more", "-1"),
        ),
        (
            f"restart_threshold={'9' * 30}",
            _refusal("restart_threshold", "a whole number of emails, zero or more", "9" * 30),
        ),
        (
            "restart_threshold=1&restart_threshold_sleep=nan",
            _refusal("restart_threshold_sleep", _SECONDS, "nan"),
        ),
        (
            "restart_threshold=1&restart_threshold_sleep=-1",
            _refusal("restart_threshold_sleep", _SECONDS, "-1"),
        ),
        ("ping_threshold=abc", _refusal("ping_threshold", _SECONDS, "abc")),
        ("ping_threshold=-0.5", _refusal("ping_threshold", _SECONDS, "-0.5")),
        (
            "source_ip=example.com",
            _refusal("source_ip", "an IPv4 or IPv6 address", "example.com"),
        ),
        ("source_ip=1.2.3", _refusal("source_ip", "an IPv4 or IPv6 address", "1.2.3")),
        ("source_ip=[1.2.3.4]", _refusal("source_ip", "an IPv4 or IPv6 address", None)),
        ("source_ip=[::1", _refusal("source_ip", "an IPv4 or IPv6 address", None)),
        (
            "peer_fingerprint=abc",
            _refusal("peer_fingerprint", "an MD5, SHA-1 or SHA-256 digest in hex", "abc"),
        ),
        (
            "peer_fingerprint=",
            _refusal("peer_fingerprint", "an MD5, SHA-1 or SHA-256 digest in hex", ""),
        ),
        (
            "local_domain[]=example.com",
            _refusal("local_domain", "a domain name or an address", None),
        ),
        (
            "local_domain=client%20example.com",
            _refusal("local_domain", "a domain name or an address", None),
        ),
        ("auto_tls=maybe", 'Value "maybe" of the "auto_tls" DSN option is not a boolean.'),
        ("verify_peer=maybe", 'Value "maybe" of the "verify_peer" DSN option is not a boolean.'),
        ("require_tls=maybe", 'Value "maybe" of the "require_tls" DSN option is not a boolean.'),
    ],
)
def test_an_option_holding_no_valid_value_is_refused_by_name(query: str, message: str) -> None:
    assert str(_create(f"smtp://example.com?{query}")) == message


def test_a_restart_sleep_is_read_only_with_a_restart_threshold() -> None:
    transport = EsmtpTransportFactory().create(
        Dsn.from_string("smtp://localhost?restart_threshold_sleep=-1")
    )

    assert transport._restart_threshold_sleep == 0


def test_an_unset_source_ip_or_an_empty_one_leaves_the_system_choice() -> None:
    for dsn in ("smtp://localhost", "smtp://localhost?source_ip="):
        transport = EsmtpTransportFactory().create(Dsn.from_string(dsn))

        assert transport.get_source_ip() is None


@pytest.mark.parametrize(
    "host",
    ["exa\x00mple.com", "exa\x1bmple.com", "exa\x85mple.com", "exa\u2028mple.com", "a\u202eb"],
)
def test_a_host_with_a_control_character_is_refused(host: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = EsmtpTransportFactory().create(Dsn("smtp", host))

    assert str(caught.value) == "The SMTP host name must not contain control characters."


@pytest.mark.parametrize(
    "dsn",
    [
        "smtp://smtp..example.com:2525?auto_tls=0",
        "smtps://smtp..example.com",
        f"smtp://{'a' * 64}.example.com",
        "smtp://smtp.\ufffd.example.com",
        "smtp://smtp.\u3002example.com",
        "smtp://exa\udcffmple.com",
    ],
)
def test_a_host_the_resolver_cannot_encode_is_refused_when_the_transport_is_built(
    dsn: str,
) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Transport.from_dsn(dsn)

    assert str(caught.value) == "The SMTP host name is not a name the resolver can look up."
    assert caught.value.__context__ is None


def test_a_failover_naming_a_host_the_resolver_cannot_encode_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Transport.from_dsn("failover(smtp://smtp..example.com:2525 smtp://127.0.0.1:2525)")


@pytest.mark.parametrize("port", [-1, 65536])
def test_a_port_out_of_range_is_refused(port: int) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = EsmtpTransportFactory().create(Dsn("smtp", "example.com", port=port))

    assert str(caught.value) == f'The SMTP port must be between 1 and 65535, "{port}" given.'


_GLUED = "smtp://us3r-name:s3cr3t-pass@mail.example.com"


def _chain(error: BaseException) -> list[BaseException]:
    seen: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in seen:
        seen.append(current)
        current = current.__cause__ or current.__context__
    return seen


def _assert_no_credentials(error: BaseException) -> None:
    for link in _chain(error):
        for text in (str(link), repr(link), repr(link.args)):
            assert "s3cr3t" not in text
            assert "us3r" not in text


@pytest.mark.parametrize(
    "option",
    [
        "timeout",
        "max_per_second",
        "restart_threshold",
        "ping_threshold",
        "source_ip",
        "peer_fingerprint",
        "local_domain",
        "auto_tls",
        "verify_peer",
        "require_tls",
    ],
)
def test_a_dsn_glued_onto_an_option_never_reaches_the_error(option: str) -> None:
    error = _create(f"smtp://example.com?{option}=x {_GLUED}")

    assert option in str(error)
    _assert_no_credentials(error)


def test_a_dsn_glued_onto_the_restart_sleep_never_reaches_the_error() -> None:
    _assert_no_credentials(
        _create(f"smtp://example.com?restart_threshold=1&restart_threshold_sleep=x {_GLUED}")
    )


@pytest.mark.parametrize(
    "query",
    ["timeout=abc", "source_ip=nowhere", "peer_fingerprint=zz", "verify_peer=maybe"],
)
def test_the_dsn_credentials_never_reach_an_option_error(query: str) -> None:
    _assert_no_credentials(_create(f"smtp://us3r-name:s3cr3t-pass@example.com?{query}"))


def test_a_glued_dsn_built_through_the_builder_never_reaches_the_error() -> None:
    builder = Transport([EsmtpTransportFactory(http_client=MockHttpClient())])

    with pytest.raises(InvalidArgumentError) as caught:
        _ = builder.from_string(f"failover(smtp://a?timeout=x {_GLUED})")

    _assert_no_credentials(caught.value)


def test_the_transport_built_never_shows_the_credentials() -> None:
    transport = EsmtpTransportFactory().create(Dsn.from_string(_GLUED))

    assert "s3cr3t" not in f"{transport} {transport!r}"
    assert "us3r" not in f"{transport} {transport!r}"
