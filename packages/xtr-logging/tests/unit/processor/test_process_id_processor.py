from __future__ import annotations

import os

from tests.support.records import make_record
from xtr_logging.processor.process_id_processor import ProcessIdProcessor


def test_it_adds_the_current_process_id() -> None:
    processor = ProcessIdProcessor()

    record = processor(make_record())

    assert record.extra["process_id"] == os.getpid()
