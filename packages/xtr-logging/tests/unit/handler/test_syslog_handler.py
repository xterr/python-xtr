from __future__ import annotations

import socket

import pytest
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import InvalidOptionError
from xtr_logging.handler.syslog_handler import SyslogHandler


def _bound_receiver() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(2.0)
    return sock


def _send_and_receive(level: Level, facility: str, message: str) -> str:
    sock = _bound_receiver()
    try:
        port = int(sock.getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed
        handler = SyslogHandler("myapp", facility, address=("127.0.0.1", port))
        try:
            _ = handler.handle(make_record(level, message, channel="app"))
        finally:
            handler.close()
        return sock.recv(4096).decode("utf-8")
    finally:
        sock.close()


def test_the_datagram_carries_the_ident_and_the_line() -> None:
    datagram = _send_and_receive(Level.ERROR, "user", "boom")

    assert "myapp: app.ERROR: boom" in datagram


@pytest.mark.parametrize(
    ("level", "facility", "priority"),
    [
        (Level.ERROR, "user", 11),  # 1*8 + 3
        (Level.EMERGENCY, "user", 8),  # 1*8 + 0
        (Level.DEBUG, "user", 15),  # 1*8 + 7
        (Level.ALERT, "user", 9),  # 1*8 + 1
        (Level.NOTICE, "local0", 133),  # 16*8 + 5
    ],
)
def test_the_priority_is_facility_times_eight_plus_severity(
    level: Level, facility: str, priority: int
) -> None:
    datagram = _send_and_receive(level, facility, "msg")

    assert datagram.startswith(f"<{priority}>")


def test_an_unknown_facility_is_refused() -> None:
    with pytest.raises(InvalidOptionError, match="facility"):
        _ = SyslogHandler(facility="nonsense")


def test_a_numeric_facility_is_used_as_given() -> None:
    sock = _bound_receiver()
    try:
        port = int(sock.getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed
        handler = SyslogHandler("myapp", 16, address=("127.0.0.1", port))  # local0
        try:
            _ = handler.handle(make_record(Level.NOTICE, "msg"))
        finally:
            handler.close()
        datagram = sock.recv(4096).decode("utf-8")
    finally:
        sock.close()

    assert datagram.startswith("<133>")  # 16*8 + 5
