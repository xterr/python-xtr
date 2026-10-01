from __future__ import annotations

from xtr_password_hasher import UnknownPasswordHasherError


def test_it_records_what_was_looked_up() -> None:
    error = UnknownPasswordHasherError("acme:User")

    assert error.looked_up == "acme:User"


def test_its_message_names_what_was_looked_up() -> None:
    error = UnknownPasswordHasherError("acme:User")

    assert "acme:User" in str(error)


def test_it_is_a_lookup_error() -> None:
    assert issubclass(UnknownPasswordHasherError, LookupError)
