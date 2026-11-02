from __future__ import annotations

import pytest

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.transport.smtp.auth._credentials import base64_line, utf8


def test_a_credential_is_written_in_utf8() -> None:
    assert utf8("pässword") == "pässword".encode()


def test_a_credential_line_is_base64_of_its_utf8() -> None:
    assert base64_line("ä") == "w6Q="


def test_a_credential_utf8_cannot_write_is_refused_without_quoting_it() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = utf8("s3cret\udcff")

    assert str(caught.value) == "The SMTP credentials must only hold characters UTF-8 can write."
    assert caught.value.__context__ is None
    assert "s3cret" not in repr(caught.value.args)
