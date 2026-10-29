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
