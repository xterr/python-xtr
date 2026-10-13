"""The head of a response, built one line at a time as it arrives."""

from __future__ import annotations

import re
from typing import Final, final

__all__ = ["ResponseHead"]

# A head is only a head when the line names a status in one of the five
# classes; anything else starting with the protocol is a line the server sent
# that this does not understand, and dropping the headers for it would lose a
# head that was perfectly good.
_STATUS_LINE: Final = re.compile(
    r"^HTTP/(?P<version>\d+(?:\.\d+)?) (?P<code>[1-5]\d\d)(?: (?P<reason>.*))?$",
)


@final
class ResponseHead:
    """What a transfer learned before the body: a status, and the headers under it.

    Fed the raw lines in the order they arrive, which is the only form every
    transfer agrees on. Two shapes mean something — a status line, and a
    ``Name: value`` header — and a status line arriving again starts the head
    over, because that is a *new* head: a redirect that was followed, or a 1xx
    the server sent ahead of the real status. Dropping what was collected is
    the whole point; otherwise a 301's ``Location`` would be read as belonging
    to the 200 that followed it.

    Every line is also kept in :attr:`recorded`, whatever its shape, because
    that is what a caller asking the transfer for its response headers gets:
    the head as it came off the wire, not this reading of it.

    Headers are keyed by lowered name, since that is the only way two
    spellings of one header can be told to be the same one, and a name maps to
    the list of its values, since a header sent twice stays twice.
    """

    __slots__ = ("headers", "protocol_version", "reason_phrase", "recorded", "status_code")

    def __init__(self) -> None:
        """Start empty, on the version a server that names none is speaking."""
        self.protocol_version = "1.1"
        self.status_code = 0
        self.reason_phrase = ""
        self.headers: dict[str, list[str]] = {}
        self.recorded: list[str] = []

    def add_line(self, line: str) -> None:
        """Take one raw line of the head.

        Args:
            line: The line as it arrived, with or without the break that ended
                it; what is recorded is the line without it, so a caller
                reading the head back is not handed the framing.
        """
        line = line.rstrip("\r\n")

        status = _STATUS_LINE.match(line)
        if status is not None:
            self.protocol_version = status["version"]
            self.status_code = int(status["code"])
            self.reason_phrase = status["reason"] or ""
            self.headers.clear()
        elif ":" in line:
            name, _, value = line.partition(":")
            self.headers.setdefault(name.lower(), []).append(value.lstrip())

        self.recorded.append(line)

    def copy(self) -> ResponseHead:
        """Return a head that starts out the same and can then diverge.

        What a response's ``with_*`` methods are built on: the copy they hand
        back must be able to carry a changed status or an added header without
        the response it came from seeing it, so the lists are copied too
        rather than shared.
        """
        copied = ResponseHead()
        copied.protocol_version = self.protocol_version
        copied.status_code = self.status_code
        copied.reason_phrase = self.reason_phrase
        copied.headers = {name: list(values) for name, values in self.headers.items()}
        copied.recorded = list(self.recorded)
        return copied
