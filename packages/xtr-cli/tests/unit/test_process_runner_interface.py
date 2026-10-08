from __future__ import annotations

from pathlib import Path

from tests.support import RecordingRunner
from xtr_cli import ProcessRunnerInterface


def test_the_recording_fake_honours_the_contract() -> None:
    runner = RecordingRunner((5,))

    assert isinstance(runner, ProcessRunnerInterface)
    assert runner.run(("uv", "add"), Path("shop")) == 5
    assert runner.run(("git", "init"), Path("shop")) == 0
    assert runner.calls == [(("uv", "add"), Path("shop")), (("git", "init"), Path("shop"))]
