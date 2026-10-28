"""Named transports, picked per message."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_notifier.exception import InvalidArgumentError, LogicError

from .transport_interface import TransportInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_notifier.message import MessageInterface, SentMessage

__all__ = ["Transports"]


@final
class Transports(TransportInterface):
    """The transports an application configured, by name, behind one transport.

    A message naming a transport (``ChatMessage(..., transport="slack")``, or
    the ``"chat/slack"`` channel) goes to that one and no other; a message
    naming none goes to the first, in configuration order, that supports it.
    """

    __slots__ = ("_transports",)

    def __init__(self, transports: Mapping[str, TransportInterface]) -> None:
        """Pick among ``transports``, keyed by name, in their order."""
        self._transports = dict(transports)

    @override
    def __str__(self) -> str:
        """Name it after its transports' names: ``[slack,telegram]``."""
        return f"[{','.join(self._transports)}]"

    @override
    def supports(self, message: MessageInterface) -> bool:
        """Tell whether any of the transports supports ``message``."""
        return any(transport.supports(message) for transport in self._transports.values())

    @override
    async def send(self, message: MessageInterface) -> SentMessage:
        """Send ``message`` through the transport it names, or the first that supports it.

        Raises:
            InvalidArgumentError: If the message names a transport there is none of.
            LogicError: If the named transport, or every transport, does not support it.
        """
        available = '", "'.join(self._transports)
        name = message.transport
        if not name:
            for transport in self._transports.values():
                if transport.supports(message):
                    return await transport.send(message)
            raise LogicError(
                "None of the available transports support the given message "
                f'(available transports: "{available}").'
            )
        transport = self._transports.get(name)
        if transport is None:
            raise InvalidArgumentError(
                f'The "{name}" transport does not exist (available transports: "{available}").'
            )
        if not transport.supports(message):
            raise LogicError(f'The "{name}" transport does not support the given message.')
        return await transport.send(message)
