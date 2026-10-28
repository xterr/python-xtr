"""The recording logger keeps every call, in order, by level."""

from __future__ import annotations

from tests.support.recording_logger import RecordingLogger


def test_it_records_each_call_with_its_level_and_context() -> None:
    logger = RecordingLogger()

    logger.warning("w {key}", {"key": "a"})
    logger.info("i")

    assert logger.records == [("warning", "w {key}", {"key": "a"}), ("info", "i", {})]
    assert logger.messages("warning") == ["w {key}"]


def test_it_hands_back_the_context_of_each_level_on_its_own() -> None:
    logger = RecordingLogger()

    logger.warning("w", {"firewall": "main"})
    logger.info("i", {"ignored": True})

    assert logger.contexts("warning") == [{"firewall": "main"}]
