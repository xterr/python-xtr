from __future__ import annotations

from xtr_mailer.transport.smtp._smtp_reply import render_reply, unexpected_response


def test_a_single_line_reply_is_its_code_and_text() -> None:
    assert render_reply(250, "2.0.0 Ok") == "250 2.0.0 Ok"


def test_a_multiline_reply_marks_every_line_but_the_last_as_continued() -> None:
    assert render_reply(250, "localhost\nPIPELINING\nSIZE 10") == (
        "250-localhost\r\n250-PIPELINING\r\n250 SIZE 10"
    )


def test_a_reply_with_no_text_is_its_code() -> None:
    assert render_reply(250, "") == "250"


def test_a_reply_with_no_code_is_its_text() -> None:
    assert render_reply(-1, "hello there") == "hello there"


def test_a_reply_with_no_code_is_trimmed() -> None:
    assert render_reply(-1, " hello there\r\n") == "hello there"


def test_an_unexpected_reply_names_the_codes_it_was_expected_with() -> None:
    error = unexpected_response([250, 251], 550, "550 Access Denied")

    assert str(error) == (
        'Expected response code "250/251" but got code "550", with message "550 Access Denied".'
    )
    assert error.code == 550


def test_an_empty_reply_is_an_empty_code() -> None:
    error = unexpected_response([220], 0, "")

    assert str(error) == 'Expected response code "220" but got empty code.'
    assert error.code == 0
