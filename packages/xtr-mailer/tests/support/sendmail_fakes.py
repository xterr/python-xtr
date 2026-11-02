"""The stand-in sendmail set up for a test, what it recorded, and whether it is gone."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    import pytest

__all__ = ["FAKE_SENDMAIL", "FakeSendmail", "assert_reaped", "fake_command"]

FAKE_SENDMAIL = Path(__file__).with_name("fake_sendmail.py")


def fake_command(*flags: str) -> str:
    """The command running the stand-in sendmail with this interpreter, given ``flags``."""
    return shlex.join([sys.executable, str(FAKE_SENDMAIL), *flags])


@final
class FakeSendmail:
    """The stand-in sendmail's settings for one test, and what its last run recorded."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, directory: Path, **settings: str) -> None:
        """Set ``settings`` — ``exit="42"`` sets ``FAKE_SENDMAIL_EXIT`` — and a record file."""
        self.record = directory / "sendmail.json"
        self.messages = directory / "messages.eml"
        monkeypatch.setenv("FAKE_SENDMAIL_RECORD", str(self.record))
        monkeypatch.setenv("FAKE_SENDMAIL_MESSAGES", str(self.messages))
        for name, value in settings.items():
            monkeypatch.setenv(f"FAKE_SENDMAIL_{name.upper()}", value)

    @property
    def argv(self) -> list[str]:
        """The arguments it was run with, its script first."""
        return list(json.loads(self.record.read_text())["argv"])  # pyright: ignore[reportAny] — JSON

    @property
    def pid(self) -> int:
        """Its process id."""
        return int(json.loads(self.record.read_text())["pid"])  # pyright: ignore[reportAny] — JSON

    @property
    def input(self) -> bytes:
        """What it read from its standard input, in pipe mode."""
        return Path(f"{self.record}.input").read_bytes()

    async def started(self) -> int:
        """Wait for it to record its process id, and return it."""
        for _ in range(500):
            if self.record.exists():
                return self.pid
            await asyncio.sleep(0.01)
        msg = "the stand-in sendmail never started"
        raise AssertionError(msg)


async def assert_reaped(pid: int) -> None:
    """Assert process ``pid`` is gone within five seconds: not running, nor a zombie.

    A zombie still answers a signal; only a process reaped by its parent is gone for
    ``os.kill``.
    """
    for _ in range(500):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.01)
    msg = f"process {pid} was not reaped"
    raise AssertionError(msg)
