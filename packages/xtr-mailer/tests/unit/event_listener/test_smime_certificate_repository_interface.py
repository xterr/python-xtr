"""Anything finding a certificate path by address is a certificate repository."""

from __future__ import annotations

from xtr_mailer.event_listener import SmimeCertificateRepositoryInterface


class _Structural:
    def find_certificate_path_for(self, email: str) -> str | None:
        del email
        return None


def test_anything_that_finds_certificates_is_a_repository() -> None:
    assert isinstance(_Structural(), SmimeCertificateRepositoryInterface)


def test_something_that_cannot_find_certificates_is_not_a_repository() -> None:
    assert not isinstance(object(), SmimeCertificateRepositoryInterface)
