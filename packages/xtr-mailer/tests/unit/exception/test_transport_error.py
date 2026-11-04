from __future__ import annotations

from xtr_mailer.exception import MailerRuntimeError, TransportError


def test_it_is_a_runtime_failure() -> None:
    assert issubclass(TransportError, MailerRuntimeError)


def test_it_starts_with_an_empty_transcript_and_no_code() -> None:
    error = TransportError("Connection could not be established.")

    assert str(error) == "Connection could not be established."
    assert error.debug == ""
    assert error.code == 0


def test_it_carries_the_code_it_was_given() -> None:
    assert TransportError("Failed to authenticate.", 535).code == 535


def test_it_appends_to_its_transcript() -> None:
    error = TransportError("failed")

    error.append_debug("> EHLO [127.0.0.1]\n")
    error.append_debug("< 250 OK\n")

    assert error.debug == "> EHLO [127.0.0.1]\n< 250 OK\n"
