"""A stand-in sendmail, run with this interpreter, told by its environment what to do.

With ``-bs`` among its arguments it speaks SMTP on its standard streams; otherwise it reads the
message from its standard input, as a sendmail handed the recipients does. Every variable is
optional:

- ``FAKE_SENDMAIL_RECORD`` — a file it writes a JSON object to first: its ``argv`` and ``pid``.
  The input it reads in pipe mode goes to the same path with ``.input`` added.
- ``FAKE_SENDMAIL_MESSAGES`` — a file each message received over SMTP is appended to.
- ``FAKE_SENDMAIL_EXIT`` — the status it exits with once done, ``0`` by default.
- ``FAKE_SENDMAIL_OUTPUT`` — text written to its standard output before it exits.
- ``FAKE_SENDMAIL_STDERR`` — how many bytes it writes to its standard error before it exits.
- ``FAKE_SENDMAIL_HANG`` — ``1``: hang at once, reading nothing, greeting no one.
- ``FAKE_SENDMAIL_READ`` — in pipe mode, how many bytes it reads before it stops reading.
- ``FAKE_SENDMAIL_CLOSE_INPUT`` — ``1``: close its standard input once done reading, and wait a
  moment before exiting, so the writer finds the input closed while the process still runs.
- ``FAKE_SENDMAIL_DIE_AT`` — in SMTP mode, the verb it exits at with status 3, without a reply.
- ``FAKE_SENDMAIL_LINGER`` — ``1``: keep running a minute after the SMTP session ends.
- ``FAKE_SENDMAIL_GARBAGE`` — ``1``: greet with a line that is not SMTP.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

__all__: list[str] = []

_HANG_SECONDS = 3600


def _setting(name: str) -> str:
    return os.environ.get(f"FAKE_SENDMAIL_{name}", "")


def _reply(text: str) -> None:
    _ = sys.stdout.buffer.write(text.encode() + b"\r\n")
    _ = sys.stdout.buffer.flush()


def _receive_message() -> bytes:
    lines: list[bytes] = []
    while (line := sys.stdin.buffer.readline()) not in {b".\r\n", b""}:
        lines.append(line[1:] if line.startswith(b"..") else line)
    return b"".join(lines)


def _converse() -> int | None:
    """Answer one SMTP session; return a status to exit with at once, or ``None`` when done."""
    if _setting("GARBAGE"):
        _reply("this is not smtp")
    _reply("220 localhost ESMTP fake sendmail")
    while line := sys.stdin.buffer.readline():
        verb = line.decode().partition(" ")[0].strip().upper()
        if verb == _setting("DIE_AT"):
            return 3
        match verb:
            case "EHLO":
                _reply("250-localhost\r\n250 8BITMIME")
            case "DATA":
                _reply("354 go ahead")
                message = _receive_message()
                if messages := _setting("MESSAGES"):
                    with Path(messages).open("ab") as file:
                        _ = file.write(message)
                _reply("250 2.0.0 Ok: queued as FAKE42")
            case "QUIT":
                _reply("221 2.0.0 Bye")
                break
            case _:
                _reply("250 2.0.0 Ok")
    if _setting("LINGER"):
        time.sleep(60)
    return None


def _read_input(record: str) -> None:
    limit = _setting("READ")
    data = sys.stdin.buffer.read(int(limit)) if limit else sys.stdin.buffer.read()
    if record:
        _ = Path(f"{record}.input").write_bytes(data)
    if _setting("CLOSE_INPUT"):
        os.close(0)
        time.sleep(0.5)


def main() -> int:
    """Do what the environment says, then exit with ``FAKE_SENDMAIL_EXIT``."""
    if record := _setting("RECORD"):
        # Written whole, then moved in place: a test polling for it never reads half of it.
        written = Path(f"{record}.part")
        _ = written.write_text(json.dumps({"argv": sys.argv, "pid": os.getpid()}))
        _ = written.replace(record)
    if _setting("HANG"):
        time.sleep(_HANG_SECONDS)
    if "-bs" in sys.argv[1:]:
        if (status := _converse()) is not None:
            return status
    else:
        _read_input(record)
    if output := _setting("OUTPUT"):
        _ = sys.stdout.write(output)
    if size := _setting("STDERR"):
        _ = sys.stderr.buffer.write(b"e" * int(size))
    return int(_setting("EXIT") or "0")


if __name__ == "__main__":
    sys.exit(main())
