"""An SMTP session with a local sendmail run in SMTP mode, over its standard streams."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from ._sendmail_channel import SendmailChannel
from .smtp_transport import SmtpTransport

if TYPE_CHECKING:
    from typing import Self

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_logging_contracts import LoggerInterface

    from ._smtp_client import SmtpClient

__all__ = ["SendmailSmtpTransport"]


@final
class SendmailSmtpTransport(SmtpTransport):
    """Speaks SMTP to ``sendmail -bs``, started for each session and waited for after it.

    Everything about the session is the SMTP transport's; only where it connects differs.
    A session ended with ``QUIT`` leaves the child to exit on its own; one ended any other way
    — a lost child, a cancelled send — kills it. :meth:`stop` waits for it, killing it once
    the timeout is over.
    """

    def __init__(
        self,
        command: str,
        *,
        event_dispatcher: EventDispatcherInterface | None = None,
        logger: LoggerInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Prepare to run ``command``, which holds ``-bs``; nothing runs until an email is sent.

        Raises:
            InvalidArgumentError: ``command`` does not parse.
        """
        super().__init__(
            port=25, tls=False, event_dispatcher=event_dispatcher, logger=logger, clock=clock
        )
        self._channel: SendmailChannel = SendmailChannel(command, self.get_timeout())

    @override
    def set_timeout(self, seconds: float) -> Self:
        """Wait at most ``seconds`` for each reply, and for the child to exit after a session."""
        _ = super().set_timeout(seconds)
        self._channel.set_timeout(self.get_timeout())
        return self

    @override
    async def stop(self) -> None:
        """End the session with ``QUIT``, and wait for the child, killed once the timeout is over.

        Never raises. Both happen in the session's turn, so a send waiting for it starts a
        child of its own afterwards rather than having it waited for here.
        """
        async with self._lock:
            await self._stop()
            _ = await self._channel.close()

    @override
    def __str__(self) -> str:
        """Name it ``smtp://sendmail``."""
        return "smtp://sendmail"

    @override
    async def _connect(self, client: SmtpClient) -> None:
        _ = await client.connect_socket(await self._channel.open(), self._channel.description)

    @override
    def _disconnect(self, *, clean: bool) -> None:
        self._channel.release(kill=not clean)
