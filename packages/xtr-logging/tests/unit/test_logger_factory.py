from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock

from tests.support.records import AT
from tests.support.stdlib import Collector
from xtr_logging import Level, LogRecord, TestHandler
from xtr_logging.config import (
    BufferHandlerSpec,
    CapturedLoggerSpec,
    CaptureSpec,
    ConsoleHandlerSpec,
    FingersCrossedHandlerSpec,
    LoggingConfig,
    NullHandlerSpec,
    ServiceHandlerSpec,
    ServiceProcessorSpec,
    Services,
    UidProcessorSpec,
)
from xtr_logging.exception.not_processable_handler_error import NotProcessableHandlerError
from xtr_logging.exception.unknown_channel_error import UnknownChannelError
from xtr_logging.exception.unknown_handler_error import UnknownHandlerError
from xtr_logging.exception.unknown_service_error import UnknownServiceError
from xtr_logging.handler.console_handler import ConsoleHandler
from xtr_logging.logger_factory import LoggerFactory
from xtr_logging.processor.processor_registry import ProcessorDescriptor, ProcessorRegistry
from xtr_logging.verbosity import Verbosity

if TYPE_CHECKING:
    from collections.abc import Callable


def _stamp(tag: str) -> Callable[[LogRecord], LogRecord]:
    def processor(record: LogRecord, /) -> LogRecord:
        seen = record.extra.get("tags", "")
        return record.with_extra({"tags": f"{seen}{tag}"})

    return processor


def _factory(config: LoggingConfig, **handlers: TestHandler) -> LoggerFactory:
    return LoggerFactory(config, services=Services(handlers=handlers), registry=ProcessorRegistry())


def test_a_logger_for_the_default_channel_is_returned_when_none_is_named() -> None:
    factory = _factory(LoggingConfig())

    assert factory.logger().name == "app"


def test_the_same_channel_returns_the_same_logger() -> None:
    factory = _factory(LoggingConfig(channels=("db",)))

    assert factory.logger("db") is factory.logger("db")


def test_an_undeclared_channel_is_refused() -> None:
    with pytest.raises(UnknownChannelError) as raised:
        _ = _factory(LoggingConfig()).logger("nowhere")

    assert raised.value.known == ("app",)


def test_handlers_are_shared_between_channels() -> None:
    main = TestHandler()
    factory = _factory(
        LoggingConfig(channels=("db",), handlers={"main": ServiceHandlerSpec(id="main")}),
        main=main,
    )

    factory.logger().info("from app")
    factory.logger("db").info("from db")

    assert [record.channel for record in main.records] == ["app", "db"]


def test_a_channel_filter_routes_records_to_the_right_handlers() -> None:
    security, rest = TestHandler(), TestHandler()
    factory = _factory(
        LoggingConfig(
            handlers={
                "security": ServiceHandlerSpec(id="security", channels="security"),
                "rest": ServiceHandlerSpec(id="rest", channels="!security"),
            },
        ),
        security=security,
        rest=rest,
    )

    factory.logger("security").warning("denied")
    factory.logger().warning("slow")

    assert [r.message for r in security.records] == ["denied"]
    assert [r.message for r in rest.records] == ["slow"]


def test_higher_priority_handlers_are_consulted_first() -> None:
    first, second = TestHandler(bubble=False), TestHandler()
    factory = _factory(
        LoggingConfig(
            handlers={
                "second": ServiceHandlerSpec(id="second"),
                "first": ServiceHandlerSpec(id="first", priority=10),
            },
        ),
        first=first,
        second=second,
    )

    factory.logger().info("x")

    assert len(first.records) == 1
    assert second.records == ()


def test_a_nested_handler_only_receives_what_its_wrapper_passes() -> None:
    file = TestHandler()
    factory = _factory(
        LoggingConfig(
            handlers={
                "main": FingersCrossedHandlerSpec(handler="file", action_level="error"),
                "file": ServiceHandlerSpec(id="file"),
            },
        ),
        file=file,
    )
    logger = factory.logger()

    logger.info("context")
    assert file.records == ()
    logger.error("failure")

    assert [r.message for r in file.records] == ["context", "failure"]


def test_close_flushes_buffers() -> None:
    file = TestHandler()
    factory = _factory(
        LoggingConfig(
            handlers={
                "buffer": BufferHandlerSpec(handler="file"),
                "file": ServiceHandlerSpec(id="file"),
            },
        ),
        file=file,
    )
    factory.logger().info("buffered")

    factory.close()

    assert [r.message for r in file.records] == ["buffered"]


def test_the_factory_is_a_context_manager_that_closes() -> None:
    file = TestHandler()
    config = LoggingConfig(
        handlers={
            "buffer": BufferHandlerSpec(handler="file"),
            "file": ServiceHandlerSpec(id="file"),
        },
    )

    with _factory(config, file=file) as factory:
        factory.logger().info("buffered")

    assert len(file.records) == 1


def test_processors_run_by_priority_and_respect_their_channel() -> None:
    main = TestHandler()
    factory = LoggerFactory(
        LoggingConfig(
            channels=("db",),
            handlers={"main": ServiceHandlerSpec(id="main")},
            processors=(
                ServiceProcessorSpec(id="a"),
                ServiceProcessorSpec(id="b", priority=5),
                ServiceProcessorSpec(id="db_only", channel="db"),
            ),
        ),
        services=Services(
            handlers={"main": main},
            processors={"a": _stamp("a"), "b": _stamp("b"), "db_only": _stamp("d")},
        ),
        registry=ProcessorRegistry(),
    )

    factory.logger().info("x")
    factory.logger("db").info("y")

    assert [r.extra["tags"] for r in main.records] == ["ba", "bad"]


def test_a_processor_can_target_a_handler() -> None:
    main = TestHandler()
    factory = LoggerFactory(
        LoggingConfig(
            handlers={"main": ServiceHandlerSpec(id="main")},
            processors=(UidProcessorSpec(handler="main"),),
        ),
        services=Services(handlers={"main": main}),
        registry=ProcessorRegistry(),
    )

    factory.logger().info("x")

    assert "uid" in main.records[0].extra
    assert factory.logger().processors == ()


def test_a_processor_targeting_a_handler_that_runs_none_is_refused() -> None:
    with pytest.raises(NotProcessableHandlerError):
        _ = LoggerFactory(
            LoggingConfig(
                handlers={"null": NullHandlerSpec()},
                processors=(UidProcessorSpec(handler="null"),),
            ),
            registry=ProcessorRegistry(),
        )


def test_declared_processors_are_attached() -> None:
    main = TestHandler()
    registry = ProcessorRegistry()
    registry.register(ProcessorDescriptor(_stamp("r")))

    factory = LoggerFactory(
        LoggingConfig(handlers={"main": ServiceHandlerSpec(id="main")}),
        services=Services(handlers={"main": main}),
        registry=registry,
    )
    factory.logger().info("x")

    assert main.records[0].extra["tags"] == "r"


def test_a_declared_processor_for_an_unknown_handler_is_refused() -> None:
    registry = ProcessorRegistry()
    registry.register(ProcessorDescriptor(_stamp("r"), handler="nope"))

    with pytest.raises(UnknownHandlerError):
        _ = LoggerFactory(LoggingConfig(), registry=registry)


def test_a_missing_service_is_refused_when_the_factory_is_made() -> None:
    with pytest.raises(UnknownServiceError) as raised:
        _ = LoggerFactory(LoggingConfig(handlers={"x": ServiceHandlerSpec(id="sentry")}))

    assert (raised.value.kind, raised.value.service_id) == ("handler", "sentry")


def test_handler_returns_a_configured_handler_by_name() -> None:
    main = TestHandler()
    factory = _factory(LoggingConfig(handlers={"main": ServiceHandlerSpec(id="main")}), main=main)

    assert factory.handler("main") is main


def test_handler_refuses_an_unknown_name() -> None:
    with pytest.raises(UnknownHandlerError):
        _ = _factory(LoggingConfig()).handler("main")


def test_set_verbosity_reaches_console_handlers() -> None:
    factory = _factory(LoggingConfig(handlers={"console": ConsoleHandlerSpec()}))

    factory.set_verbosity(Verbosity.DEBUG)

    console = factory.handler("console")
    assert isinstance(console, ConsoleHandler)
    assert console.level is Level.DEBUG


def test_reset_ends_a_unit_of_work() -> None:
    main = TestHandler()
    factory = _factory(LoggingConfig(handlers={"main": ServiceHandlerSpec(id="main")}), main=main)
    factory.logger().info("x")

    factory.reset()

    assert main.records == ()


def test_loggers_read_time_from_the_clock_given() -> None:
    main = TestHandler()
    clock = MockClock(AT)
    factory = LoggerFactory(
        LoggingConfig(handlers={"main": ServiceHandlerSpec(id="main")}),
        services=Services(handlers={"main": main}),
        registry=ProcessorRegistry(),
        clock=clock,
    )

    factory.logger().info("x")

    assert main.records[0].datetime == clock.now()


@pytest.mark.usefixtures("stdlib_logging")
def test_a_capture_section_takes_over_stdlib_until_the_factory_closes() -> None:
    main, console = TestHandler(), Collector()
    logging.getLogger().addHandler(console)
    factory = _factory(
        LoggingConfig(
            channels=("http",),
            handlers={"main": ServiceHandlerSpec(id="main")},
            capture=CaptureSpec(
                loggers={"httpx": CapturedLoggerSpec(level="info", channel="http")}
            ),
        ),
        main=main,
    )

    logging.getLogger("httpx").info("GET /health 200")
    factory.close()
    logging.getLogger("httpx").warning("after close")

    assert [(r.channel, r.message) for r in main.records] == [("http", "GET /health 200")]
    assert console.messages == ["after close"]


def test_without_a_capture_section_stdlib_is_left_alone() -> None:
    assert _factory(LoggingConfig()).capture is None
