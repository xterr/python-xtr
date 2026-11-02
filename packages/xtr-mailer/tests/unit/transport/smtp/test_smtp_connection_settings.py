from __future__ import annotations

import pytest

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig
from xtr_mailer.transport.smtp._smtp_connection_settings import SmtpConnectionSettings


def _settings(config: SmtpConnectionConfig | None = None) -> SmtpConnectionSettings:
    settings = SmtpConnectionSettings()
    if config is not None:
        settings._config = config
    return settings


@pytest.mark.parametrize(
    ("config", "name"),
    [
        (SmtpConnectionConfig("mail.example.com", 25), "smtp://mail.example.com"),
        (SmtpConnectionConfig("mail.example.com", 465, tls=True), "smtps://mail.example.com"),
        (SmtpConnectionConfig("mail.example.com", 587), "smtp://mail.example.com:587"),
        (SmtpConnectionConfig("mail.example.com", 465), "smtp://mail.example.com:465"),
        (SmtpConnectionConfig("mail.example.com", 25, tls=True), "smtps://mail.example.com"),
    ],
)
def test_the_server_is_named_with_its_port_unless_the_default(
    config: SmtpConnectionConfig, name: str
) -> None:
    assert _settings(config)._server_name() == name


def test_the_defaults_are_those_of_a_local_session() -> None:
    settings = _settings()

    assert settings.get_local_domain() == "[127.0.0.1]"
    assert settings.get_timeout() == 60.0
    assert settings.is_peer_verified()


@pytest.mark.parametrize(
    ("domain", "written"),
    [
        ("client.example.com", "client.example.com"),
        ("192.0.2.1", "[192.0.2.1]"),
        ("2001:db8::1", "[IPv6:2001:db8::1]"),
        ("[192.0.2.1]", "[192.0.2.1]"),
        ("", ""),
    ],
)
def test_a_local_domain_that_is_an_address_is_bracketed(domain: str, written: str) -> None:
    assert _settings().set_local_domain(domain).get_local_domain() == written


@pytest.mark.parametrize("domain", ["client\r\n.example", "client\x00", "client\x7f"])
def test_a_local_domain_with_a_control_character_is_refused(domain: str) -> None:
    with pytest.raises(InvalidArgumentError, match="control characters"):
        _ = _settings().set_local_domain(domain)


def test_the_timeout_is_kept_in_seconds() -> None:
    assert _settings().set_timeout(5).get_timeout() == 5.0


@pytest.mark.parametrize("seconds", [float("nan"), float("inf"), 0, -1])
def test_a_timeout_that_would_wait_forever_or_not_at_all_is_refused(seconds: float) -> None:
    with pytest.raises(InvalidArgumentError, match="positive number of seconds"):
        _ = _settings().set_timeout(seconds)


def test_the_source_ip_is_the_system_choice_by_default() -> None:
    assert _settings().get_source_ip() is None


@pytest.mark.parametrize("address", ["192.0.2.1", "2001:db8::1", "[2001:db8::1]"])
def test_a_source_ip_reaches_the_next_session(address: str) -> None:
    settings = _settings().set_source_ip(address)

    assert settings.get_source_ip() == address
    assert settings._config.source_address == address


def test_the_source_ip_can_be_left_to_the_system_again() -> None:
    assert _settings().set_source_ip("192.0.2.1").set_source_ip(None).get_source_ip() is None


def test_a_source_ip_that_is_no_address_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="IPv4 or IPv6 address"):
        _ = _settings().set_source_ip("mail.example.com")


def test_peer_verification_can_be_turned_off() -> None:
    assert not _settings().set_verify_peer(False).is_peer_verified()


def test_a_peer_fingerprint_reaches_the_next_session() -> None:
    settings = _settings().set_peer_fingerprint("ab" * 32)

    assert settings._config.peer_fingerprint == "ab" * 32


def test_a_peer_fingerprint_no_digest_could_produce_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="not an MD5, SHA-1 or SHA-256 digest"):
        _ = _settings().set_peer_fingerprint("abc")


def test_a_setting_leaves_the_other_settings_alone() -> None:
    settings = _settings(SmtpConnectionConfig("mail.example.com", 2525))

    _ = settings.set_timeout(5).set_local_domain("client.example")

    assert settings._config == SmtpConnectionConfig(
        "mail.example.com", 2525, timeout=5.0, local_hostname="client.example"
    )
