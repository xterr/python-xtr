"""A missing key file is refused in this server's terms."""

from __future__ import annotations

from xtr_security_jwt.exception import MissingKeyError

from xtr_security_oauth2_server._missing_key_file import MINT_COMMAND, missing_key_file


def test_it_names_the_file_the_setting_and_the_command() -> None:
    refusal = missing_key_file(
        MissingKeyError("/srv/secrets/oauth2.pem"),
        "authorization_server.private_key",
        "nothing signs",
    )

    message = str(refusal)
    assert "'/srv/secrets/oauth2.pem'" in message
    assert "authorization_server.private_key names" in message
    assert "so nothing signs." in message
    assert "<app>/config/packages/oauth2_server.py" in message
    assert MINT_COMMAND in message


def test_it_says_where_the_written_configuration_reads_the_setting() -> None:
    refusal = missing_key_file(
        MissingKeyError("/k.pem"),
        "authorization_server.private_key",
        "nothing signs",
        " — read from THE_VARIABLE",
    )

    assert "config/packages/oauth2_server.py — read from THE_VARIABLE," in str(refusal)
