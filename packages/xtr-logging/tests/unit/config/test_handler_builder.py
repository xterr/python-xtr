from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import (
    AbstractHandler,
    BufferHandler,
    FilterHandler,
    LogRecord,
    NullHandler,
    QueueHandler,
    SamplingHandler,
    StreamHandler,
    TestHandler,
    UnknownServiceError,
)
from xtr_logging.config import (
    BufferHandlerConfig,
    DeduplicationHandlerConfig,
    FilterHandlerConfig,
    LoggingConfig,
    NullHandlerConfig,
    QueueHandlerConfig,
    SamplingHandlerConfig,
    ServiceHandlerConfig,
    StreamHandlerConfig,
)
from xtr_logging.config.handler_builder import HandlerBuilder
from xtr_logging.config.services import Services

if TYPE_CHECKING:
    from pathlib import Path

_MEMBER = ServiceHandlerConfig(id="member", nested=True)


@final
class _Raising(AbstractHandler):
    """A handler that fails on every record, to exercise a queue's ``on_error``."""

    @override
    def handle(self, record: LogRecord, /) -> bool:
        raise RuntimeError("boom")


def _builder(**handlers: object) -> HandlerBuilder:
    # The wrong type is the case under test.
    config = LoggingConfig(handlers={"member": _MEMBER, **handlers})  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
    return HandlerBuilder(config, Services(handlers={"member": TestHandler()}))


def test_deduplication_handlers_of_alike_sinks_keep_stores_of_their_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    sinks = {"a": TestHandler(), "b": TestHandler()}
    config = LoggingConfig(
        handlers={
            "a": ServiceHandlerConfig(id="a", nested=True),
            "b": ServiceHandlerConfig(id="b", nested=True),
            "mail": DeduplicationHandlerConfig(handler="a"),
            "chat": DeduplicationHandlerConfig(handler="b"),
        }
    )
    builder = HandlerBuilder(config, Services(handlers=sinks))

    for name in ("mail", "chat"):
        handler = builder.build(name)
        _ = handler.handle(make_record(Level.ERROR, "boom"))
        handler.close()

    assert [len(sink.records) for sink in sinks.values()] == [1, 1]


def test_a_stream_config_gives_its_level_and_bubble() -> None:
    handler = _builder(main=StreamHandlerConfig(level="error", bubble=False)).build("main")

    assert isinstance(handler, StreamHandler)
    assert (handler.level, handler.bubble) == (Level.ERROR, False)


def test_a_null_config_gives_its_level() -> None:
    handler = _builder(main=NullHandlerConfig(level="warning")).build("main")

    assert isinstance(handler, NullHandler)
    assert handler.level is Level.WARNING


def test_a_buffer_config_gives_its_level_and_bubble() -> None:
    buffer = BufferHandlerConfig(handler="member", level="notice", bubble=False)

    handler = _builder(main=buffer).build("main")

    assert isinstance(handler, BufferHandler)
    assert (handler.level, handler.bubble) == (Level.NOTICE, False)


def test_a_filter_config_gives_its_bubble() -> None:
    handler = _builder(main=FilterHandlerConfig(handler="member", bubble=False)).build("main")

    assert isinstance(handler, FilterHandler)
    assert handler.handle(make_record()) is True


def test_a_sampling_config_gives_its_bubble() -> None:
    sampling = SamplingHandlerConfig(handler="member", factor=1, bubble=False)

    handler = _builder(main=sampling).build("main")

    assert isinstance(handler, SamplingHandler)
    assert handler.bubble is False


def test_a_handler_named_twice_is_built_once() -> None:
    builder = _builder(main=StreamHandlerConfig())

    assert builder.build("main") is builder.build("main")


def test_a_service_nobody_supplied_is_refused() -> None:
    config = LoggingConfig(handlers={"main": ServiceHandlerConfig(id="sentry")})

    with pytest.raises(UnknownServiceError):
        _ = HandlerBuilder(config, Services()).build("main")


def test_a_stream_config_passes_its_open_mode(tmp_path: Path) -> None:
    target = tmp_path / "app.log"
    _ = target.write_text("stale\n", encoding="utf-8")
    handler = _builder(main=StreamHandlerConfig(path=str(target), mode="w")).build("main")

    assert isinstance(handler, StreamHandler)
    _ = handler.handle(make_record(message="fresh"))
    handler.close()
    # mode="w" reached the handler, so the stale content was truncated.
    text = target.read_text(encoding="utf-8")
    assert "stale" not in text
    assert "fresh" in text


def test_a_queue_config_runs_its_resolved_on_error_handler() -> None:
    seen: list[Exception] = []

    def report(error: Exception, _record: LogRecord) -> None:
        seen.append(error)

    config = LoggingConfig(
        handlers={
            "member": ServiceHandlerConfig(id="member", nested=True),
            "main": QueueHandlerConfig(handler="member", on_error="report"),
        },
    )
    builder = HandlerBuilder(
        config,
        Services(handlers={"member": _Raising()}, error_handlers={"report": report}),
    )
    handler = builder.build("main")
    assert isinstance(handler, QueueHandler)

    _ = handler.handle(make_record(message="x"))
    handler.flush()
    handler.close()

    assert len(seen) == 1
    assert isinstance(seen[0], RuntimeError)


def test_a_queue_config_naming_an_unknown_on_error_handler_is_refused() -> None:
    config = LoggingConfig(
        handlers={
            "member": _MEMBER,
            "main": QueueHandlerConfig(handler="member", on_error="missing"),
        },
    )
    builder = HandlerBuilder(config, Services(handlers={"member": TestHandler()}))

    with pytest.raises(UnknownServiceError):
        _ = builder.build("main")
