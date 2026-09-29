from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING

import pytest
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import (
    BufferHandler,
    FilterHandler,
    NullHandler,
    SamplingHandler,
    StreamHandler,
    TestHandler,
    UnknownServiceError,
)
from xtr_logging.config import (
    BufferHandlerSpec,
    DeduplicationHandlerSpec,
    FilterHandlerSpec,
    LoggingConfig,
    NullHandlerSpec,
    SamplingHandlerSpec,
    ServiceHandlerSpec,
    StreamHandlerSpec,
)
from xtr_logging.config.handler_builder import HandlerBuilder
from xtr_logging.config.services import Services

if TYPE_CHECKING:
    from pathlib import Path

_MEMBER = ServiceHandlerSpec(id="member", nested=True)


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
            "a": ServiceHandlerSpec(id="a", nested=True),
            "b": ServiceHandlerSpec(id="b", nested=True),
            "mail": DeduplicationHandlerSpec(handler="a"),
            "chat": DeduplicationHandlerSpec(handler="b"),
        }
    )
    builder = HandlerBuilder(config, Services(handlers=sinks))

    for name in ("mail", "chat"):
        handler = builder.build(name)
        _ = handler.handle(make_record(Level.ERROR, "boom"))
        handler.close()

    assert [len(sink.records) for sink in sinks.values()] == [1, 1]


def test_a_stream_spec_gives_its_level_and_bubble() -> None:
    handler = _builder(main=StreamHandlerSpec(level="error", bubble=False)).build("main")

    assert isinstance(handler, StreamHandler)
    assert (handler.level, handler.bubble) == (Level.ERROR, False)


def test_a_null_spec_gives_its_level() -> None:
    handler = _builder(main=NullHandlerSpec(level="warning")).build("main")

    assert isinstance(handler, NullHandler)
    assert handler.level is Level.WARNING


def test_a_buffer_spec_gives_its_level_and_bubble() -> None:
    spec = BufferHandlerSpec(handler="member", level="notice", bubble=False)

    handler = _builder(main=spec).build("main")

    assert isinstance(handler, BufferHandler)
    assert (handler.level, handler.bubble) == (Level.NOTICE, False)


def test_a_filter_spec_gives_its_bubble() -> None:
    handler = _builder(main=FilterHandlerSpec(handler="member", bubble=False)).build("main")

    assert isinstance(handler, FilterHandler)
    assert handler.handle(make_record()) is True


def test_a_sampling_spec_gives_its_bubble() -> None:
    spec = SamplingHandlerSpec(handler="member", factor=1, bubble=False)

    handler = _builder(main=spec).build("main")

    assert isinstance(handler, SamplingHandler)
    assert handler.bubble is False


def test_a_handler_named_twice_is_built_once() -> None:
    builder = _builder(main=StreamHandlerSpec())

    assert builder.build("main") is builder.build("main")


def test_a_service_nobody_supplied_is_refused() -> None:
    config = LoggingConfig(handlers={"main": ServiceHandlerSpec(id="sentry")})

    with pytest.raises(UnknownServiceError):
        _ = HandlerBuilder(config, Services()).build("main")
