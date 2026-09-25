from __future__ import annotations

import socket

from tests.support.records import make_record
from xtr_logging.processor.hostname_processor import HostnameProcessor


def test_it_adds_the_machines_hostname() -> None:
    processor = HostnameProcessor()

    record = processor(make_record())

    assert record.extra["hostname"] == socket.gethostname()


def test_the_hostname_is_the_same_for_every_record() -> None:
    processor = HostnameProcessor()

    first = processor(make_record())
    second = processor(make_record())

    assert first.extra["hostname"] == second.extra["hostname"]
