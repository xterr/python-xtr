"""The recording logger keeps each line as a reader would see it."""

from __future__ import annotations

from tests.support.recording_logger import RecordingLogger


def test_it_records_each_message_with_its_placeholders_filled() -> None:
    logger = RecordingLogger()

    logger.debug('Email transport "{transport}" started', {"transport": "smtp://localhost"})
    logger.info("plain")

    assert logger.records == ['Email transport "smtp://localhost" started', "plain"]
