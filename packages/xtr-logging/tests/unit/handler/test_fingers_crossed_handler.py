from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from tests.support.records import make_record
from xtr_logging import AbstractHandler, HandlerInterface, Level, LogRecord
from xtr_logging.handler.fingers_crossed_handler import FingersCrossedHandler

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
class Spy(AbstractHandler):
    """Remembers everything it was asked to do, and never forgets it."""

    def __init__(self, level: Level = Level.DEBUG, bubble: bool = True) -> None:
        super().__init__(level, bubble)
        self.handled: list[LogRecord] = []
        self.closed = 0
        self.resets = 0

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.handled.append(record)
        return not self.bubble

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        self.handled.extend(records)

    @override
    def close(self) -> None:
        self.closed += 1

    @override
    def reset(self) -> None:
        self.resets += 1


@final
class CountingFactory:
    """Builds one handler, lazily, and counts how often it was asked to."""

    def __init__(self, handler: HandlerInterface) -> None:
        self.handler = handler
        self.calls = 0

    def __call__(
        self, record: LogRecord | None, owner: FingersCrossedHandler, /
    ) -> HandlerInterface:
        self.calls += 1
        return self.handler


def _stamp(record: LogRecord, /) -> LogRecord:
    return record.with_extra({"stamped": True})


def test_it_buffers_until_a_record_activates() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy)

    _ = handler.handle(make_record(Level.INFO, "info"))

    assert spy.handled == []


def test_activation_flushes_the_whole_buffer() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy)

    _ = handler.handle(make_record(Level.INFO, "info"))
    _ = handler.handle(make_record(Level.WARNING, "warning"))

    assert [record.message for record in spy.handled] == ["info", "warning"]


def test_records_pass_straight_through_after_activation() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy)

    _ = handler.handle(make_record(Level.WARNING, "warning"))
    _ = handler.handle(make_record(Level.DEBUG, "after"))

    assert [record.message for record in spy.handled] == ["warning", "after"]


def test_nothing_is_forwarded_when_no_record_activates() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy)

    _ = handler.handle(make_record(Level.INFO, "info"))
    handler.close()

    assert spy.handled == []
    assert spy.closed == 1


def test_activate_flushes_the_buffer_manually() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy)
    _ = handler.handle(make_record(Level.INFO, "info"))

    handler.activate()

    assert [record.message for record in spy.handled] == ["info"]


def test_buffer_size_keeps_only_the_most_recent_records() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy, buffer_size=2)
    for message in ("a", "b", "c"):
        _ = handler.handle(make_record(Level.DEBUG, message))

    handler.activate()

    assert [record.message for record in spy.handled] == ["b", "c"]


def test_stop_buffering_off_keeps_buffering_after_activation() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy, stop_buffering=False)

    _ = handler.handle(make_record(Level.WARNING, "first"))
    _ = handler.handle(make_record(Level.INFO, "between"))
    _ = handler.handle(make_record(Level.WARNING, "second"))

    assert [record.message for record in spy.handled] == ["first", "between", "second"]


def test_the_passthru_floor_is_flushed_on_close() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(
        spy, activation_strategy=Level.ERROR, passthru_level=Level.WARNING
    )

    _ = handler.handle(make_record(Level.INFO, "info"))
    _ = handler.handle(make_record(Level.WARNING, "warning"))
    handler.close()

    assert [record.message for record in spy.handled] == ["warning"]


def test_reset_resets_the_wrapped_handler() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy)
    _ = handler.handle(make_record(Level.WARNING, "warning"))

    handler.reset()

    assert spy.resets == 1


def test_reset_starts_buffering_again() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy)
    _ = handler.handle(make_record(Level.WARNING, "warning"))
    handler.reset()
    spy.handled.clear()

    _ = handler.handle(make_record(Level.INFO, "after reset"))

    assert spy.handled == []


def test_clear_discards_the_buffer_even_with_a_passthru_floor() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy, passthru_level=Level.DEBUG)
    _ = handler.handle(make_record(Level.INFO, "info"))

    handler.clear()

    assert spy.handled == []


def test_is_handling_is_always_true() -> None:
    handler = FingersCrossedHandler(Spy())

    assert handler.is_handling(make_record(Level.DEBUG))


def test_bubble_off_stops_the_record() -> None:
    assert FingersCrossedHandler(Spy(), bubble=False).handle(make_record())


def test_a_level_is_accepted_as_an_activation_strategy() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy, activation_strategy=Level.ERROR)

    _ = handler.handle(make_record(Level.WARNING, "warning"))
    _ = handler.handle(make_record(Level.ERROR, "error"))

    assert [record.message for record in spy.handled] == ["warning", "error"]


def test_its_processors_run_before_buffering() -> None:
    spy = Spy()
    handler = FingersCrossedHandler(spy)
    handler.push_processor(_stamp)

    _ = handler.handle(make_record(Level.WARNING))

    assert spy.handled[0].extra["stamped"] is True


def test_a_handler_factory_is_resolved_lazily() -> None:
    spy = Spy()
    factory = CountingFactory(spy)
    handler = FingersCrossedHandler(factory)

    _ = handler.handle(make_record(Level.INFO, "info"))
    assert factory.calls == 0

    _ = handler.handle(make_record(Level.WARNING, "warning"))
    _ = handler.handle(make_record(Level.DEBUG, "after"))

    assert factory.calls == 1
    assert [record.message for record in spy.handled] == ["info", "warning", "after"]
