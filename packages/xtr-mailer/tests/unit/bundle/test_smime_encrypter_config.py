from __future__ import annotations

from typing import cast

import pytest
from xtr_dependency_injection import Reference

from xtr_mailer.bundle import SmimeEncrypterConfig
from xtr_mailer.event_listener import InMemorySmimeCertificateRepository
from xtr_mailer.exception import InvalidArgumentError

_CERTIFICATES = {"r1@example.com": "r1.crt"}


def test_by_default_a_recipient_without_a_certificate_fails_the_email_with_aes_256() -> None:
    config = SmimeEncrypterConfig(certificates=_CERTIFICATES)

    assert (config.cipher, config.on_missing_certificate, config.encrypt_for_sender) == (
        "aes-256-cbc",
        "fail",
        False,
    )


def test_a_repository_service_may_find_the_certificates() -> None:
    repository = Reference(InMemorySmimeCertificateRepository, "certificates")

    assert SmimeEncrypterConfig(repository=repository).repository == repository


def test_a_repository_and_certificates_cannot_be_used_together() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmimeEncrypterConfig(
            repository=Reference(InMemorySmimeCertificateRepository),
            certificates=_CERTIFICATES,
        )

    assert str(caught.value) == '"repository" and "certificates" cannot be used together.'


def test_an_encrypter_with_no_certificates_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmimeEncrypterConfig()

    assert str(caught.value) == 'The S/MIME encrypter needs a "repository" or "certificates".'


def test_a_repository_qualifier_must_be_a_string() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmimeEncrypterConfig(repository=Reference(InMemorySmimeCertificateRepository, 3))

    assert str(caught.value) == 'The S/MIME "repository" qualifier must be a string.'


@pytest.mark.parametrize("mode", ["encrypt", "skip"])
def test_a_known_mode_is_kept(mode: str) -> None:
    config = SmimeEncrypterConfig(certificates=_CERTIFICATES, on_missing_certificate=mode)

    assert config.on_missing_certificate == mode


def test_an_unknown_mode_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmimeEncrypterConfig(certificates=_CERTIFICATES, on_missing_certificate="drop")

    assert str(caught.value) == (
        'The "on_missing_certificate" option must be "fail", "encrypt" or "skip" (got "drop").'
    )


def test_a_mode_that_is_not_a_string_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmimeEncrypterConfig(
            certificates=_CERTIFICATES, on_missing_certificate=_as_text(["fail"])
        )

    assert str(caught.value) == (
        'The "on_missing_certificate" option must be "fail", "encrypt" or "skip" '
        '(got a value of type "list").'
    )


@pytest.mark.parametrize("cipher", ["aes-128-cbc", "aes-256-cbc"])
def test_an_aes_cipher_is_kept(cipher: str) -> None:
    assert SmimeEncrypterConfig(certificates=_CERTIFICATES, cipher=cipher).cipher == cipher


def test_a_cipher_the_encrypter_cannot_use_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmimeEncrypterConfig(certificates=_CERTIFICATES, cipher="des")

    assert str(caught.value) == (
        'The "des" S/MIME cipher is not supported; use "aes-128-cbc" or "aes-256-cbc".'
    )


def test_an_unknown_cipher_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmimeEncrypterConfig(certificates=_CERTIFICATES, cipher="rot13")

    assert str(caught.value) == 'Invalid S/MIME cipher "rot13".'


def test_a_cipher_that_is_not_a_string_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmimeEncrypterConfig(certificates=_CERTIFICATES, cipher=_as_text(256))

    assert str(caught.value) == 'Invalid S/MIME cipher (got a value of type "int").'


def _as_text(value: object) -> str:
    """Hand ``value`` over where text is expected, as an application's mistake would."""
    return cast("str", value)
