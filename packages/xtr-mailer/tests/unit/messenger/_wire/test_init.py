"""A queued email and its envelope as plain data: versioned, and read back only if it fits."""

from __future__ import annotations

import json

import pytest
from xtr_mime import Address, Email

from xtr_mailer import Envelope
from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.messenger._wire import read, write


def _email() -> Email:
    return Email().from_("a@example.com").to("b@example.com").text("Hi")


def test_what_is_written_is_plain_json_data() -> None:
    written = write(_email(), None)

    assert json.loads(json.dumps(written)) == written


def test_it_is_written_under_version_1() -> None:
    assert write(_email(), None)["version"] == 1


def test_the_email_and_its_envelope_come_back() -> None:
    envelope = Envelope(Address("s@example.com"), [Address("r@example.com")])

    message, back = read(write(_email(), envelope))

    assert isinstance(message, Email)
    assert back is not None
    assert back.get_recipients() == [Address("r@example.com")]


def test_reading_what_was_written_writes_the_same_data_again() -> None:
    written = write(_email().attach(b"x", "x.bin"), None)

    assert write(*read(written)) == written


@pytest.mark.parametrize("version", [2, 0, "1", None])
def test_another_version_is_refused(version: object) -> None:
    with pytest.raises(InvalidArgumentError, match="version"):
        _ = read({**write(_email(), None), "version": version})


@pytest.mark.parametrize("data", [None, [], "email", {"version": 1}])
def test_data_of_another_shape_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = read(data)
