from __future__ import annotations

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
    FilterHandlerSpec,
    LoggingConfig,
    NullHandlerSpec,
    SamplingHandlerSpec,
    ServiceHandlerSpec,
    StreamHandlerSpec,
)
from xtr_logging.config.handler_builder import HandlerBuilder
from xtr_logging.config.services import Services

_MEMBER = ServiceHandlerSpec(id="member", nested=True)


def _builder(**handlers: object) -> HandlerBuilder:
    config = LoggingConfig(handlers={"member": _MEMBER, **handlers})  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
    return HandlerBuilder(config, Services(handlers={"member": TestHandler()}))


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
