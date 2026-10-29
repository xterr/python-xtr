"""The stand-in sendmail answers one SMTP session on its standard streams."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FAKE_SENDMAIL = Path(__file__).parent.parent / "fixtures" / "fake_sendmail.py"


def _session(*arguments: str, script: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 - runs the fixture with this interpreter
        [sys.executable, str(FAKE_SENDMAIL), "-bs", *arguments],
        input=script,
        capture_output=True,
        check=False,
        timeout=10,
    )


def test_it_delivers_a_message_and_quits(tmp_path: Path) -> None:
    record = tmp_path / "mail.eml"

    result = _session(
        "--record",
        str(record),
        script=b"EHLO me\r\nMAIL FROM:<a@example.com>\r\nDATA\r\n..x\r\n.\r\nQUIT\r\n",
    )

    assert result.returncode == 0
    assert result.stdout.split(b"\r\n")[-3:] == [
        b"250 2.0.0 Ok: queued as FAKE42",
        b"221 2.0.0 Bye",
        b"",
    ]
    assert record.read_bytes() == b".x\r\n"


def test_it_exits_without_a_reply_at_the_verb_it_dies_at() -> None:
    result = _session("--die-at", "MAIL", script=b"EHLO me\r\nMAIL FROM:<a@example.com>\r\n")

    assert result.returncode == 3
    assert result.stdout.endswith(b"250 8BITMIME\r\n")


def test_it_ends_when_its_input_does() -> None:
    result = _session(script=b"NOOP\r\n")

    assert result.returncode == 0
    assert result.stdout.endswith(b"250 2.0.0 Ok\r\n")
