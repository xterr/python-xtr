"""The stand-in sendmail does what its environment says, in SMTP mode and in pipe mode."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

from tests.support.sendmail_fakes import FAKE_SENDMAIL, FakeSendmail

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _run(*flags: str, script: bytes, **settings: str) -> subprocess.CompletedProcess[bytes]:
    environment = {**os.environ, **{f"FAKE_SENDMAIL_{k.upper()}": v for k, v in settings.items()}}
    return subprocess.run(  # noqa: S603 - runs the stand-in with this interpreter
        [sys.executable, str(FAKE_SENDMAIL), *flags],
        input=script,
        capture_output=True,
        check=False,
        timeout=10,
        env=environment,
    )


def test_it_delivers_a_message_and_quits(tmp_path: Path) -> None:
    messages = tmp_path / "mail.eml"

    result = _run(
        "-bs",
        script=b"EHLO me\r\nMAIL FROM:<a@example.com>\r\nDATA\r\n..x\r\n.\r\nQUIT\r\n",
        messages=str(messages),
    )

    assert result.returncode == 0
    assert result.stdout.split(b"\r\n")[-3:] == [
        b"250 2.0.0 Ok: queued as FAKE42",
        b"221 2.0.0 Bye",
        b"",
    ]
    assert messages.read_bytes() == b".x\r\n"


def test_it_exits_without_a_reply_at_the_verb_it_dies_at() -> None:
    result = _run("-bs", script=b"EHLO me\r\nMAIL FROM:<a@example.com>\r\n", die_at="MAIL")

    assert result.returncode == 3
    assert result.stdout.endswith(b"250 8BITMIME\r\n")


def test_it_ends_when_its_input_does() -> None:
    result = _run("-bs", script=b"NOOP\r\n")

    assert result.returncode == 0
    assert result.stdout.endswith(b"250 2.0.0 Ok\r\n")


def test_it_greets_with_garbage_when_told_to() -> None:
    result = _run("-bs", script=b"", garbage="1")

    assert result.stdout.startswith(b"this is not smtp\r\n")


def test_it_records_its_arguments_and_its_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)

    result = _run("-fa@example.com", "--", "b@example.com", script=b"hi\n")

    assert result.returncode == 0
    assert fake.argv == [str(FAKE_SENDMAIL), "-fa@example.com", "--", "b@example.com"]
    assert fake.pid > 0
    assert fake.input == b"hi\n"


def test_it_fails_as_told() -> None:
    result = _run("-t", script=b"hi\n", exit="42", output="Sending failed", stderr="5")

    assert result.returncode == 42
    assert result.stdout == b"Sending failed"
    assert result.stderr == b"eeeee"


def test_it_reads_only_as_much_as_told(tmp_path: Path) -> None:
    record = tmp_path / "record.json"

    _ = _run("-t", script=b"0123456789", read="4", record=str(record))

    assert (tmp_path / "record.json.input").read_bytes() == b"0123"
