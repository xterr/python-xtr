"""What a handler worked out about the token a client handed it."""

from __future__ import annotations

from xtr_security_oauth2_server_core.handlers.validated_token import ValidatedToken


def test_it_carries_the_kind_of_token_and_what_it_says() -> None:
    read = ValidatedToken("access_token", {"jti": "access-1"})

    assert read.token_type == "access_token"
    assert read.token_data == {"jti": "access-1"}


def test_two_readings_of_the_same_token_are_the_same_value() -> None:
    assert ValidatedToken("refresh_token", {"refresh_token_id": "refresh-1"}) == ValidatedToken(
        "refresh_token",
        {"refresh_token_id": "refresh-1"},
    )


def test_its_reading_names_the_kind_and_nothing_the_token_says() -> None:
    shown = repr(ValidatedToken("access_token", {"jti": "access-1", "sub": "user-1"}))

    assert shown == "<ValidatedToken access_token>"
