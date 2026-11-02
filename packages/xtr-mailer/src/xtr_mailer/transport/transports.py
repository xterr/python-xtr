"""Named transports, picked per email."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_mime import Message

from xtr_mailer._error_text import shown
from xtr_mailer.exception import InvalidArgumentError, LogicError

from .transport_interface import TransportInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_mime import RawMessage

    from xtr_mailer.envelope import Envelope
    from xtr_mailer.sent_message import SentMessage

__all__ = ["Transports"]

_HEADER = "X-Transport"


@final
class Transports(TransportInterface):
    """The transports an application configured, by name, behind one transport.

    An email goes to the first transport, in configuration order, unless an ``X-Transport``
    header names another. The header is taken off the email before it goes — it is an
    instruction to this class, not something a recipient should see — and put back if the
    send fails, so the email can be sent again as it was.
    """

    __slots__ = ("_default", "_transports")

    def __init__(self, transports: Mapping[str, TransportInterface]) -> None:
        """Pick among ``transports``, keyed by name, the first being the default.

        Raises:
            LogicError: There is no transport.
        """
        self._transports: dict[str, TransportInterface] = dict(transports)
        if not self._transports:
            raise LogicError(
                '"xtr_mailer.transport.Transports" must have at least one transport configured.'
            )
        self._default: TransportInterface = next(iter(self._transports.values()))

    @override
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        """Send ``message`` through the transport its ``X-Transport`` header names, or the first.

        Raises:
            InvalidArgumentError: The header names a transport there is none of; the email is
                left as it was.
            Exception: Whatever the transport raised, once the header is put back.
        """
        headers = message.get_headers() if isinstance(message, Message) else None
        if headers is None or not headers.has(_HEADER):
            return await self._default.send(message, envelope)
        removed = list(headers.all(_HEADER))
        name = str(removed[0].get_body())
        transport = self._transports.get(name)
        if transport is None:
            available = '", "'.join(self._transports)
            raise InvalidArgumentError(
                f'The "{shown(name)}" transport does not exist (available transports: '
                f'"{available}").'
            )
        headers.remove(_HEADER)
        try:
            return await transport.send(message, envelope)
        except Exception:
            for header in removed:
                _ = headers.add(header)
            raise

    @override
    def __str__(self) -> str:
        """Name it after its transports' names: ``[main,marketing]``."""
        return f"[{','.join(self._transports)}]"
