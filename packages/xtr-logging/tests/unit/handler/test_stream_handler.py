from __future__ import annotations

import io
import stat
from typing import TYPE_CHECKING

from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging.formatter.json_batch_mode import JsonBatchMode
from xtr_logging.formatter.json_formatter import JsonFormatter
from xtr_logging.handler.stream_handler import StreamHandler

if TYPE_CHECKING:
    from pathlib import Path


def test_it_writes_the_formatted_line_to_a_given_stream() -> None:
    stream = io.StringIO()
    handler = StreamHandler(stream)

    _ = handler.handle(make_record(Level.WARNING, "low disk", channel="ops"))

    assert "ops.WARNING: low disk" in stream.getvalue()


def test_a_given_stream_is_exposed_and_left_open_by_close() -> None:
    stream = io.StringIO()
    handler = StreamHandler(stream)

    handler.close()

    assert handler.stream is stream
    assert handler.url is None
    assert not stream.closed


def test_a_path_is_untouched_until_the_first_record(tmp_path: Path) -> None:
    target = tmp_path / "logs" / "app.log"
    handler = StreamHandler(target)

    assert handler.url == str(target)
    assert handler.stream is None
    assert not target.exists()


def test_the_first_record_opens_the_file_and_makes_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "app.log"
    handler = StreamHandler(target)

    _ = handler.handle(make_record(message="hello"))
    handler.close()

    assert "app.INFO: hello" in target.read_text(encoding="utf-8")


def test_a_created_file_gets_the_requested_permission(tmp_path: Path) -> None:
    target = tmp_path / "app.log"
    handler = StreamHandler(target, file_permission=0o600)

    _ = handler.handle(make_record(message="hi"))
    handler.close()

    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_close_then_write_reopens_the_file(tmp_path: Path) -> None:
    target = tmp_path / "app.log"
    handler = StreamHandler(target)

    _ = handler.handle(make_record(message="first"))
    handler.close()
    assert handler.stream is None
    _ = handler.handle(make_record(message="second"))
    handler.close()

    text = target.read_text(encoding="utf-8")
    assert "first" in text
    assert "second" in text


def test_truncate_mode_starts_the_file_fresh(tmp_path: Path) -> None:
    target = tmp_path / "app.log"
    _ = target.write_text("stale\n", encoding="utf-8")
    handler = StreamHandler(target, mode="w")

    _ = handler.handle(make_record(message="fresh"))
    handler.close()

    text = target.read_text(encoding="utf-8")
    assert "stale" not in text
    assert "fresh" in text


def test_text_its_encoding_cannot_hold_is_escaped_rather_than_failing(tmp_path: Path) -> None:
    handler = StreamHandler(tmp_path / "app.log", encoding="ascii")

    _ = handler.handle(make_record(message="café"))
    handler.close()

    assert "caf\\xe9" in (tmp_path / "app.log").read_text(encoding="ascii")


def test_a_batch_is_written_as_the_formatter_renders_a_batch() -> None:
    stream = io.StringIO()
    handler = StreamHandler(stream)
    handler.formatter = JsonFormatter(JsonBatchMode.JSON)

    handler.handle_batch([make_record(message="a"), make_record(message="b")])

    assert stream.getvalue().startswith('[{"message":"a"')
    assert stream.getvalue().count("\n") == 1


def test_a_batch_leaves_out_records_below_the_level() -> None:
    stream = io.StringIO()
    handler = StreamHandler(stream, Level.WARNING)

    handler.handle_batch([make_record(Level.INFO, "quiet"), make_record(Level.ERROR, "loud")])

    assert "quiet" not in stream.getvalue()
    assert "loud" in stream.getvalue()
