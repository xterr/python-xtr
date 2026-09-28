from __future__ import annotations

from xtr_logging.formatter.json_batch_mode import JsonBatchMode


def test_it_offers_an_array_and_one_object_per_line() -> None:
    assert [mode.name for mode in JsonBatchMode] == ["JSON", "NEWLINES"]
