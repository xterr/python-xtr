"""A raw message: bytes handed over as they are, from a string, bytes, chunks or a file.

Upstream's serialization case is xtr-mailer's: it carries a queued message as plain data, and
ports the case through its queue. Its destructor case has no counterpart: whoever opened a file
closes it. A generator read to its end is kept, so the message can be sent again; upstream
raised on a second read instead.
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from copy import copy
from typing import TYPE_CHECKING, BinaryIO, Final

import pytest
from typing_extensions import override

from xtr_mime import RawMessage
from xtr_mime.exception import InvalidArgumentError, LogicError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

CLOSED: Final = "Unable to send the email as its generator is already closed."


def _generator() -> Iterator[bytes]:
    yield b"some"
    yield b" "
    yield b"string"


class _Chunks:
    """An iterable that is not a sequence, read afresh each time."""

    def __iter__(self) -> Iterator[bytes]:
        return iter([b"some", b" ", b"string"])


Source = str | bytes | BinaryIO | Iterable[bytes]

MESSAGES: Final[list[tuple[str, Callable[[], Source]]]] = [
    ("string", lambda: "some string"),
    ("bytes", lambda: b"some string"),
    ("iterable", _Chunks),
    ("list", lambda: [b"some", b" ", b"string"]),
    ("generator", _generator),
    ("file", lambda: io.BytesIO(b"some string")),
]


MAKERS: Final = [make for _, make in MESSAGES]
LABELS: Final = [label for label, _ in MESSAGES]


@pytest.mark.parametrize("make", MAKERS, ids=LABELS)
def test_to_string(make: Callable[[], Source]) -> None:
    message = RawMessage(make())

    assert message.to_string() == "some string"
    assert b"".join(message.to_iterable()) == b"some string"
    # Both can be called more than once.
    assert message.to_string() == "some string"
    assert b"".join(message.to_iterable()) == b"some string"


@pytest.mark.parametrize("make", MAKERS, ids=LABELS)
def test_to_iterable(make: Callable[[], Source]) -> None:
    message = RawMessage(make())

    assert b"".join(message.to_iterable()) == b"some string"
    assert b"".join(message.to_iterable()) == b"some string"


def test_a_generator_read_to_its_end_is_kept_for_the_next_read() -> None:
    message = RawMessage(_generator())
    assert list(message.to_iterable()) == [b"some", b" ", b"string"]

    assert message.to_string() == "some string"
    assert b"".join(message.to_iterable()) == b"some string"


def test_a_generator_left_half_read_cannot_be_read_again() -> None:
    message = RawMessage(_generator())
    chunks = message.to_iterable()
    assert next(chunks) == b"some"
    chunks.close()

    with pytest.raises(LogicError, match=f"^{CLOSED}$"):
        _ = list(message.to_iterable())


def test_to_string_refuses_a_generator_left_half_read() -> None:
    message = RawMessage(_generator())
    chunks = message.to_iterable()
    _ = next(chunks)
    chunks.close()

    with pytest.raises(LogicError, match=f"^{CLOSED}$"):
        _ = message.to_string()


def test_a_generator_read_to_its_end_through_a_copy_is_kept_for_the_original() -> None:
    message = RawMessage(_generator())
    assert b"".join(copy(message).to_iterable()) == b"some string"

    assert b"".join(message.to_iterable()) == b"some string"
    assert copy(message).to_string() == "some string"


def test_a_generator_left_half_read_through_a_copy_cannot_be_read_by_the_original() -> None:
    message = RawMessage(_generator())
    chunks = copy(message).to_iterable()
    _ = next(chunks)
    chunks.close()

    with pytest.raises(LogicError, match=f"^{CLOSED}$"):
        _ = b"".join(message.to_iterable())


def test_a_generator_still_being_read_through_a_copy_cannot_be_read_by_another() -> None:
    message = RawMessage(_generator())
    chunks = copy(message).to_iterable()
    _ = next(chunks)

    with pytest.raises(LogicError, match=f"^{CLOSED}$"):
        _ = b"".join(copy(message).to_iterable())


def test_to_iterable_on_a_file_rewinds_and_yields_lines() -> None:
    handle = io.BytesIO()
    _ = handle.write(b"line1\nline2\nline3\n")

    message = RawMessage(handle)

    assert list(message.to_iterable()) == [b"line1\n", b"line2\n", b"line3\n"]


def test_to_iterable_on_a_file_yields_a_final_line_without_a_line_break() -> None:
    handle = io.BytesIO()
    _ = handle.write(b"line1\n0")

    message = RawMessage(handle)

    assert b"".join(message.to_iterable()) == b"line1\n0"


def test_to_string_reads_a_file_from_its_start() -> None:
    handle = io.BytesIO()
    _ = handle.write(b"some string")

    assert RawMessage(handle).to_string() == "some string"


class _Pipe(io.BytesIO):
    """A file that cannot seek, as a pipe."""

    @override
    def seekable(self) -> bool:
        return False


def test_to_iterable_reads_a_file_that_cannot_seek_from_where_it_is() -> None:
    message = RawMessage(_Pipe(b"line1\nline2\n"))

    assert list(message.to_iterable()) == [b"line1\n", b"line2\n"]


def test_bytes_that_are_not_utf8_survive_to_string_as_surrogates() -> None:
    message = RawMessage(b"caf\xe9")

    assert message.to_string().encode("utf-8", "surrogateescape") == b"caf\xe9"


def test_a_string_is_sent_as_utf8() -> None:
    assert b"".join(RawMessage("café").to_iterable()) == "café".encode()


def test_a_string_holding_bytes_as_surrogates_is_sent_as_those_bytes() -> None:
    message = RawMessage("caf\udce9")

    assert b"".join(message.to_iterable()) == b"caf\xe9"
    assert message.to_string() == "caf\udce9"


UNWRITABLE: Final = "^The message cannot be written in UTF-8: .*'\\\\ud800'"


def test_to_iterable_refuses_a_string_utf8_cannot_hold() -> None:
    message = RawMessage("x\ud800\r\n")

    with pytest.raises(InvalidArgumentError, match=UNWRITABLE) as caught:
        _ = b"".join(message.to_iterable())

    _ = str(caught.value).encode("utf-8")  # the surrogate is shown escaped


def test_to_string_refuses_a_string_utf8_cannot_hold() -> None:
    # What to_string returns is the text of what would be sent: a message that cannot be sent
    # has none.
    message = RawMessage("x\ud800")

    with pytest.raises(InvalidArgumentError, match=UNWRITABLE):
        _ = message.to_string()


def test_ensure_validity_accepts_any_raw_message() -> None:
    RawMessage("").ensure_validity()
