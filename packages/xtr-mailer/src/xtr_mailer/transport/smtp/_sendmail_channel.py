"""A local sendmail run in SMTP mode, with its standard streams on one end of a socket pair."""

from __future__ import annotations

import asyncio
import contextlib
import shlex
import socket
import sys
from typing import final

from xtr_mailer.exception import InvalidArgumentError, LogicError, TransportError
from xtr_mailer.transport._sendmail_process import UNTAKEN_ARGUMENT

__all__ = ["SendmailChannel"]


@final
class SendmailChannel:
    """Runs a sendmail-style command (``-bs``) and gives an SMTP client a socket to it.

    The child reads its standard input and writes its standard output on one end
    of a socket pair, so an SMTP client speaks to it over the other end exactly as
    it would to a server. The command is split like a shell would but never run
    through one, so nothing in it is expanded. What the child writes to its standard
    error goes nowhere: in SMTP mode, its replies say what went wrong.

    A child let go with :meth:`release` is waited for the next time the channel opens or
    closes, killed if it outlives the timeout then.
    """

    __slots__ = ("_arguments", "_child", "_command", "_lock", "_released", "_timeout")

    def __init__(self, command: str, timeout: float = 60.0) -> None:
        """Prepare to run ``command``; ``timeout`` bounds the wait for it to exit.

        Raises:
            InvalidArgumentError: ``command`` is empty or its quoting does not close.
        """
        try:
            arguments = shlex.split(command)
        except ValueError as error:
            raise InvalidArgumentError(
                f'The sendmail command "{command}" is invalid: {error}.'
            ) from None
        if not arguments:
            raise InvalidArgumentError("The sendmail command must not be empty.")
        self._command = command
        self._arguments = arguments
        self._timeout = timeout
        self._child: tuple[asyncio.subprocess.Process, socket.socket] | None = None
        self._released: list[asyncio.subprocess.Process] = []
        # Opening awaits the child's start; without it, two opens at once would both
        # find the channel closed and start a child each, the first never waited for.
        self._lock = asyncio.Lock()

    @property
    def description(self) -> str:
        """What errors call the child: ``process <command>``."""
        return f"process {self._command}"

    def set_timeout(self, seconds: float) -> None:
        """Wait ``seconds`` for a child to exit before killing it."""
        self._timeout = seconds

    async def open(self) -> socket.socket:
        """Start the child and return the socket its standard streams are connected to.

        A child released before is waited for first.

        Raises:
            LogicError: The channel is already open; close it first.
            TransportError: The system is not POSIX, or the command could not be started.
        """
        async with self._lock:
            return await self._open()

    async def close(self) -> int | None:
        """Close the socket, wait for the child and any released, kill what outlives the timeout.

        Call it after the client closed its session. In SMTP mode the child's exit
        status says nothing the session did not, so it is returned, not raised.

        Returns:
            The last child's exit status (negative when it was killed), or ``None`` when
            no child is left to wait for.
        """
        async with self._lock:
            return await self._close()

    def release(self, *, kill: bool) -> None:
        """Close the socket and let the child go, killing it at once when ``kill`` is set.

        Synchronous, so a cancelled session can let go of its child where it cannot
        wait: an unkilled child is expected to exit once it sees its input end — after
        ``QUIT`` — and is waited for the next time the channel opens or closes.
        """
        if self._child is None:
            return
        process, ours = self._child
        self._child = None
        ours.close()
        if kill:
            _kill(process)
        self._released.append(process)

    async def _open(self) -> socket.socket:
        if self._child is not None:
            # A second child would replace the first, which would then never be waited for.
            raise LogicError("The sendmail channel is already open.")
        _ = await self._reap_released()
        if sys.platform == "win32":
            raise TransportError(
                "The sendmail transport needs a POSIX system: it runs sendmail over a socket pair."
            )
        ours, theirs = socket.socketpair()
        try:
            process = await asyncio.create_subprocess_exec(
                *self._arguments,
                stdin=theirs.fileno(),
                stdout=theirs.fileno(),
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as error:
            ours.close()
            raise TransportError(f"Process could not be started: {error}") from None
        except ValueError:  # A NUL, or a character the file system encoding has no bytes for.
            ours.close()
            raise TransportError(UNTAKEN_ARGUMENT) from None
        except BaseException:
            ours.close()  # Cancelled while it starts: no child will ever answer on it.
            raise
        finally:
            # The child holds its own copy; keeping ours would hide its exit from the client.
            theirs.close()
        self._child = (process, ours)
        return ours

    async def _close(self) -> int | None:
        self.release(kill=False)
        return await self._reap_released()

    async def _reap_released(self) -> int | None:
        """Wait for every released child, killing one that outlives the timeout."""
        exit_code = None
        while self._released:
            exit_code = await self._reap(self._released[0])
            _ = self._released.pop(0)
        return exit_code

    async def _reap(self, process: asyncio.subprocess.Process) -> int:
        try:
            return await asyncio.wait_for(process.wait(), self._timeout)
        except TimeoutError:
            _kill(process)
            return await process.wait()
        except BaseException:
            _kill(process)  # Cancelled while waiting: the event loop reaps it once it is dead.
            raise


def _kill(process: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):  # It exited already.
        process.kill()
