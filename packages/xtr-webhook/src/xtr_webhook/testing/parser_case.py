"""One captured payload, and the events a parser must read out of it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_remote_event import RemoteEvent

__all__ = ["ParserCase"]


@final
@dataclass(frozen=True, slots=True)
class ParserCase:
    """A fixture pair as it was read off disk: what arrived, and what it must become.

    A sender's payloads are the one thing a parser's test cannot invent — they
    come from the sender, captured once and kept. So a case is a record of two
    files rather than something assembled in a test, and it is frozen because
    the files it came from are: a case changed half way through a run would
    leave the failure naming a payload that was never on disk.

    Attributes:
        expected: What the parser must read out of ``payload`` — one event, or
            every event when the capture carried a batch of them.
        id: Where the capture lies under the directory it was found in, as a
            slash-separated relative path, extension and all. It names the case
            in the test report, so a failure says which file to look at.
        payload: The bytes of the capture, exactly as they lie on disk. A
            signature is made over the bytes that arrived, so nothing decodes,
            re-encodes or reformats them on the way here.
    """

    id: str
    payload: bytes
    expected: RemoteEvent | list[RemoteEvent]
