from __future__ import annotations

import inspect

import pytest

from tests.support.fake_uploaded_file import FakeUploadedFile
from tests.support.missing_member import members_of, without
from xtr_http_message_contracts import UploadedFileInterface


def test_a_fake_carrying_every_member_is_an_uploaded_file() -> None:
    uploaded: UploadedFileInterface = FakeUploadedFile()

    assert isinstance(uploaded, UploadedFileInterface)


@pytest.mark.parametrize("missing", sorted(members_of(FakeUploadedFile)))
def test_a_fake_missing_a_member_is_not_an_uploaded_file(missing: str) -> None:
    assert not isinstance(without(FakeUploadedFile, missing)(), UploadedFileInterface)


def test_a_plain_object_is_not_an_uploaded_file() -> None:
    assert not isinstance(object(), UploadedFileInterface)


def test_moving_the_file_away_is_awaited() -> None:
    assert inspect.iscoroutinefunction(UploadedFileInterface.move_to)
