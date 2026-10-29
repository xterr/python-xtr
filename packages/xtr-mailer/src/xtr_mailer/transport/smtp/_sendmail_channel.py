"""A local sendmail run in SMTP mode, with its standard streams on one end of a socket pair."""

from __future__ import annotations

import asyncio
import shlex
import socket
import sys
from typing import final

from xtr_mailer.exception import InvalidArgumentError, LogicError, TransportError

__all__ = ["SendmailChannel"]


@final
class SendmailChannel:
    """Runs a sendmail-style command (``-bs``) and gives an SMTP client a socket to it.

    The child reads its standard input and writes its standard output on one end
    of a socket pair, so an SMTP client speaks to it over the other end exactly as
    it would to a server. The command is split like a shell would but never run
    through one, so nothing in it is expanded.
    """

    __slots__ = ("_arguments", "_child", "_command", "_lock", "_timeout")

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
        # Opening awaits the child's start; without it, two opens at once would both
        # find the channel closed and start a child each, the first never waited for.
        self._lock = asyncio.Lock()

    @property
    def description(self) -> str:
        """What errors call the child: ``process <command>``."""
        return f"process {self._command}"

    async def open(self) -> socket.socket:
        """Start the child and return the socket its standard streams are connected to.

        Raises:
            LogicError: The channel is already open; close it first.
            TransportError: The system is not POSIX, or the command could not be started.
        """
        async with self._lock:
            return await self._open()

    async def close(self) -> int | None:
        """Close the socket and wait for the child, killing it if it outlives the timeout.

        Call it after the client closed its session. In SMTP mode the child's exit
        status says nothing the session did not, so it is returned, not raised.

        Returns:
            The child's exit status (negative when it was killed), or ``None`` when
            the channel was never opened.
        """
        async with self._lock:
            return await self._close()

    async def _open(self) -> socket.socket:
        if self._child is not None:
            # A second child would replace the first, which would then never be waited for.
            raise LogicError("The sendmail channel is already open.")
        if sys.platform == "win32":
            raise TransportError(
                "The sendmail transport needs a POSIX system: it runs sendmail over a socket pair."
            )
        ours, theirs = socket.socketpair()
        try:
            process = await asyncio.create_subprocess_exec(
                *self._arguments, stdin=theirs.fileno(), stdout=theirs.fileno()
            )
        except OSError as error:
            ours.close()
            raise TransportError(f"Process could not be started: {error}") from None
        finally:
            # The child holds its own copy; keeping ours would hide its exit from the client.
            theirs.close()
        self._child = (process, ours)
        return ours

    async def _close(self) -> int | None:
        if self._child is None:
            return None
        process, ours = self._child
        self._child = None
        ours.close()
        try:
            return await asyncio.wait_for(process.wait(), self._timeout)
        except TimeoutError:
            process.kill()
            return await process.wait()
