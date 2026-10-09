from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_uploaded_file import FakeUploadedFile
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import UploadedFileFactoryInterface, UploadError

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_message_contracts import StreamInterface, UploadedFileInterface


class _FakeUploadedFileFactory:
    def create_uploaded_file(
        self,
        stream: StreamInterface,
        size: int | None = None,
        error: int = UploadError.OK,
        client_filename: str | None = None,
        client_media_type: str | None = None,
    ) -> UploadedFileInterface:
        del stream, size, error, client_filename, client_media_type
        return FakeUploadedFile()


def test_a_fake_carrying_every_member_is_an_uploaded_file_factory() -> None:
    factory: UploadedFileFactoryInterface = _FakeUploadedFileFactory()

    assert isinstance(factory, UploadedFileFactoryInterface)


@pytest.mark.parametrize("missing", sorted(members_of(_FakeUploadedFileFactory)))
def test_a_fake_missing_a_member_is_not_an_uploaded_file_factory(missing: str) -> None:
    assert not isinstance(
        without(_FakeUploadedFileFactory, missing)(), UploadedFileFactoryInterface
    )


def test_a_plain_object_is_not_an_uploaded_file_factory() -> None:
    assert not isinstance(object(), UploadedFileFactoryInterface)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [
        (UploadedFileFactoryInterface.create_uploaded_file, "size", None),
        (UploadedFileFactoryInterface.create_uploaded_file, "error", UploadError.OK),
        (UploadedFileFactoryInterface.create_uploaded_file, "client_filename", None),
        (UploadedFileFactoryInterface.create_uploaded_file, "client_media_type", None),
    ],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected
