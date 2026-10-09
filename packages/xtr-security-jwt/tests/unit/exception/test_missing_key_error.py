"""The missing-key error names what to set, and is a configuration error, not a token's."""

from __future__ import annotations

from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.exception import JwtFailureError, MissingKeyError


def test_it_is_an_invalid_argument_and_not_a_token_failure() -> None:
    assert issubclass(MissingKeyError, InvalidArgumentError)
    assert not issubclass(MissingKeyError, JwtFailureError)


def test_with_no_key_configured_it_says_where_to_set_one_and_how_to_mint_it() -> None:
    error = MissingKeyError()

    assert error.location is None
    assert str(error).startswith("No JWT key is configured: set secret_key in <app>/config/jwt.py")
    assert "jwt:generate-keypair --output-dir secrets" in str(error)


def test_with_a_missing_file_it_names_the_file() -> None:
    error = MissingKeyError("secrets/jwt.pem")

    assert error.location == "secrets/jwt.pem"
    assert str(error).startswith("The key file 'secrets/jwt.pem' does not exist:")
