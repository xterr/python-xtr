from __future__ import annotations

from xtr_http_client import chunk


def test_it_exports_every_kind_of_chunk() -> None:
    assert sorted(chunk.__all__) == [
        "DataChunk",
        "ErrorChunk",
        "FirstChunk",
        "InformationalChunk",
        "LastChunk",
    ]


def test_every_exported_name_is_there() -> None:
    for name in chunk.__all__:
        assert hasattr(chunk, name)
