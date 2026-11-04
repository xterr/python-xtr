"""The repository finding an address's S/MIME certificate in a mapping it was given."""

from __future__ import annotations

from xtr_mailer.event_listener import (
    InMemorySmimeCertificateRepository,
    SmimeCertificateRepositoryInterface,
)


def test_returns_the_configured_certificate_path() -> None:
    repository = InMemorySmimeCertificateRepository({"user@example.com": "/path/to/user.crt"})

    assert repository.find_certificate_path_for("user@example.com") == "/path/to/user.crt"


def test_returns_none_for_unknown_address() -> None:
    repository = InMemorySmimeCertificateRepository()

    assert repository.find_certificate_path_for("unknown@example.com") is None


def test_an_address_is_found_as_written_only() -> None:
    repository = InMemorySmimeCertificateRepository({"user@example.com": "/path/to/user.crt"})

    assert repository.find_certificate_path_for("User@example.com") is None


def test_changing_the_mapping_given_leaves_the_repository_as_it_was() -> None:
    certificates = {"user@example.com": "/path/to/user.crt"}
    repository = InMemorySmimeCertificateRepository(certificates)

    certificates["user@example.com"] = "/path/to/other.crt"

    assert repository.find_certificate_path_for("user@example.com") == "/path/to/user.crt"


def test_it_is_a_certificate_repository() -> None:
    assert isinstance(InMemorySmimeCertificateRepository(), SmimeCertificateRepositoryInterface)
