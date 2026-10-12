from __future__ import annotations

from xtr_remote_event.exception import InvalidArgumentError, ParseError, RemoteEventError


def test_it_is_an_invalid_argument_and_so_derives_from_the_base() -> None:
    error = ParseError("payload has no id")

    assert isinstance(error, InvalidArgumentError)
    assert isinstance(error, RemoteEventError)
