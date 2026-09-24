from __future__ import annotations

from xtr_logging import LoggerInterface, NullLogger


def test_a_null_logger_is_a_logger() -> None:
    assert isinstance(NullLogger(), LoggerInterface)


def test_a_null_logger_accepts_every_call_without_checking_the_level() -> None:
    logger = NullLogger()

    logger.emergency("gone", {"exception": RuntimeError()})
    logger.log("not a level", "still fine")
