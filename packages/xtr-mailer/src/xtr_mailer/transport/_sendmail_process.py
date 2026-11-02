"""One sendmail run that reads an email from its standard input, and what its exit means."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Final

from xtr_mailer._error_text import shown
from xtr_mailer.exception import TransportError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["pipe_to_sendmail"]

#: The bytes of each output stream kept for an error; the rest is read and dropped.
_KEPT_BYTES: Final = 4096
#: The characters of that output an error shows.
_SHOWN_CHARACTERS: Final = 1000
_CHUNK: Final = 65536


async def pipe_to_sendmail(arguments: Sequence[str], message: bytes, time_limit: float) -> None:
    """Run ``arguments``, write ``message`` to its input, and wait for it to exit with ``0``.

    Its output is read as it comes, so a process writing much never blocks on a full pipe;
    an error shows the start of it, escaped. A process still running after ``time_limit``
    seconds, or when the send is cancelled, is killed and waited for.

    Raises:
        TransportError: The process could not be started, exited with another status, did
            not finish in time, or closed its input before reading the whole message.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *arguments,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as error:
        raise TransportError(f"Process could not be started: {shown(str(error), 200)}") from None
    try:
        async with asyncio.timeout(time_limit):
            closed_early, output, errors = await asyncio.gather(
                _write(process, message), _read(process.stdout), _read(process.stderr)
            )
            exit_code = await process.wait()
    except TimeoutError:
        await _reap(process)
        raise TransportError(f"Process did not finish within {time_limit:g} seconds.") from None
    except BaseException:
        await _reap(process)  # Cancelled: the process must not outlive the send.
        raise
    if exit_code != 0:
        text = (output + errors).decode("utf-8", "replace").strip()
        raise TransportError(
            f"Process failed with exit code {exit_code}: {shown(text, _SHOWN_CHARACTERS)}"
        )
    if closed_early:
        raise TransportError("Process closed its input before the whole message was written.")


async def _write(process: asyncio.subprocess.Process, message: bytes) -> bool:
    """Write ``message`` and close the input; ``True`` when the process closed it first."""
    stdin = process.stdin
    if stdin is None:  # pragma: no cover - always a pipe, as it was asked for
        return True
    try:
        stdin.write(message)
        await stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        return True
    finally:
        stdin.close()
    return False


async def _read(stream: asyncio.StreamReader | None) -> bytes:
    """Read ``stream`` to its end, keeping its first bytes."""
    kept = bytearray()
    while stream is not None and (chunk := await stream.read(_CHUNK)):
        kept += chunk[: max(_KEPT_BYTES - len(kept), 0)]
    return bytes(kept)


async def _reap(process: asyncio.subprocess.Process) -> None:
    """Kill ``process`` and wait for it, the wait shielded from a cancellation still pending."""
    with contextlib.suppress(ProcessLookupError):  # It exited already.
        process.kill()
    _ = await asyncio.shield(process.wait())
