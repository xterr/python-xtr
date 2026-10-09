from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_stream import FakeStream
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import StreamFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import BinaryIO

    from xtr_http_message_contracts import StreamInterface


class _FakeStreamFactory:
    def create_stream(self, content: bytes = b"") -> StreamInterface:
        del content
        return FakeStream()

    def create_stream_from_file(self, filename: str, mode: str = "r") -> StreamInterface:
        del filename, mode
        return FakeStream()

    def create_stream_from_resource(self, resource: BinaryIO) -> StreamInterface:
        del resource
        return FakeStream()


def test_a_fake_carrying_every_member_is_a_stream_factory() -> None:
    factory: StreamFactoryInterface = _FakeStreamFactory()

    assert isinstance(factory, StreamFactoryInterface)


@pytest.mark.parametrize("missing", sorted(members_of(_FakeStreamFactory)))
def test_a_fake_missing_a_member_is_not_a_stream_factory(missing: str) -> None:
    assert not isinstance(without(_FakeStreamFactory, missing)(), StreamFactoryInterface)


def test_a_plain_object_is_not_a_stream_factory() -> None:
    assert not isinstance(object(), StreamFactoryInterface)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [
        (StreamFactoryInterface.create_stream, "content", b""),
        (StreamFactoryInterface.create_stream_from_file, "mode", "r"),
    ],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected
