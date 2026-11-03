"""``mailer:test``: send a plain email through a transport, to see that it works."""

from __future__ import annotations

from typing import Annotated, final

from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_mime import Email, MimeError

from xtr_mailer.exception import MailerError
from xtr_mailer.transport.transport_interface import (
    TransportInterface,  # noqa: TC001 -- a container reads the constructor's annotations at runtime
)

__all__ = ["MailerTestCommand"]


@as_command("mailer:test")
@final
class MailerTestCommand:
    """Sends a plain email through a transport, to see that the transport works.

    The email goes straight to the transport, never through a message bus the mailer may queue
    email on: the transport is what is tested. Given an application's named transports behind
    one :class:`~xtr_mailer.transport.Transports`, ``--transport`` picks one of them by name,
    through the ``X-Transport`` header it reads.

    A container builds the command with its transport. Run without one, the console reports the
    missing ``transport`` parameter rather than build the command bare.
    """

    __slots__ = ("_transport",)

    def __init__(self, transport: TransportInterface) -> None:
        """Send through ``transport``."""
        self._transport = transport

    async def __call__(  # noqa: PLR0913 -- one parameter per argument and option of the command
        self,
        io: ConsoleStyle,
        to: str,
        *,
        from_: Annotated[str, Option(name="from")] = "from@example.org",
        subject: str = "Testing transport",
        body: str = "Testing body",
        transport_name: Annotated[str | None, Option(name="transport")] = None,
    ) -> int:
        """Test mailer transports by sending an email.

        The [green]mailer:test[/green] command tests a mailer transport by sending a simple
        email message:

          [green]mailer:test to@example.com[/green]

        You can also specify a specific transport:

          [green]mailer:test to@example.com --transport=transport_name[/green]

        Note that this command bypasses the message bus if one is configured.

        Args:
            io: Where the command writes.
            to: The recipient of the message.
            from_: The sender of the message.
            subject: The subject of the message.
            body: The body of the message.
            transport_name: The transport to be used.
        """
        try:
            message = Email().to(to).from_(from_).subject(subject).text(body)
            if transport_name:
                _ = message.get_headers().add_text_header("X-Transport", transport_name)
            _ = await self._transport.send(message)
        except (MailerError, MimeError) as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        return ExitCode.SUCCESS
