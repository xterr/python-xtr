from __future__ import annotations

import pytest

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig


def test_it_builds_with_no_arguments() -> None:
    config = SmtpConnectionConfig()

    assert (config.host, config.port, config.tls) == ("localhost", 25, False)
    assert config.local_hostname == "[127.0.0.1]"
    assert config.validate_certs


def test_its_description_names_the_server() -> None:
    assert SmtpConnectionConfig("mail.example.com", 587).description == "mail.example.com:587"


def test_a_tls_description_is_prefixed() -> None:
    assert SmtpConnectionConfig("mail.example.com", 465, tls=True).description == (
        "ssl://mail.example.com:465"
    )


@pytest.mark.parametrize("fingerprint", ["a" * 32, "B" * 40, "0" * 64])
def test_an_md5_sha1_or_sha256_fingerprint_is_accepted(fingerprint: str) -> None:
    assert SmtpConnectionConfig(peer_fingerprint=fingerprint).peer_fingerprint == fingerprint


@pytest.mark.parametrize("fingerprint", ["abc", "z" * 40, "a" * 50, "aa:" * 20])
def test_a_peer_fingerprint_that_is_no_digest_is_refused(fingerprint: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmtpConnectionConfig(peer_fingerprint=fingerprint)

    assert str(caught.value) == (
        f'The peer fingerprint "{fingerprint}" is not an MD5, SHA-1 or SHA-256 digest in hex.'
    )


@pytest.mark.parametrize(
    "host", ["a\x00b", "a\nb", "a\x7fb", "a\x9bb", "a\u2028b", "a\u2029b", "a\u200bb"]
)
def test_a_host_with_a_control_character_is_refused(host: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmtpConnectionConfig(host)

    assert str(caught.value) == "The SMTP host name must not contain control characters."


@pytest.mark.parametrize("host", ["mail.example.com", "[2001:db8::1]", "bücher.example"])
def test_a_host_name_or_address_is_accepted(host: str) -> None:
    assert SmtpConnectionConfig(host).host == host


@pytest.mark.parametrize(
    "host",
    [
        "smtp..example.com",
        f"{'a' * 64}.example.com",
        "smtp.\ufffd.example.com",
        "smtp.\u3002example.com",
        "exa\udcffmple.com",
    ],
)
def test_a_host_the_resolver_cannot_encode_is_refused_without_showing_it(host: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmtpConnectionConfig(host)

    assert str(caught.value) == "The SMTP host name is not a name the resolver can look up."
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("host", ["192.0.2.1", "::1", "[::1]"])
def test_an_ip_address_is_accepted_as_the_host(host: str) -> None:
    assert SmtpConnectionConfig(host).host == host


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_a_port_out_of_range_is_refused(port: int) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmtpConnectionConfig(port=port)

    assert str(caught.value) == f'The SMTP port must be between 1 and 65535, "{port}" given.'


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0])
def test_a_timeout_that_is_not_a_positive_number_of_seconds_is_refused(timeout: float) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmtpConnectionConfig(timeout=timeout)

    assert str(caught.value) == (
        f'The SMTP timeout must be a positive number of seconds, "{timeout}" given.'
    )


@pytest.mark.parametrize("address", ["192.0.2.1", "2001:db8::1", "[2001:db8::1]"])
def test_a_source_address_that_is_an_ip_address_is_accepted(address: str) -> None:
    assert SmtpConnectionConfig(source_address=address).source_address == address


@pytest.mark.parametrize("address", ["", "mail.example.com", "[192.0.2.1]", "[::1", "1.2.3"])
def test_a_source_address_that_is_no_ip_address_is_refused(address: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmtpConnectionConfig(source_address=address)

    assert str(caught.value) == "The source IP must be an IPv4 or IPv6 address."
