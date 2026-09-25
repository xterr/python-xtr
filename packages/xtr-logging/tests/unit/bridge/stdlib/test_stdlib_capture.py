"""A capture owns the standard library's output: every record is written exactly once."""

from __future__ import annotations

import logging
import logging.config
from uuid import uuid4

import pytest
from xtr_logging_contracts import Level

from tests.support.stdlib import Collector
from xtr_logging import Logger, TestHandler
from xtr_logging.bridge.stdlib import StdlibCapture

pytestmark = pytest.mark.usefixtures("stdlib_logging")


def _name() -> str:
    return f"lib{uuid4().hex}"


def test_a_root_handler_from_basic_config_no_longer_prints_what_is_captured() -> None:
    console = Collector()
    logging.getLogger().addHandler(console)
    channel = TestHandler()

    with StdlibCapture(Logger("app", [channel])):
        logging.getLogger(_name()).warning("disk low")

    assert [r.message for r in channel.records] == ["disk low"]
    assert console.records == []


def test_a_libraries_own_handler_is_moved_aside_while_captured() -> None:
    name = _name()
    own = Collector()
    logging.getLogger(name).addHandler(own)
    channel = TestHandler()

    with StdlibCapture(Logger("app", [channel])):
        logging.getLogger(name).error("request failed")

    assert len(channel.records) == 1
    assert own.records == []


def test_a_logger_that_did_not_propagate_is_captured_once() -> None:
    name = _name()
    own = Collector()
    library = logging.getLogger(name)
    library.addHandler(own)
    library.propagate = False
    channel = TestHandler()

    with StdlibCapture(Logger("app", [channel])):
        library.warning("server started")

    assert len(channel.records) == 1
    assert own.records == []


def test_a_disabled_logger_is_heard_while_captured() -> None:
    name = _name()
    logging.getLogger(name).disabled = True
    channel = TestHandler()

    with StdlibCapture(Logger("app", [channel])):
        logging.getLogger(name).warning("was silenced")

    assert len(channel.records) == 1


def test_a_handler_attached_to_a_library_after_installation_prints_nothing() -> None:
    name = _name()
    channel = TestHandler()
    late = Collector()

    with StdlibCapture(Logger("app", [channel])):
        logging.getLogger(name).addHandler(late)
        logging.getLogger(name).warning("first")
        logging.getLogger(name).warning("second")

    assert [r.message for r in channel.records] == ["first", "second"]
    assert late.records == []


def test_a_root_handler_attached_after_installation_prints_nothing() -> None:
    channel = TestHandler()
    late = Collector()

    with StdlibCapture(Logger("app", [channel])):
        logging.getLogger().addHandler(late)
        logging.getLogger(_name()).warning("first")

    assert len(channel.records) == 1
    assert late.records == []


def test_basic_config_after_installation_prints_nothing() -> None:
    channel = TestHandler()

    with StdlibCapture(Logger("app", [channel])):
        logging.basicConfig(force=True)
        logging.getLogger(_name()).warning("first")

    assert len(channel.records) == 1


def test_dict_config_after_installation_neither_prints_nor_unhooks_the_capture() -> None:
    name = _name()
    channel = TestHandler()

    with StdlibCapture(Logger("app", [channel])):
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": True,
                "handlers": {"console": {"class": "logging.StreamHandler"}},
                "root": {"handlers": ["console"], "level": "INFO"},
                "loggers": {name: {"handlers": ["console"], "propagate": False}},
            },
        )
        logging.getLogger(name).warning("from the library")
        logging.getLogger(_name()).warning("from elsewhere")

    assert [r.message for r in channel.records] == ["from the library", "from elsewhere"]


def test_a_logger_told_to_stop_propagating_after_installation_is_captured_once() -> None:
    name = _name()
    channel = TestHandler()

    with StdlibCapture(Logger("app", [channel])):
        logging.getLogger(name).propagate = False
        logging.getLogger(name).warning("first")
        logging.getLogger(name).warning("second")

    assert [r.message for r in channel.records] == ["first", "second"]


def test_a_handler_attached_during_the_capture_is_attached_on_release() -> None:
    name = _name()
    late = Collector()

    with StdlibCapture(Logger("app")):
        logging.getLogger(name).addHandler(late)

    assert logging.getLogger(name).handlers == [late]


def test_release_gives_the_standard_library_its_methods_and_last_resort_back() -> None:
    add, remove, last_resort = (
        logging.Logger.addHandler,
        logging.Logger.removeHandler,
        logging.lastResort,
    )

    with StdlibCapture(Logger("app")):
        assert logging.Logger.addHandler is not add

    assert (logging.Logger.addHandler, logging.Logger.removeHandler) == (add, remove)
    assert logging.lastResort is last_resort


def test_the_most_recent_of_nested_captures_owns_the_output() -> None:
    outer, inner = TestHandler(), TestHandler()

    with StdlibCapture(Logger("outer", [outer])), StdlibCapture(Logger("inner", [inner])):
        logging.getLogger(_name()).warning("x")

    assert (len(outer.records), len(inner.records)) == (0, 1)


def test_release_gives_every_logger_back_as_it_was() -> None:
    name = _name()
    own = Collector()
    library = logging.getLogger(name)
    library.addHandler(own)
    library.setLevel(logging.ERROR)
    library.propagate = False
    root_handlers = list(logging.getLogger().handlers)
    root_level = logging.getLogger().level

    with StdlibCapture(Logger("app"), levels={name: "debug"}):
        pass

    assert library.handlers == [own]
    assert (library.level, library.propagate) == (logging.ERROR, False)
    assert logging.getLogger().handlers == root_handlers
    assert logging.getLogger().level == root_level


def test_the_root_level_is_the_threshold_for_loggers_without_their_own() -> None:
    channel = TestHandler()

    with StdlibCapture(Logger("app", [channel]), level=Level.WARNING):
        logging.getLogger(_name()).info("chatter")
        logging.getLogger(_name()).warning("worth hearing")

    assert [r.message for r in channel.records] == ["worth hearing"]


def test_a_logger_given_its_own_level_says_more() -> None:
    name = _name()
    channel = TestHandler()

    with StdlibCapture(Logger("app", [channel]), levels={name: "info"}):
        logging.getLogger(f"{name}.client").info("GET /health 200")

    assert [r.message for r in channel.records] == ["GET /health 200"]


def test_a_route_sends_a_logger_and_its_children_to_their_own_channel() -> None:
    name = _name()
    handler = TestHandler()
    app = Logger("app", [handler])

    with StdlibCapture(app, routes={name: app.with_name("db")}):
        logging.getLogger(f"{name}.engine").warning("slow query")
        logging.getLogger(_name()).warning("elsewhere")

    assert [(r.channel, r.message) for r in handler.records] == [
        ("db", "slow query"),
        ("app", "elsewhere"),
    ]


def test_installing_twice_changes_nothing() -> None:
    channel = TestHandler()
    capture = StdlibCapture(Logger("app", [channel]))

    with capture:
        capture.install()
        logging.getLogger(_name()).warning("once")

    assert len(channel.records) == 1
    assert not capture.installed
