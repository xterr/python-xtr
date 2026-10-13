from __future__ import annotations

import inspect
import os
from typing import TYPE_CHECKING

import pytest

from tests.support.fake_stream import FakeStream
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import StreamInterface

if TYPE_CHECKING:
    from collections.abc import Callable


def test_a_fake_carrying_every_member_is_a_stream() -> None:
    stream: StreamInterface = FakeStream()

    assert isinstance(stream, StreamInterface)


@pytest.mark.parametrize("missing", sorted(members_of(FakeStream)))
def test_a_fake_missing_a_member_is_not_a_stream(missing: str) -> None:
    assert not isinstance(without(FakeStream, missing)(), StreamInterface)


def test_a_plain_object_is_not_a_stream() -> None:
    assert not isinstance(object(), StreamInterface)


def test_the_contract_declares_no_whole_body_shortcut() -> None:
    assert not hasattr(StreamInterface, "__bytes__")


@pytest.mark.parametrize(
    "method",
    [
        StreamInterface.close,
        StreamInterface.get_contents,
        StreamInterface.read,
        StreamInterface.rewind,
        StreamInterface.seek,
        StreamInterface.write,
    ],
)
def test_a_method_that_moves_bytes_is_awaited(method: Callable[..., object]) -> None:
    assert inspect.iscoroutinefunction(method)


@pytest.mark.parametrize(
    "method",
    [
        StreamInterface.detach,
        StreamInterface.eof,
        StreamInterface.get_metadata,
        StreamInterface.get_size,
        StreamInterface.is_readable,
        StreamInterface.is_seekable,
        StreamInterface.is_writable,
        StreamInterface.tell,
    ],
)
def test_a_method_that_only_reports_what_the_stream_holds_is_not_awaited(
    method: Callable[..., object],
) -> None:
    assert not inspect.iscoroutinefunction(method)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [
        (StreamInterface.seek, "whence", os.SEEK_SET),
        (StreamInterface.get_metadata, "key", None),
    ],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected
