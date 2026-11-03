from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from tests.support.sendmail_fakes import FAKE_SENDMAIL, FakeSendmail, assert_reaped
from xtr_mailer import TransportError
from xtr_mailer.transport._sendmail_process import pipe_to_sendmail

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_ARGUMENTS = [sys.executable, str(FAKE_SENDMAIL), "-t"]


async def test_the_message_is_written_to_the_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)

    await pipe_to_sendmail(_ARGUMENTS, b"hello\n", 5)

    assert fake.input == b"hello\n"
    await assert_reaped(fake.pid)


async def test_what_the_process_writes_on_success_is_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path, output="queued", stderr="10")

    await pipe_to_sendmail(_ARGUMENTS, b"x", 5)


async def test_its_output_and_errors_both_explain_a_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path, exit="75", output="out:", stderr="3")

    with pytest.raises(TransportError) as caught:
        await pipe_to_sendmail(_ARGUMENTS, b"x", 5)

    assert str(caught.value) == "Process failed with exit code 75: out:eee"


async def test_a_process_still_running_at_the_time_limit_is_killed_and_reaped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, hang="1")

    with pytest.raises(TransportError, match=r"did not finish within 0\.2 seconds"):
        await pipe_to_sendmail(_ARGUMENTS, b"x", 0.2)

    await assert_reaped(fake.pid)


async def test_the_reason_a_process_cannot_start_is_cut_short(tmp_path: Path) -> None:
    with pytest.raises(TransportError) as caught:
        await pipe_to_sendmail([str(tmp_path / ("x" * 250))], b"x", 5)

    assert str(caught.value).startswith("Process could not be started: ")
    assert len(str(caught.value)) < 260


@pytest.mark.parametrize(
    "argument",
    [pytest.param("to\x00@example.com", id="nul"), pytest.param("to\ud800@x.org", id="surrogate")],
)
async def test_an_argument_the_system_cannot_take_fails_without_showing_it(argument: str) -> None:
    with pytest.raises(TransportError) as caught:
        await pipe_to_sendmail([*_ARGUMENTS, "--", argument], b"x", 5)

    assert str(caught.value) == (
        "Process could not be started: an argument holds a character the system cannot take."
    )
    assert caught.value.__cause__ is None
