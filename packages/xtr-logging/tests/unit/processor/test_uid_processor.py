from __future__ import annotations

import pytest

from tests.support.records import make_record
from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.processor.uid_processor import UidProcessor


def test_it_adds_a_uid_of_the_requested_length() -> None:
    processor = UidProcessor(10)

    record = processor(make_record())

    assert record.extra["uid"] == processor.uid
    assert len(processor.uid) == 10


def test_the_default_length_is_seven() -> None:
    assert len(UidProcessor().uid) == 7


def test_the_same_uid_rides_every_record_until_reset() -> None:
    processor = UidProcessor()

    first = processor(make_record())
    second = processor(make_record())

    assert first.extra["uid"] == second.extra["uid"]


def test_reset_mints_a_new_uid() -> None:
    processor = UidProcessor()
    before = processor.uid

    processor.reset()

    assert processor.uid != before


def test_a_length_below_one_is_refused() -> None:
    with pytest.raises(InvalidOptionError):
        _ = UidProcessor(0)


def test_a_length_above_thirty_two_is_refused() -> None:
    with pytest.raises(InvalidOptionError):
        _ = UidProcessor(33)
