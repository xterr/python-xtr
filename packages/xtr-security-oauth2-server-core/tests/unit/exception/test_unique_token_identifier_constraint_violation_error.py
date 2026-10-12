"""The collision a grant retries past, and gives up on."""

from __future__ import annotations

from xtr_security_oauth2_server_core.exception import (
    OAuthServerError,
    UniqueTokenIdentifierConstraintViolationError,
)


def test_it_reports_that_no_free_identifier_could_be_found() -> None:
    error = UniqueTokenIdentifierConstraintViolationError.create()

    assert str(error) == "Could not create unique access token identifier"
    assert error.get_code() == 100
    assert error.get_error_type() == "access_token_duplicate"
    assert error.get_http_status_code() == 500


def test_it_is_one_of_the_protocol_errors() -> None:
    # A grant catches it by this base while it retries, and lets everything
    # else through.
    assert issubclass(UniqueTokenIdentifierConstraintViolationError, OAuthServerError)
