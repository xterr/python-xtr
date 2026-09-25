from __future__ import annotations

from xtr_logging_contracts import Level

from xtr_logging import Logger, TestHandler
from xtr_logging.processor.introspection_processor import IntrospectionProcessor


def _log_boom(logger: Logger) -> None:
    logger.error("boom")


def test_it_points_at_the_caller_that_logged() -> None:
    # Given a logger whose processor records where each call came from
    handler = TestHandler()
    logger = Logger("app", [handler], [IntrospectionProcessor()])

    # When a record is logged straight from this test function
    logger.error("boom")

    # Then the origin is this test, not the library's own frames
    extra = handler.records[0].extra
    assert extra["file"] == __file__
    assert extra["function"] == "test_it_points_at_the_caller_that_logged"
    assert extra["module"] == __name__
    assert isinstance(extra["line"], int)


def test_a_record_below_the_level_is_left_untouched() -> None:
    # Given a processor that only introspects errors
    handler = TestHandler()
    logger = Logger("app", [handler], [IntrospectionProcessor(Level.ERROR)])

    # When a record below that level is logged
    logger.info("quiet")

    # Then nothing about its origin is added
    assert "file" not in handler.records[0].extra


def test_it_points_at_the_immediate_caller_by_default() -> None:
    # Given a call made through an intermediate helper
    handler = TestHandler()
    logger = Logger("app", [handler], [IntrospectionProcessor()])

    # When the helper logs
    _log_boom(logger)

    # Then the helper is the reported origin
    assert handler.records[0].extra["function"] == "_log_boom"


def test_skip_frames_steps_past_an_intermediate_caller() -> None:
    # Given a processor told to skip one frame past the first outside one
    handler = TestHandler()
    logger = Logger("app", [handler], [IntrospectionProcessor(skip_frames=1)])

    # When a helper logs on this test's behalf
    _log_boom(logger)

    # Then the origin is this test, not the helper
    assert (
        handler.records[0].extra["function"] == "test_skip_frames_steps_past_an_intermediate_caller"
    )
