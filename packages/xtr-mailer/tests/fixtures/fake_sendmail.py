"""A stand-in sendmail that speaks SMTP on its standard streams, as ``sendmail -bs`` does.

Run as ``python fake_sendmail.py -bs [--record FILE] [--die-at VERB] [--linger]``:
``--record`` appends every message received to ``FILE``, ``--die-at`` exits with
status 3 when the client sends ``VERB``, and ``--linger`` keeps the process alive
after the session ends, as a sendmail that does not exit would.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

__all__: list[str] = []


def _reply(text: str) -> None:
    _ = sys.stdout.buffer.write(text.encode() + b"\r\n")
    _ = sys.stdout.buffer.flush()


def _option(arguments: list[str], name: str) -> str | None:
    return arguments[arguments.index(name) + 1] if name in arguments else None


def _receive_message() -> bytes:
    lines: list[bytes] = []
    while (line := sys.stdin.buffer.readline()) not in {b".\r\n", b""}:
        lines.append(line[1:] if line.startswith(b"..") else line)
    return b"".join(lines)


def main() -> int:
    """Answer one SMTP session, then exit."""
    arguments = sys.argv[1:]
    if "-bs" not in arguments:
        return 64
    record_path = _option(arguments, "--record")
    record = Path(record_path) if record_path is not None else None
    die_at = _option(arguments, "--die-at")
    linger = "--linger" in arguments

    _reply("220 localhost ESMTP fake sendmail")
    while line := sys.stdin.buffer.readline():
        verb = line.decode().partition(" ")[0].strip().upper()
        if verb == die_at:
            return 3
        match verb:
            case "EHLO":
                _reply("250-localhost\r\n250 8BITMIME")
            case "DATA":
                _reply("354 go ahead")
                message = _receive_message()
                if record is not None:
                    with record.open("ab") as file:
                        _ = file.write(message)
                _reply("250 2.0.0 Ok: queued as FAKE42")
            case "QUIT":
                _reply("221 2.0.0 Bye")
                break
            case _:
                _reply("250 2.0.0 Ok")
    if linger:
        time.sleep(60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
